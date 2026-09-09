"""PyBLOCK BLAKE2b Template Supplier — main event loop.

Loop invariant (matches PyBLOCK join script):
  Publish when:  block height changed  OR  ≥20 seconds since last publish
  Check interval: 2 seconds (same as upstream loop)
  GBT rules: segwit + blake2b

Startup order is deliberate and fails closed at every step:

  1. Write the "starting" health sentinel before anything else, so a crash
     during initialisation can never be read as "not started yet".
  2. Record the PID, so the health check can tell a live loop from a stale file.
  3. Install signal handlers, so a stop during a long wait is recorded as such.
  4. Load config, retrying rather than exiting so the precise validation error
     stays visible in the health check until the operator fixes it.
  5. When Tor is the selected network, prove a circuit can actually be built to
     the publish target before entering the loop. There is no clearnet fallback.

Any exception that escapes all of that is caught at the top level and recorded
as "failed" before the process exits — the health file is never left saying
"starting" after the process is gone.
"""

import logging
import signal
import sys
import time

from supplier import tor
from supplier.config import Config, ConfigError
from supplier.bitcoin_rpc import BitcoinRPC, RPCError
from supplier.pyblock import PyblockPublisher, PublishError, TorNotReadyError
from supplier.health import HealthState, write_health, write_pid, write_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pyblock-supplier")

POLL_INTERVAL_S = 2
PUBLISH_INTERVAL_S = 20

# Refresh the health file this often while the loop is idle between publishes,
# so a healthy-but-quiet service is never mistaken for a stalled one. Must stay
# comfortably below health.STALE_AFTER_S.
HEARTBEAT_INTERVAL_S = 15

# How long to wait between retries when config is invalid or Tor is unusable.
RETRY_INTERVAL_S = 10


def _heartbeat(health: HealthState, last_write: float) -> float:
    """Rewrite the current state if it is getting close to being stale."""
    now = time.time()
    if now - last_write < HEARTBEAT_INTERVAL_S:
        return last_write
    health.touch()
    write_health(health)
    return now


def _load_config(health: HealthState) -> Config:
    """Load config, waiting for the operator to fix it rather than exiting.

    Exiting here would leave the health check reporting a dead process instead
    of the actual validation error, and would put StartOS into a restart loop.
    Holding the process open keeps the precise reason on screen; the Config
    action restarts the service once the values are corrected.
    """
    logged = ""
    while True:
        try:
            return Config.load()
        except ConfigError as e:
            msg = str(e)
            if msg != logged:
                log.error("Config error: %s", msg)
                logged = msg
            health.set("config_error", msg)
            write_health(health)
            time.sleep(RETRY_INTERVAL_S)


def _await_tor(health: HealthState, config: Config) -> None:
    """Block until Tor can route to the publish target.

    Retries across timeouts instead of giving up: the operator's network may
    come back, and until it does the health check keeps reporting exactly why
    publishing is impossible. Clearnet is never substituted.
    """
    host, port = config.pyblock_endpoint
    log.info("Verifying Tor can reach %s:%d before publishing", host, port)

    def _progress(reason: str) -> None:
        health.set("tor_unavailable", reason)
        write_health(health)
        log.info("Waiting for Tor: %s", reason)

    while True:
        try:
            tor.wait_until_ready(host, port, on_wait=_progress)
            log.info("Tor circuit to %s:%d confirmed", host, port)
            return
        except tor.TorUnavailableError as e:
            msg = str(e)
            log.error("Tor unusable — refusing clearnet fallback: %s", msg)
            health.set("tor_unavailable", msg)
            write_health(health)
            time.sleep(RETRY_INTERVAL_S)


