# ── Stage 1: test runner ───────────────────────────────────────────────────
FROM python:3.12-alpine AS test

WORKDIR /app
COPY supplier/ ./supplier/
COPY tests/    ./tests/
# PyYAML for config loading, PySocks for Tor routing, pytest for tests
RUN pip install --no-cache-dir pyyaml PySocks pytest
RUN python -m pytest tests/ -v --tb=short

# ── Stage 2: runtime image ────────────────────────────────────────────────
FROM python:3.12-alpine AS runtime

# tor:            Tor daemon for onion transport
# su-exec:        drops privileges so tor runs as the `tor` user, not root
# netcat-openbsd: nc for the SOCKS readiness probe in the entrypoint
RUN apk add --no-cache \
      tor \
      su-exec \
      netcat-openbsd \
    && pip install --no-cache-dir pyyaml PySocks

# Tor config is baked into the image: it is not operator-tunable and must not
# be reachable from the data volume. It opens no ControlPort.
COPY docker/torrc /etc/tor/torrc
RUN chown root:tor /etc/tor/torrc && chmod 640 /etc/tor/torrc

WORKDIR /app
COPY supplier/ ./supplier/
COPY scripts/  /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh

# StartOS mounts the data volume here
VOLUME /root/start9

CMD ["/usr/local/bin/docker_entrypoint.sh"]
