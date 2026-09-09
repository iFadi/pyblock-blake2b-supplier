"""Tests for supplier.tor — the Tor routing smoke test.

These exercise the SOCKS5 client against a scripted fake proxy rather than a
real tor daemon, so they cover the failure branches (which is the point: the
smoke test exists to turn silent non-routing into a health failure).
"""

import socket
import struct
import threading
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from supplier import tor
from supplier.tor import TorUnavailableError, sentinel_present, smoke_test, socks_port_open


def _recv(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise AssertionError("client closed early")
        buf += chunk
    return buf


@contextmanager
def fake_proxy(handler):
    """Run `handler(conn, captured)` for a single connection on a free port."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    captured = {}

    def serve():
        try:
            conn, _ = srv.accept()
            with conn:
                handler(conn, captured)
        except (OSError, AssertionError):
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port, captured
    finally:
        srv.close()
        thread.join(timeout=2)


def _read_connect(conn, captured):
    captured["greeting"] = _recv(conn, 3)
    conn.sendall(b"\x05\x00")
    captured["request_head"] = _recv(conn, 4)
    length = _recv(conn, 1)[0]
    captured["host"] = _recv(conn, length)
    captured["port"] = struct.unpack("!H", _recv(conn, 2))[0]


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


ONION = "qzhxvlnzfir7pwmsheadahe6hejqkvb3z5nn35ils32hptgpwuzabhyd.onion"


# ── happy path ────────────────────────────────────────────────────────────

def test_smoke_test_completes_a_connect():
    def handler(conn, captured):
        _read_connect(conn, captured)
        conn.sendall(b"\x05\x00\x00\x01" + b"\x00\x00\x00\x00" + b"\x00\x00")

    with fake_proxy(handler) as (port, captured):
        smoke_test(ONION, 80, timeout=5, proxy_port=port)

    assert captured["greeting"] == b"\x05\x01\x00"  # SOCKS5, no authentication
    # ATYP 0x03 = domain name: the .onion is resolved by Tor, never locally.
    assert captured["request_head"] == b"\x05\x01\x00\x03"
    assert captured["host"] == ONION.encode()
    assert captured["port"] == 80


def test_smoke_test_drains_a_domain_bound_address():
    """A bound address of any ATYP must be consumed so the socket closes clean."""
    def handler(conn, captured):
        _read_connect(conn, captured)
        conn.sendall(b"\x05\x00\x00\x03" + bytes([3]) + b"abc" + b"\x00\x50")

    with fake_proxy(handler) as (port, _):
        smoke_test(ONION, 80, timeout=5, proxy_port=port)


# ── failure paths ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "code,fragment",
    [
        (0x01, "general SOCKS server failure"),
        (0x04, "host unreachable"),
        (0xF0, "onion service descriptor cannot be found"),
        (0xF7, "onion service introduction timed out"),
        (0x7B, "unknown SOCKS5 error"),
    ],
)
def test_connect_failure_is_reported_with_a_readable_reason(code, fragment):
    def handler(conn, captured):
        _read_connect(conn, captured)
        conn.sendall(bytes([0x05, code, 0x00, 0x01]) + b"\x00\x00\x00\x00\x00\x00")

    with fake_proxy(handler) as (port, _):
        with pytest.raises(TorUnavailableError, match=fragment):
            smoke_test(ONION, 80, timeout=5, proxy_port=port)


def test_non_socks5_proxy_is_rejected():
    def handler(conn, captured):
        _recv(conn, 3)
        conn.sendall(b"\x04\x00")

    with fake_proxy(handler) as (port, _):
        with pytest.raises(TorUnavailableError, match="not SOCKS5"):
            smoke_test(ONION, 80, timeout=5, proxy_port=port)


def test_proxy_demanding_authentication_is_rejected():
    def handler(conn, captured):
        _recv(conn, 3)
        conn.sendall(b"\x05\xff")

    with fake_proxy(handler) as (port, _):
        with pytest.raises(TorUnavailableError, match="authentication"):
            smoke_test(ONION, 80, timeout=5, proxy_port=port)


def test_proxy_hanging_up_mid_handshake_is_rejected():
    def handler(conn, captured):
        _recv(conn, 3)
        conn.close()

    with fake_proxy(handler) as (port, _):
        with pytest.raises(TorUnavailableError, match="closed the connection"):
            smoke_test(ONION, 80, timeout=5, proxy_port=port)


def test_unreachable_proxy_is_rejected():
    with pytest.raises(TorUnavailableError, match="not reachable"):
        smoke_test(ONION, 80, timeout=2, proxy_port=_closed_port())


def test_empty_target_host_is_rejected():
    with pytest.raises(TorUnavailableError, match="No publish target"):
        smoke_test("", 80, timeout=2)


def test_overlong_target_host_is_rejected():
    with pytest.raises(TorUnavailableError, match="too long"):
        smoke_test("a" * 256, 80, timeout=2, proxy_port=_closed_port())


# ── readiness probes ──────────────────────────────────────────────────────

def test_sentinel_present(tmp_path):
    path = str(tmp_path / ".tor-ready")
    assert sentinel_present(path) is False
    open(path, "w").close()
    assert sentinel_present(path) is True


def test_socks_port_open_detects_a_listener():
    with fake_proxy(lambda conn, captured: None) as (port, _):
        assert socks_port_open("127.0.0.1", port, timeout=2) is True
    assert socks_port_open("127.0.0.1", _closed_port(), timeout=2) is False


# ── wait_until_ready ──────────────────────────────────────────────────────

def test_wait_until_ready_times_out_without_the_sentinel(tmp_path):
    with pytest.raises(TorUnavailableError, match="was not usable within"):
        tor.wait_until_ready(
            ONION, 80, timeout=0.2, poll_interval=0.05,
            sentinel_path=str(tmp_path / "never"),
        )


def test_wait_until_ready_reports_progress_while_waiting(tmp_path):
    reasons = []
    with pytest.raises(TorUnavailableError):
        tor.wait_until_ready(
            ONION, 80, timeout=0.3, poll_interval=0.05,
            on_wait=reasons.append, sentinel_path=str(tmp_path / "never"),
        )
    assert reasons
    assert all("tor daemon" in r for r in reasons)


def test_wait_until_ready_returns_once_a_circuit_is_proven(tmp_path):
    sentinel = tmp_path / ".tor-ready"
    sentinel.write_text("")
    with patch("supplier.tor.socks_port_open", return_value=True), \
         patch("supplier.tor.smoke_test") as fake:
        tor.wait_until_ready(ONION, 80, timeout=5, sentinel_path=str(sentinel))
    fake.assert_called_once()


def test_wait_until_ready_retries_a_failing_smoke_test(tmp_path):
    sentinel = tmp_path / ".tor-ready"
    sentinel.write_text("")
    attempts = [TorUnavailableError("no descriptor"), None]

    def flaky(*args, **kwargs):
        outcome = attempts.pop(0)
        if outcome is not None:
            raise outcome

    with patch("supplier.tor.socks_port_open", return_value=True), \
         patch("supplier.tor.smoke_test", side_effect=flaky):
        tor.wait_until_ready(ONION, 80, timeout=5, poll_interval=0.01,
                             sentinel_path=str(sentinel))
    assert attempts == []


def test_socks_port_down_is_reported_as_the_reason(tmp_path):
    sentinel = tmp_path / ".tor-ready"
    sentinel.write_text("")
    reasons = []
    with patch("supplier.tor.socks_port_open", return_value=False):
        with pytest.raises(TorUnavailableError, match="not accepting connections"):
            tor.wait_until_ready(ONION, 80, timeout=0.2, poll_interval=0.05,
                                 on_wait=reasons.append, sentinel_path=str(sentinel))
    assert reasons and "not accepting connections" in reasons[0]
