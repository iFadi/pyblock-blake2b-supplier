"""Tests for supplier.config."""

import os
import tempfile
import pytest
import yaml

from supplier.config import Config, ConfigError, PYBLOCK_CLEARNET_URL, PYBLOCK_ONION_URL


def _write_config(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


VALID_BASE = {
    "payout-address": "bc1qtest000000000000000000000000000000000000",
    # What the StartOS runtime writes: the resolved bitcoind bridge address.
    "rpc-host": "10.0.3.1",
    "rpc-port": 8332,
    "rpc-user": "satoshi",
    "rpc-password": "hunter2",
    "network": "tor",
}


def test_valid_tor_config():
    path = _write_config(VALID_BASE)
    cfg = Config.load(path)
    assert cfg.payout_address == VALID_BASE["payout-address"]
    assert cfg.rpc_port == 8332
    assert cfg.network == "tor"
    assert cfg.pyblock_url == PYBLOCK_ONION_URL
    assert cfg.supplier_name is None
    os.unlink(path)


def test_valid_clearnet_config():
    data = {**VALID_BASE, "network": "clearnet", "supplier-name": "Example Node"}
    path = _write_config(data)
    cfg = Config.load(path)
    assert cfg.network == "clearnet"
    assert cfg.pyblock_url == PYBLOCK_CLEARNET_URL
    assert cfg.supplier_name == "Example Node"
    os.unlink(path)


def test_valid_legacy_p2pkh_address():
    data = {**VALID_BASE, "payout-address": "1AAAAAAAAAAAA AAAAAAAAAAAAA"}
    # The genesis block address — format valid even though historic
    data["payout-address"] = "1AAAAAAAAAAAAAAAAAAAAAAAAA"
    path = _write_config(data)
    cfg = Config.load(path)
    assert cfg.payout_address.startswith("1")
    os.unlink(path)


def test_valid_p2sh_address():
    data = {**VALID_BASE, "payout-address": "3BBBBBBBBBBBBBBBBBBBBBBBBB"}
    path = _write_config(data)
    cfg = Config.load(path)
    assert cfg.payout_address.startswith("3")
    os.unlink(path)


def test_missing_payout_address():
    data = {k: v for k, v in VALID_BASE.items() if k != "payout-address"}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="payout-address is required"):
        Config.load(path)
    os.unlink(path)


def test_invalid_payout_address():
    data = {**VALID_BASE, "payout-address": "not-an-address"}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="not a valid BLAKE2b-chain address"):
        Config.load(path)
    os.unlink(path)


def test_missing_rpc_user():
    data = {k: v for k, v in VALID_BASE.items() if k != "rpc-user"}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="rpc-user is required"):
        Config.load(path)
    os.unlink(path)


def test_missing_rpc_password():
    data = {k: v for k, v in VALID_BASE.items() if k != "rpc-password"}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="rpc-password is required"):
        Config.load(path)
    os.unlink(path)


def test_invalid_network():
    data = {**VALID_BASE, "network": "i2p"}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="network must be"):
        Config.load(path)
    os.unlink(path)


def test_rpc_port_out_of_range():
    data = {**VALID_BASE, "rpc-port": 80}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="rpc-port.*out of range"):
        Config.load(path)
    os.unlink(path)


def test_missing_config_file():
    with pytest.raises(ConfigError, match="Config not found"):
        Config.load("/nonexistent/config.yaml")


def test_supplier_name_whitespace_is_none():
    data = {**VALID_BASE, "supplier-name": "   "}
    path = _write_config(data)
    cfg = Config.load(path)
    assert cfg.supplier_name is None
    os.unlink(path)


def test_missing_rpc_host_is_rejected():
    """An unresolved bridge address must fail loudly, not fall back to a guess."""
    data = dict(VALID_BASE)
    del data["rpc-host"]
    with pytest.raises(ConfigError, match="rpc-host is empty"):
        Config.load(_write_config(data))


def test_blank_rpc_host_is_rejected():
    data = dict(VALID_BASE, **{"rpc-host": "   "})
    with pytest.raises(ConfigError, match="rpc-host is empty"):
        Config.load(_write_config(data))


@pytest.mark.parametrize(
    "host",
    ["http://remote.example:8332", "https://node.example/rpc", "remote.example/rpc"],
)
def test_remote_rpc_url_is_rejected(host):
    """A remote RPC URL is never an acceptable substitute for the local node."""
    data = dict(VALID_BASE, **{"rpc-host": host})
    with pytest.raises(ConfigError, match="not a URL"):
        Config.load(_write_config(data))


def test_pyblock_endpoint_tor():
    cfg = Config.load(_write_config(dict(VALID_BASE, network="tor")))
    host, port = cfg.pyblock_endpoint
    assert host.endswith(".onion")
    assert port == 80
    assert cfg.uses_tor is True


def test_pyblock_endpoint_clearnet():
    cfg = Config.load(_write_config(dict(VALID_BASE, network="clearnet")))
    assert cfg.pyblock_endpoint == ("pool.pyblock.xyz", 5800)
    assert cfg.uses_tor is False
