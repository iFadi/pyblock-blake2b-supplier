#!/bin/sh
# StartOS health check — prints {"result": ..., "message": ...} on stdout.
# Runs from /app so `python3 -m supplier.healthcheck` resolves the package.
set -eu
cd /app
exec python3 -m supplier.healthcheck