def run() -> None:
    # ── Fail-closed sentinel, written before any initialisation ───────────
    health = write_state("starting", "Supplier starting")
    pid = write_pid()
    log.info("Supplier starting (pid %d)", pid)

    # ── Signal handling (installed early so stops during waits are clean) ─
    def _stop(sig, frame):
        log.info("Received signal %s, stopping", sig)
        health.set("stopped", "Service stopped")
        write_health(health)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # ── Load config ────────────────────────────────────────────────────────
    config = _load_config(health)

    log.info("Payout address configured: yes")
    log.info("Supplier name configured: %s", "yes" if config.supplier_name else "no")
    log.info("Node RPC:       %s:%d", config.rpc_host, config.rpc_port)
    log.info("Network mode:   %s", config.network)
    log.info("PyBLOCK URL:    %s", config.pyblock_url)

    # ── Prove Tor works before claiming to be operational ─────────────────
    if config.uses_tor:
        _await_tor(health, config)

    health.set("starting", "Connecting to the Bitcoin node")
    write_health(health)
    last_write = time.time()

    rpc = BitcoinRPC(config)

    # ── Fetch node UA (best-effort; used as X-PyBLOCK-UA header) ──────────
    node_ua = ""
    try:
        net_info = rpc.getnetworkinfo()
        node_ua = net_info.get("subversion", "")
        log.info("Node UA: %s", node_ua)
    except Exception as e:
        log.warning("Could not fetch node UA: %s", e)

    publisher = PyblockPublisher(config, node_ua=node_ua)

    last_height: int | None = None
    last_sent: float = 0.0

    # ── Main loop ──────────────────────────────────────────────────────────
    while True:
        try:
            chain_info = rpc.getblockchaininfo()
        except RPCError as e:
            msg = f"RPC error: {e}"
            log.warning(msg)
            health.set("node_unavailable", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue
        except Exception as e:
            msg = f"Unexpected RPC error: {e}"
            log.warning(msg)
            health.set("node_unavailable", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue

        if chain_info.get("initialblockdownload", False):
            pct = chain_info.get("verificationprogress", 0) * 100
            msg = f"IBD in progress — {chain_info['blocks']} blocks ({pct:.1f}%)"
            log.info(msg)
            health.set("node_unsynced", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue

        height = chain_info["blocks"]
        now = time.time()
        elapsed = now - last_sent

        if height == last_height and elapsed < PUBLISH_INTERVAL_S:
            last_write = _heartbeat(health, last_write)
            time.sleep(POLL_INTERVAL_S)
            continue

        # ── Get block template ─────────────────────────────────────────────
        try:
            gbt = rpc.getblocktemplate()
        except RPCError as e:
            # RPC code -8 = unknown rule; -32603 = general internal error
            msg = f"getblocktemplate failed (code {e.code}): {e}"
            log.warning(msg)
            health.set("gbt_unsupported", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue
        except Exception as e:
            msg = f"GBT unexpected error: {e}"
            log.warning(msg)
            health.set("gbt_unsupported", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue

        trigger = "new block" if height != last_height else "interval"
        log.info("Publishing template height=%d trigger=%s", height, trigger)

        # ── Publish to PyBLOCK ─────────────────────────────────────────────
        try:
            result = publisher.publish(gbt)
        except TorNotReadyError as e:
            msg = str(e)
            log.error("Tor not ready — refusing clearnet fallback: %s", msg)
            health.set("tor_unavailable", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue
        except PublishError as e:
            msg = str(e)
            log.warning("Publish error: %s", msg)
            health.set("pyblock_rejected", msg)
            write_health(health)
            last_write = time.time()
            time.sleep(POLL_INTERVAL_S)
            continue

        if result.get("ok"):
            msg = f"Accepted — height {height}, trigger: {trigger}"
            log.info("PyBLOCK accepted template: %s", msg)
            health.set("healthy_active", msg)
        else:
            reason = result.get("reason", "rejected (no reason given)")
            msg = f"PyBLOCK rejected at height {height}: {reason}"
            log.warning(msg)
            health.set("pyblock_rejected", msg)

        write_health(health)
        last_write = time.time()
        last_height = height
        last_sent = now

        time.sleep(POLL_INTERVAL_S)


def main() -> None:
    """Entry point — records a terminal health state for every exit path."""
    try:
        run()
    except SystemExit:
        # Raised by the signal handler, which has already recorded "stopped".
        raise
    except BaseException as e:
        log.exception("Supplier terminated unexpectedly")
        try:
            write_state("failed", f"Supplier exited unexpectedly: {type(e).__name__}: {e}")
        except Exception:
            # Never let the failure recorder mask the original failure.
            log.exception("Could not record the failure health state")
        sys.exit(1)


if __name__ == "__main__":
    main()
