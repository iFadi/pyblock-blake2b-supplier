"""Tor readiness and routing smoke test.

The container runs its own tor daemon and the supplier is expected to reach
PyBLOCK's onion service through it. "Tor is ready" is not something we can infer
from the daemon having been spawned — tor accepts SOCKS connections well before
it has a usable circuit, and a proxy that answers but cannot route is worse than
one that is down, because it looks healthy.

So readiness is proven, not assumed: the entrypoint drops a sentinel once the
SOCKS port is listening, and this module then performs a real SOCKS5 CONNECT
through it to the publish target. Only a completed CONNECT — which requires tor
to have built a circuit and, for an onion address, to have reached the hidden
service's introduction points — counts as ready. If that does not happen within
the timeout we raise, and the caller fails the health check. There is no
clearnet fallback anywhere in this path.
"""

import os
import socket
import struct
import time

# The tor daemon in this container is configured (see docker/torrc) to listen
# for SOCKS on loopback only. It has no ControlPort.
TOR_PROXY_HOST = os.environ.get("PYBLOCK_TOR_HOST", "127.0.0.1")
TOR_PROXY_PORT = int(os.environ.get("PYBLOCK_TOR_PORT", "9050"))

# Written by the entrypoint once tor's SOCKS port is accepting connections.
TOR_READY_SENTINEL = os.environ.get("PYBLOCK_TOR_SENTINEL", "/tmp/.tor-ready")

# How long to wait for a usable circuit before failing health. Onion service
# descriptors can take a while to fetch on a cold start.
TOR_READY_TIMEOUT_S = float(os.environ.get("PYBLOCK_TOR_TIMEOUT_S", "180"))
TOR_POLL_INTERVAL_S = float(os.environ.get("PYBLOCK_TOR_POLL_S", "3"))

# SOCKS5 reply codes (RFC 1928 §6) plus tor's onion-specific extensions.
_SOCKS5_ERRORS = {
    0x01: "general SOCKS server failure",
    0x02: "connection not allowed by ruleset",
    0x03: "network unreachable",
    0x04: "host unreachable",
    0x05: "connection refused",
    0x06: "TTL expired",
    0x07: "command not supported",
    0x08: "address type not supported",
    0xF0: "onion service descriptor cannot be found",
    0xF1: "onion service descriptor is invalid",
    0xF2: "onion service introduction failed",
    0xF3: "onion service rendezvous failed",
    0xF4: "onion service missing client authorization",
    0xF5: "onion service wrong client authorization",
    0xF6: "onion service invalid address",
    0xF7: "onion service introduction timed out",
}


class TorUnavailableError(Exception):
    """Tor is not usable for routing — never a reason to fall back to clearnet."""


def sentinel_present(path: str = TOR_READY_SENTINEL) -> bool:
    """True once the entrypoint has signalled that tor's SOCKS port came up."""
    return os.path.exists(path)


def socks_port_open(
    host: str = TOR_PROXY_HOST,
    port: int = TOR_PROXY_PORT,
    timeout: float = 5.0,
) -> bool:
    """True if something is accepting TCP connections on the SOCKS port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    buf = b""
    while len(buf) < count:
        chunk = sock.recv(count - len(buf))
        if not chunk:
            raise TorUnavailableError("Tor SOCKS proxy closed the connection early")
        buf += chunk
    return buf


def smoke_test(
    target_host: str,
    target_port: int = 80,
    timeout: float = 60.0,
    proxy_host: str = TOR_PROXY_HOST,
    proxy_port: int = TOR_PROXY_PORT,
) -> None:
    """Prove that traffic can actually be routed to `target_host` through Tor.

    Performs a SOCKS5 handshake and CONNECT, then closes without sending any
    payload. Hostnames are passed to the proxy verbatim (SOCKS5h): the .onion
    address is resolved by tor, never by the local resolver.

    Raises TorUnavailableError if any step fails.
    """
    if not target_host:
        raise TorUnavailableError("No publish target host to test the Tor circuit against")

    host_bytes = target_host.encode("idna") if not target_host.isascii() else target_host.encode()
    if len(host_bytes) > 255:
        raise TorUnavailableError(f"Target host is too long for SOCKS5: {target_host!r}")

    try:
        sock = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    except OSError as e:
        raise TorUnavailableError(
            f"Tor SOCKS proxy {proxy_host}:{proxy_port} is not reachable: {e}"
        ) from e

    try:
        sock.settimeout(timeout)

        # Greeting: version 5, one method, "no authentication required".
        sock.sendall(b"\x05\x01\x00")
        version, method = _recv_exact(sock, 2)
        if version != 0x05:
            raise TorUnavailableError(f"Proxy is not SOCKS5 (version byte {version:#04x})")
        if method != 0x00:
            raise TorUnavailableError(
                f"Tor SOCKS proxy demands authentication method {method:#04x}"
            )

        # CONNECT to a domain name, letting tor do the resolution.
        request = (
            b"\x05\x01\x00\x03"
            + bytes([len(host_bytes)])
            + host_bytes
            + struct.pack("!H", target_port)
        )
        sock.sendall(request)

        _, reply, _, atyp = _recv_exact(sock, 4)
        if reply != 0x00:
            detail = _SOCKS5_ERRORS.get(reply, f"unknown SOCKS5 error {reply:#04x}")
            raise TorUnavailableError(
                f"Tor could not open a circuit to {target_host}:{target_port} — {detail}"
            )

        # Drain the bound address so the proxy is left in a clean state.
        if atyp == 0x01:
            _recv_exact(sock, 4)
        elif atyp == 0x04:
            _recv_exact(sock, 16)
        elif atyp == 0x03:
            length = _recv_exact(sock, 1)[0]
            _recv_exact(sock, length)
        else:
            raise TorUnavailableError(f"Tor returned an unknown address type {atyp:#04x}")
        _recv_exact(sock, 2)
    except socket.timeout as e:
        raise TorUnavailableError(
            f"Tor timed out building a circuit to {target_host}:{target_port}"
        ) from e
    except OSError as e:
        raise TorUnavailableError(f"Tor SOCKS transport error: {e}") from e
    finally:
        try:
            sock.close()
        except OSError:
            pass


def wait_until_ready(
    target_host: str,
    target_port: int = 80,
    timeout: float = TOR_READY_TIMEOUT_S,
    poll_interval: float = TOR_POLL_INTERVAL_S,
    on_wait=None,
    sentinel_path: str = TOR_READY_SENTINEL,
) -> None:
    """Block until Tor can route to the target, or raise after `timeout`.

    `on_wait(reason)` is invoked once per unsuccessful attempt so the caller can
    log progress and keep the health state fresh while waiting.
    """
    deadline = time.monotonic() + timeout
    reason = "Tor has not started yet"

    while True:
        if not sentinel_present(sentinel_path):
            reason = "Waiting for the tor daemon to signal that its SOCKS port is up"
        elif not socks_port_open():
            reason = f"Tor SOCKS proxy {TOR_PROXY_HOST}:{TOR_PROXY_PORT} is not accepting connections"
        else:
            try:
                smoke_test(target_host, target_port, timeout=min(timeout, 60.0))
                return
            except TorUnavailableError as e:
                reason = str(e)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TorUnavailableError(
                f"Tor was not usable within {timeout:.0f}s — {reason}"
            )
        if on_wait is not None:
            on_wait(reason)
        time.sleep(min(poll_interval, remaining))
