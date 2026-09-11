# This OCI index is Python 3.12.14 on Alpine 3.24.1. Its linux/amd64 and
# linux/arm64 child digests are recorded in docker/base-images.lock.json.
FROM python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a AS test

WORKDIR /app
COPY requirements-runtime.txt requirements-test.txt ./
COPY supplier/ ./supplier/
COPY tests/    ./tests/
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-test.txt
RUN python -m pytest tests/ -v --tb=short

# ── Stage 2: runtime image ────────────────────────────────────────────────
FROM python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a AS runtime

ARG TARGETARCH

# tor:            Tor daemon for onion transport
# su-exec:        drops privileges so tor runs as the `tor` user, not root
# netcat-openbsd: nc for the SOCKS readiness probe in the entrypoint
COPY docker/runtime-apk.lock docker/tor-apk-sha256.lock /tmp/dependency-locks/
COPY scripts/install-runtime-apks.sh /usr/local/bin/install-runtime-apks
RUN TARGETARCH="$TARGETARCH" /usr/local/bin/install-runtime-apks \
    && rm -f /usr/local/bin/install-runtime-apks \
    && rm -rf /tmp/dependency-locks \
    && python -m pip --version

COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-runtime.txt \
    && rm -f /tmp/requirements-runtime.txt

# Tor config is baked into the image: it is not operator-tunable and must not
# be reachable from the data volume. It opens no ControlPort.
COPY docker/torrc /etc/tor/torrc
RUN chown root:tor /etc/tor/torrc && chmod 640 /etc/tor/torrc

WORKDIR /app
COPY supplier/ ./supplier/
COPY scripts/docker_entrypoint.sh scripts/health-check.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh

# StartOS mounts the data volume here
VOLUME /root/start9

CMD ["/usr/local/bin/docker_entrypoint.sh"]
