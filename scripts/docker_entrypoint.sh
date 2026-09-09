#!/bin/sh
# Main container entrypoint for pyblock-blake2b-supplier.
#
# Starts the Tor daemon (when network=tor) as the unprivileged `tor` user, waits
# for its SOCKS port, then hands off to the Python supplier loop.
#
# The sentinel written here only means "the SOCKS port is listening". Proof that
# Tor can actually route is done by the supplier itself (supplier/tor.py), which
# performs a real SOCKS5 CONNECT to the publish target before reporting healthy.

set -eu

CONFIG_FILE="/root/start9/config.yaml"
TOR_SENTINEL="/tmp/.tor-ready"
TOR_WAIT_TRIES=30

# Never inherit a sentinel from a previous run.
rm -f "$TOR_SENTINEL"

# ── Read network mode from config ─────────────────────────────────────────
# Default to tor if config has not been written yet.
NETWORK="tor"
if [ -f "$CONFIG_FILE" ]; then
  NETWORK=$(sed -n 's/^network:[[:space:]]*["'\'']\{0,1\}\([a-z]*\).*/\1/p' "$CONFIG_FILE" | head -n1)
  [ -n "$NETWORK" ] || NETWORK="tor"
fi

# ── Start Tor if requested ────────────────────────────────────────────────
if [ "$NETWORK" = "tor" ]; then
  echo "[entrypoint] Starting Tor daemon as user 'tor'..."
  mkdir -p /var/lib/tor
  chown -R tor:tor /var/lib/tor
  # Tor refuses to start on a group- or world-readable DataDirectory.
  chmod 700 /var/lib/tor

  # Drop privileges before exec'ing tor. Running the daemon as root would give
  # a compromised Tor process full control of the container.
  su-exec tor:tor tor -f /etc/tor/torrc &

  TRIES=0
  until nc -z 127.0.0.1 9050 2>/dev/null; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -ge "$TOR_WAIT_TRIES" ]; then
      echo "[entrypoint] ERROR: Tor SOCKS port did not open after $((TOR_WAIT_TRIES * 2))s"
      echo "[entrypoint] Refusing to start without Tor — clearnet fallback is not permitted."
      exit 1
    fi
    echo "[entrypoint] Waiting for Tor SOCKS port... ($TRIES/$TOR_WAIT_TRIES)"
    sleep 2
  done

  touch "$TOR_SENTINEL"
  echo "[entrypoint] Tor SOCKS port is listening."
fi

# ── Launch supplier ───────────────────────────────────────────────────────
exec python3 -m supplier.main
