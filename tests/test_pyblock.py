"""Tests for supplier.pyblock."""

import json
import gzip
import sys
from unittest.mock import MagicMock, patch, call
import pytest
import urllib.error

from supplier.pyblock import (
    PyblockPublisher,
    PublishError,
    TorNotReadyError,
    _SocksHTTPConnection,
    _SocksHTTPHandler,
    TOR_PROXY_HOST,
    TOR_PROXY_PORT,
)
from supplier.config import PYBLOCK_CLEARNET_URL, PYBLOCK_ONION_URL


def _mock_config(network="clearnet"):
    cfg = MagicMock()
    cfg.payout_address = "bc1qtest000000000000000000000000000000000000"
    cfg.supplier_name = "Test Supplier"
    cfg.network = network
    cfg.pyblock_url = PYBLOCK_ONION_URL if network == "tor" else PYBLOCK_CLEARNET_URL
    return cfg


SAMPLE_GBT = {
    "version": 536870912,
    "rules": ["segwit", "blake2b"],
    "transactions": [],
    "coinbasevalue": 312500000,
    "height": 850000,
}


def _mock_response(body: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestPyblockPublisher:
    def setup_method(self):
        self.pub = PyblockPublisher(_mock_config(), node_ua="/Bitcoin Knots:29.4.1/")

    def test_successful_publish(self):
        fake = _mock_response({"ok": True})
        with patch("urllib.request.OpenerDirector.open", return_value=fake):
            result = self.pub.publish(SAMPLE_GBT)
        assert result["ok"] is True

    def test_rejected_template_returns_reason(self):
        fake = _mock_response({"ok": False, "reason": "OP_RETURN detected"})
        with patch("urllib.request.OpenerDirector.open", return_value=fake):
            result = self.pub.publish(SAMPLE_GBT)
        assert result.get("reason") == "OP_RETURN detected"

    def test_network_error_raises_publish_error(self):
        with patch("urllib.request.OpenerDirector.open",
                   side_effect=urllib.error.URLError("timed out")):
            with pytest.raises(PublishError, match="Cannot reach PyBLOCK"):
                self.pub.publish(SAMPLE_GBT)

    def test_tor_not_ready_raises_tor_error(self):
        tor_pub = PyblockPublisher(_mock_config(network="tor"), node_ua="")
        with patch("supplier.pyblock._tor_ready", return_value=False):
            with pytest.raises(TorNotReadyError, match="not ready"):
                tor_pub.publish(SAMPLE_GBT)

    def test_no_clearnet_fallback_when_tor_configured(self):
        """Tor failing must raise, not fall back to clearnet silently."""
        tor_pub = PyblockPublisher(_mock_config(network="tor"), node_ua="")
        with patch("supplier.pyblock._tor_ready", return_value=False):
            with pytest.raises(TorNotReadyError):
                tor_pub.publish(SAMPLE_GBT)
        # Ensure the clearnet URL was NOT used (url stays onion)
        assert tor_pub.config.pyblock_url == PYBLOCK_ONION_URL

    def test_x_pyblock_user_header_set(self):
        """X-PyBLOCK-User header must carry the payout address."""
        captured = []

        def capture_open(req, timeout=None):
            captured.append(req)
            return _mock_response({"ok": True})

        with patch("urllib.request.OpenerDirector.open", side_effect=capture_open):
            self.pub.publish(SAMPLE_GBT)

        req = captured[0]
        assert req.get_header("X-pyblock-user") == "bc1qtest000000000000000000000000000000000000"

    def test_x_pyblock_name_header_set(self):
        captured = []

        def capture_open(req, timeout=None):
            captured.append(req)
            return _mock_response({"ok": True})

        with patch("urllib.request.OpenerDirector.open", side_effect=capture_open):
            self.pub.publish(SAMPLE_GBT)

        req = captured[0]
        assert req.get_header("X-pyblock-name") == "Test Supplier"

    def test_no_name_header_when_supplier_name_none(self):
        cfg = _mock_config()
        cfg.supplier_name = None
        pub = PyblockPublisher(cfg, node_ua="")
        captured = []

        def capture_open(req, timeout=None):
            captured.append(req)
            return _mock_response({"ok": True})

        with patch("urllib.request.OpenerDirector.open", side_effect=capture_open):
            pub.publish(SAMPLE_GBT)

        req = captured[0]
        assert req.get_header("X-pyblock-name") is None


class TestSocksHandler:
    """Exercises the real Tor handler/connection path without needing a live proxy."""

    def test_tor_opener_returns_opener_with_socks_handler(self):
        """_tor_opener() must build an opener that contains _SocksHTTPHandler."""
        mock_socks = MagicMock()
        with patch.dict(sys.modules, {"socks": mock_socks}):
            opener = PyblockPublisher._tor_opener()
        assert any(isinstance(h, _SocksHTTPHandler) for h in opener.handlers)

    def test_tor_opener_raises_when_pysocks_missing(self):
        """_tor_opener() must raise PublishError if PySocks is not installed."""
        with patch.dict(sys.modules, {"socks": None}):
            with pytest.raises(PublishError, match="PySocks not installed"):
                PyblockPublisher._tor_opener()

    def test_socks_connection_connect_routes_via_proxy(self):
        """_SocksHTTPConnection.connect() must configure the socket for SOCKS5h
        and assign it to self.sock — this is the do_open() contract."""
        mock_sock = MagicMock()
        mock_socks = MagicMock()
        mock_socks.SOCKS5 = 2
        mock_socks.socksocket.return_value = mock_sock

        conn = _SocksHTTPConnection("oniontest.onion", timeout=30)
        with patch.dict(sys.modules, {"socks": mock_socks}):
            conn.connect()

        mock_socks.socksocket.assert_called_once()
        mock_sock.set_proxy.assert_called_once_with(
            2, TOR_PROXY_HOST, TOR_PROXY_PORT, rdns=True
        )
        mock_sock.settimeout.assert_called_once_with(30)
        mock_sock.connect.assert_called_once_with(("oniontest.onion", 80))
        assert conn.sock is mock_sock

    def test_socks_handler_calls_do_open_with_connection_class(self):
        """_SocksHTTPHandler.http_open() must pass _SocksHTTPConnection to do_open."""
        handler = _SocksHTTPHandler()
        mock_req = MagicMock()
        mock_req.host = "oniontest.onion"
        with patch.object(handler, "do_open", return_value=MagicMock()) as mock_do:
            handler.http_open(mock_req)
        mock_do.assert_called_once_with(_SocksHTTPConnection, mock_req)
