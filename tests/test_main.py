"""Regression tests for synchronization gates in the supplier event loop."""

from unittest.mock import MagicMock, patch

import pytest

from supplier.health import HealthState
from supplier.main import _await_tor, _node_sync_status, run
from supplier.tor import PublishTargetUnavailableError


@pytest.mark.parametrize(
    "chain_info",
    [
        {"blocks": 970518, "initialblockdownload": False},
        {"blocks": 970518, "headers": None, "initialblockdownload": False},
        {"blocks": 970518, "headers": "970546", "initialblockdownload": False},
        {"blocks": True, "headers": 970546, "initialblockdownload": False},
        {"blocks": 970546, "headers": 970518, "initialblockdownload": False},
        {"blocks": 970546, "headers": 970546},
        {"blocks": 970546, "headers": 970546, "initialblockdownload": None},
        {"blocks": 970546, "headers": 970546, "initialblockdownload": 0},
        {"blocks": 970546, "headers": 970546, "initialblockdownload": 1},
        {"blocks": 970546, "headers": 970546, "initialblockdownload": "false"},
    ],
)
def test_node_sync_status_fails_closed_for_invalid_sync_evidence(chain_info):
    synchronized, _, message = _node_sync_status(chain_info)

    assert synchronized is False
    assert message


def test_node_sync_status_is_stateless_for_legitimate_reorgs():
    assert _node_sync_status({
        "blocks": 970534,
        "headers": 970534,
        "initialblockdownload": False,
    })[:2] == (True, 970534)
    assert _node_sync_status({
        "blocks": 970533,
        "headers": 970533,
        "initialblockdownload": False,
    })[:2] == (True, 970533)


def test_await_tor_records_target_outage_without_going_stale():
    config = MagicMock()
    config.pyblock_endpoint = ("example.onion", 80)
    health = HealthState()
    recorded_states = []

    def wait_until_ready(host, port, on_wait):
        assert (host, port) == ("example.onion", 80)
        on_wait(PublishTargetUnavailableError("onion service introduction failed"))

    def record_health(state):
        recorded_states.append((state.state, state.message, state.updated_at))

    with (
        patch("supplier.main.tor.wait_until_ready", side_effect=wait_until_ready),
        patch("supplier.main.write_health", side_effect=record_health),
    ):
        _await_tor(health, config)

    assert recorded_states
    assert recorded_states[-1][0] == "pyblock_unreachable"
    assert "introduction failed" in recorded_states[-1][1]


def test_loop_refuses_stale_template_then_resumes_when_headers_are_caught_up():
    class StopLoop(Exception):
        pass

    config = MagicMock()
    config.uses_tor = False
    config.supplier_name = None
    config.rpc_host = "bitcoind.embassy"
    config.rpc_port = 8332
    config.network = "clearnet"
    config.pyblock_url = "http://pool.pyblock.xyz:5800/"

    rpc = MagicMock()
    rpc.getnetworkinfo.return_value = {"subversion": "/Bitcoin Knots:29.4.1/"}
    rpc.getblockchaininfo.side_effect = [
        {
            "blocks": 970518,
            "headers": 970546,
            "initialblockdownload": False,
            "verificationprogress": 0.999,
        },
        {
            "blocks": 970546,
            "headers": 970546,
            "initialblockdownload": False,
            "verificationprogress": 1.0,
        },
    ]
    template = {"height": 970547, "rules": ["segwit", "blake2b"]}
    rpc.getblocktemplate.return_value = template

    publisher = MagicMock()
    health = HealthState()
    health.set("starting", "Supplier starting")
    recorded_states = []

    def record_health(state):
        recorded_states.append((state.state, state.message))

    def publish_after_sync(gbt):
        assert gbt == template
        assert rpc.getblockchaininfo.call_count == 2
        assert any(
            state == "node_unsynced" and "970518" in message and "970546" in message
            for state, message in recorded_states
        )
        return {"ok": True}

    publisher.publish.side_effect = publish_after_sync

    with (
        patch("supplier.main.write_state", return_value=health),
        patch("supplier.main.write_pid", return_value=1234),
        patch("supplier.main.signal.signal"),
        patch("supplier.main._load_config", return_value=config),
        patch("supplier.main.BitcoinRPC", return_value=rpc),
        patch("supplier.main.PyblockPublisher", return_value=publisher),
        patch("supplier.main.write_health", side_effect=record_health),
        patch("supplier.main.time.sleep", side_effect=[None, StopLoop]),
    ):
        with pytest.raises(StopLoop):
            run()

    publisher.publish.assert_called_once_with(template)
    assert health.state == "healthy_active"
