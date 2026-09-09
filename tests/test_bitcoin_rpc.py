"""Tests for supplier.bitcoin_rpc."""

import json
import unittest
from unittest.mock import MagicMock, patch
from http.client import HTTPResponse
from io import BytesIO

from supplier.bitcoin_rpc import BitcoinRPC, RPCError


def _mock_config(host="localhost", port=8332, user="u", password="p"):
    cfg = MagicMock()
    cfg.rpc_host = host
    cfg.rpc_port = port
    cfg.rpc_user = user
    cfg.rpc_password = password
    return cfg


def _fake_response(body: dict, status: int = 200):
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestBitcoinRPC:
    def setup_method(self):
        self.rpc = BitcoinRPC(_mock_config())

    def test_getblockcount_success(self):
        fake = _fake_response({"result": 850000, "error": None, "id": 1})
        with patch("urllib.request.urlopen", return_value=fake):
            count = self.rpc.getblockcount()
        assert count == 850000

    def test_getblockchaininfo_ibd(self):
        info = {
            "blocks": 100,
            "initialblockdownload": True,
            "verificationprogress": 0.01,
        }
        fake = _fake_response({"result": info, "error": None, "id": 1})
        with patch("urllib.request.urlopen", return_value=fake):
            result = self.rpc.getblockchaininfo()
        assert result["initialblockdownload"] is True

    def test_rpc_error_raised(self):
        err_body = {"result": None, "error": {"code": -8, "message": "unknown rule: blake2b"}, "id": 1}
        fake = _fake_response(err_body)
        with patch("urllib.request.urlopen", return_value=fake):
            import pytest
            with pytest.raises(RPCError) as exc_info:
                self.rpc.getblocktemplate()
        assert exc_info.value.code == -8
        assert "blake2b" in str(exc_info.value)

    def test_getblocktemplate_success(self):
        gbt = {
            "version": 536870912,
            "rules": ["segwit", "blake2b"],
            "transactions": [],
            "coinbasevalue": 312500000,
            "height": 850000,
        }
        fake = _fake_response({"result": gbt, "error": None, "id": 1})
        with patch("urllib.request.urlopen", return_value=fake):
            result = self.rpc.getblocktemplate()
        assert result["height"] == 850000
        assert "blake2b" in result["rules"]

    def test_connection_refused_raises_rpc_error(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            import pytest
            with pytest.raises(RPCError, match="Connection failed"):
                self.rpc.getblockcount()

    def test_auth_header_set(self):
        import base64
        rpc = BitcoinRPC(_mock_config(user="alice", password="secret"))
        expected = "Basic " + base64.b64encode(b"alice:secret").decode()
        assert rpc._auth == expected
