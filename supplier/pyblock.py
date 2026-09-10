"""PyBLOCK template publisher.

Protocol proven by reading the official join script source at
https://b.pyblock.xyz:8443/join (inspected 2026-09-07, never executed).

Endpoints:
  Clearnet: http://pool.pyblock.xyz:5800/
  Tor:      http://qzhxvlnzfir7pwmsheadahe6hejqkvb3z5nn35ils32hptgpwuzabhyd.onion/

Request: POST with raw GBT JSON body (optionally gzip-compressed).
Headers:
  X-PyBLOCK-UA:   node subversion string
  X-PyBLOCK-User: payout address
  X-PyBLOCK-Name: supplier name (omitted if not set)

Response: JSON  {"ok": true}  or  {"reason": "..."}
"""

import gzip
import http.client
import json
import socket
import urllib.request
import urllib.error
from typing import Any

# Single source of truth for the proxy endpoint lives in supplier.tor, which
# also owns the readiness proof used at startup. Re-exported here because the
# SOCKS connection classes below are the hot path that uses it.
from supplier.tor import TOR_PROXY_HOST, TOR_PROXY_PORT, socks_port_open


class PublishError(Exception):
    pass


class TorNotReadyError(PublishError):
    """Tor was requested but the proxy is not reachable.

    Never falls back to clearnet — raises instead.
    """


class _SocksHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection subclass that routes through a SOCKS5h proxy (Tor).

    SOCKS5h means remote DNS — the .onion hostname is resolved by Tor, never
    by the local resolver.
    """

    def connect(self):
        import socks  # PySocks — installed in Docker image; verified in _tor_opener
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, TOR_PROXY_HOST, TOR_PROXY_PORT, rdns=True)
        # AbstractHTTPHandler.do_open() copies opener.open(..., timeout=...)
        # onto this connection.  A manually-created PySocks socket does not
        # inherit that value, so apply it before either the proxy handshake or
        # target connection can block.
        if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            s.settimeout(self.timeout)
        s.connect((self.host, self.port or 80))
        self.sock = s


class _SocksHTTPHandler(urllib.request.HTTPHandler):
    """urllib handler that opens HTTP connections via _SocksHTTPConnection."""

    def http_open(self, req):
        return self.do_open(_SocksHTTPConnection, req)


def _tor_ready() -> bool:
    """Check if the Tor SOCKS5 proxy port is accepting connections.

    This is the cheap per-publish guard. The expensive proof that tor can
    actually build a circuit is done once at startup by supplier.tor.
    """
    return socks_port_open()


class PyblockPublisher:
    def __init__(self, config, node_ua: str = ""):
        self.config = config
        self.node_ua = node_ua
        self._session_handler = self._build_handler()

    def _build_handler(self):
        """Build a urllib opener.

        For clearnet: uses default opener (no proxy for the local node).
        For Tor: uses a SOCKS5 proxy handler — the 'requests[socks]' package
        is not available in all Alpine builds, so we implement a minimal
        SOCKS5h connect manually via a custom HTTPHandler subclass.

        The simpler approach used here: we install a SocksiPy / PySocks
        socket monkey-patch only for this publisher's session. Because we
        use urllib.request with a fresh opener per publish call, this does
        not affect the RPC socket.
        """
        # Handler is resolved at publish time to allow lazy Tor startup.
        return None

    def publish(self, gbt: dict) -> dict:
        """Push a GBT response to PyBLOCK. Returns the parsed JSON response."""
        url = self.config.pyblock_url
        use_tor = self.config.network == "tor"

        if use_tor and not _tor_ready():
            raise TorNotReadyError(
                f"Tor SOCKS5 proxy not ready at {TOR_PROXY_HOST}:{TOR_PROXY_PORT}"
            )

        body = json.dumps(gbt).encode()
        body_gz = gzip.compress(body)
        use_gzip = len(body_gz) < len(body)

        headers = {
            "Content-Type": "application/json",
            "X-PyBLOCK-UA": self.node_ua or "pyblock-blake2b-supplier/1.0.0",
            "X-PyBLOCK-User": self.config.payout_address,
        }
        if self.config.supplier_name:
            headers["X-PyBLOCK-Name"] = self.config.supplier_name
        if use_gzip:
            headers["Content-Encoding"] = "gzip"
            send_body = body_gz
        else:
            send_body = body

        req = urllib.request.Request(
            url,
            data=send_body,
            headers=headers,
            method="POST",
        )

        if use_tor:
            opener = self._tor_opener()
        else:
            opener = urllib.request.build_opener()

        try:
            with opener.open(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                body_resp = json.loads(e.read())
                return body_resp
            except Exception:
                raise PublishError(f"HTTP {e.code} from PyBLOCK: {e.reason}")
        except urllib.error.URLError as e:
            raise PublishError(f"Cannot reach PyBLOCK ({url}): {e.reason}")
        except Exception as e:
            raise PublishError(f"Publish failed: {e}")

    @staticmethod
    def _tor_opener():
        """Return an opener that routes HTTP through the Tor SOCKS5 proxy."""
        try:
            import socks  # noqa: F401 — verify PySocks is present before first connect
        except ImportError:
            raise PublishError(
                "PySocks not installed — cannot route through Tor. "
                "This is a packaging defect; rebuild the Docker image."
            )
        return urllib.request.build_opener(_SocksHTTPHandler)
