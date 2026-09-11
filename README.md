# PyBLOCK BLAKE2b Supplier — StartOS Package

[![CI](https://github.com/iFadi/pyblock-blake2b-supplier/actions/workflows/ci.yml/badge.svg)](https://github.com/iFadi/pyblock-blake2b-supplier/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Publishes BLAKE2b block templates from a local Bitcoin Knots node to the
[PyBLOCK Carousel](https://b.pyblock.xyz:8443/suppliers.php) mining pool.
Packaged for StartOS 0.4 using the TypeScript Package API.

---

## Download / Installation

Download the latest stable StartOS package from GitHub:

- [x86_64 `.s9pk`](https://github.com/iFadi/pyblock-blake2b-supplier/releases/latest/download/pyblock-blake2b-supplier_x86_64.s9pk)
- [aarch64 `.s9pk`](https://github.com/iFadi/pyblock-blake2b-supplier/releases/latest/download/pyblock-blake2b-supplier_aarch64.s9pk)
- [SHA256 checksums](https://github.com/iFadi/pyblock-blake2b-supplier/releases/latest/download/SHA256SUMS)
- [Latest stable release page](https://github.com/iFadi/pyblock-blake2b-supplier/releases/latest)

Most current Start9/StartOS x86 machines use **x86_64**. Verify your server's
architecture before sideloading, then install the downloaded `.s9pk` through
your StartOS side-loading workflow.

After installation, StartOS creates a critical **Configure PyBLOCK BLAKE2b
Supplier** task. Open that task and fill in your payout address, RPC
credentials, and transport preference before starting the service.

See [`instructions.md`](instructions.md) for the full first-run walkthrough
and health-state reference.

---

## Overview

This package connects to the local `bitcoind` dependency on your StartOS
device, calls `getblocktemplate` with the `segwit` and `blake2b` rules, and
submits the resulting template to PyBLOCK every ≤20 seconds and immediately
on every new block.

**Outbound-only.** No inbound ports are opened. Your private keys, wallet
seed, and RPC credentials never leave the device.

**Tor by default.** Templates are published through the package's own Tor
daemon to PyBLOCK's onion service. Clearnet is an opt-in alternative; the
service fails rather than silently downgrading when Tor is selected but
unavailable.

---

## Features

- Polls block and header heights every 2 s; publishes only from a synchronized tip
- GBT rules: `segwit` + `blake2b` (required for BLAKE2b Carousel eligibility)
- Tor-first transport: routes to PyBLOCK's `.onion` via an in-container Tor daemon
- Clearnet fallback available as explicit opt-in
- Eight distinct health states reported to StartOS
- Payout address validated locally against the PyBLOCK address regex
- RPC credentials stored in the package's persistent volume; never written to logs
- Zero inbound surface: no listening ports, no ControlPort on the Tor daemon

---

## Requirements

- StartOS 0.4 server
- `bitcoind` (Bitcoin Knots ≥ 29.4.1 with BLAKE2b support) installed and
  running on the same server — required dependency; remote nodes are not supported
- `datacarrier=0` in your node's `bitcoin.conf` (PyBLOCK rejects templates
  containing OP_RETURN outputs)
- A BLAKE2b-chain payout address and dedicated RPC credentials for this supplier

---

## Architecture

```
StartOS device
│
├── Bitcoin Knots BLAKE2b node  (separate StartOS package: bitcoind)
│   └── JSON-RPC on port 8332 (internal, never forwarded)
│
└── pyblock-blake2b-supplier  (this package)
    ├── supplier/main.py          — main event loop
    ├── supplier/bitcoin_rpc.py   — JSON-RPC client (direct, no proxy)
    ├── supplier/pyblock.py       — HTTP POST publisher (via Tor SOCKS5)
    ├── supplier/config.py        — config loader + validator
    ├── supplier/health.py        — state machine → /root/start9/health.json
    ├── supplier/tor.py           — Tor readiness probe and SOCKS helpers
    ├── scripts/docker_entrypoint.sh  — starts Tor daemon, then Python loop
    └── startos/                  — StartOS TypeScript Package API
        ├── manifest/index.ts     — package manifest
        ├── main.ts               — daemon + health check wiring
        ├── backups.ts            — volume backup/restore
        ├── dependencies.ts       — bitcoind dependency declaration
        ├── actions/config.ts     — Configure action (payout address, RPC, transport)
        ├── init/index.ts         — lifecycle hooks + first-run setup task
        └── versions/current.ts  — version + release notes
```

### Loop invariant

| Parameter | Value |
|---|---|
| Poll interval | 2 s |
| Max publish interval | 20 s |
| GBT rules | `segwit`, `blake2b` |

### Transport endpoints

| Mode | Endpoint |
|---|---|
| Tor (default) | `http://qzhxvlnzfir7pwmsheadahe6hejqkvb3z5nn35ils32hptgpwuzabhyd.onion/` |
| Clearnet | `http://pool.pyblock.xyz:5800/` |

### Headers sent to PyBLOCK

| Header | Value |
|---|---|
| `X-PyBLOCK-UA` | Node `subversion` string from `getnetworkinfo` |
| `X-PyBLOCK-User` | Payout address |
| `X-PyBLOCK-Name` | Supplier name (omitted if not configured) |
| `Content-Encoding` | `gzip` when compression reduces payload size |

---

## Health states

| State | StartOS result | Meaning |
|---|---|---|
| `healthy_active` | Success | PyBLOCK accepted your most recent template |
| `node_unsynced` | Loading | Node is in initial block download, behind its known headers, or returned invalid synchronization data |
| `starting` | Starting | Supplier has started; first publish not yet sent |
| `node_unavailable` | Failure | RPC unreachable or credentials rejected |
| `gbt_unsupported` | Failure | Node rejected the `blake2b` GBT rule |
| `tor_unavailable` | Failure | Tor selected but circuit could not be built |
| `pyblock_rejected` | Failure | PyBLOCK rejected the template (often: OP_RETURN in mempool) |
| `config_error` | Failure | Missing or invalid configuration value |

The health check fails closed: it reports success only when the recorded
state is fresh (≤60 s) and the supplier process is still alive.

---

## Build

### Prerequisites

```sh
# Node.js ≥ 20 + npm
node --version
npm --version

# start-cli (for packaging .s9pk files)
curl -fsSL https://start9.com/start-cli/install.sh | sh

# squashfs-tools (packaging dependency)
sudo apt install -y squashfs-tools squashfs-tools-ng jq

# Docker (for running unit tests via the Dockerfile test stage)
docker --version
```

### Install SDK dependencies

```sh
npm ci
```

### TypeScript type check

```sh
npm run check
```

### TypeScript security tests

```sh
npm test
```

Covers first-save password rejection, exact retention, exact rotation, and
non-disclosure through logs and Configure form defaults.

### Unit tests (via Docker build stage)

```sh
docker build --target test -t pyblock-blake2b-supplier-test .
```

Runs the full Python test suite inside the Docker `test` stage. No containers
remain running after the build completes.

### Unit tests (direct, no Docker)

If Python 3.12+ and the required packages are available locally:

```sh
python3 -m pytest tests/ -v
```

Dependencies: `pyyaml`, `PySocks`, `pytest`.

Container and Python dependencies are version- and hash-locked for both
supported architectures. See
[dependency lock maintenance](CONTRIBUTING.md#dependency-lock-maintenance) for
the maintained reproducibility boundary and update procedure.

### Bundle TypeScript (no .s9pk output)

```sh
npm run build
```

Produces `javascript/index.js` — the bundled StartOS ABI used during packaging.

### Build .s9pk package (requires start-cli)

```sh
make x86        # x86_64 only
make arm        # aarch64 only
make arches     # both architectures
```

Outputs: `pyblock-blake2b-supplier_x86_64.s9pk` or `_aarch64.s9pk`.

### GitHub package builds

CI builds x86_64 and aarch64 `.s9pk` packages for verification. Temporary
GitHub Actions workflow artifacts are test-only and are not distributable
releases.

Official distributable packages are signed `.s9pk` GitHub Release assets
published with `SHA256SUMS`. See the
[maintainer release and signing details](CONTRIBUTING.md#maintainer-release-runbook).

---

## Configuration

The service reads its runtime config from `/root/start9/config.yaml` (written by
the StartOS Configure action). The operator must supply:

| Field | Required | Description |
|---|---|---|
| Payout Address | Yes | BLAKE2b-chain address for coinbase splits |
| RPC Username | Yes | `rpcuser` from your Bitcoin Knots node |
| RPC Password | First save | `rpcpassword` from your node; later, leave blank to retain it or enter a new value to rotate it |
| Supplier Name | No | Public display name on PyBLOCK's suppliers page |
| Network Mode | Yes | `tor` (recommended) or `clearnet` |

RPC host and port are resolved automatically from the local `bitcoind`
dependency on every start and are shown read-only in the Configure form.
The masked RPC password is never prefilled or returned to the browser. A blank
field on a later save retains the exact stored value; the first save requires a
password, and any later nonblank value replaces it without transformation.

---

## Security

- **No inbound ports.** The service opens zero listening sockets.
- **Credential isolation.** The RPC password is stored in the package's
  persistent volume and is never written to logs or error messages. Storage
  encryption depends on the operator's StartOS host configuration.
- **Minimal disclosure to PyBLOCK.** The pool receives only: the block template
  JSON, the payout address, the optional supplier name, and the node user-agent
  string.
- **Tor-or-fail.** When Tor is selected, the service proves a live circuit to the
  publish target before entering the main loop. It never silently falls back to
  clearnet.
- **Payout address validation.** The address is validated locally against the
  PyBLOCK pattern before use.
- **Tor daemon hardened.** `SocksPolicy` restricts the proxy to loopback only;
  no `ControlPort` is opened.

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process.

---

## Screenshots

![Configure form with sensitive values redacted](docs/screenshots/configure.png)

This genuine StartOS Configure capture uses opaque redactions for the payout
address, RPC endpoint, and RPC username. The saved RPC password is never
returned to the form. On later edits, leave the password field blank to keep
the stored value or enter a new value to rotate it.

See [`docs/screenshots/CAPTURE.md`](docs/screenshots/CAPTURE.md) for the capture
and redaction checklist. Generated or mockup screenshots are not accepted.

---

## Payout terms disclaimer

PyBLOCK's documented split for the Carousel is 96% miner · 3% supplier · 1%
PyBLOCK. These are pool-operator terms; this package does not hard-code or
guarantee any percentage. Verify current terms at
https://b.pyblock.xyz:8443/suppliers.php before relying on them.

---

## License

[MIT](LICENSE) — Copyright © 2026 Fadi Asbih

---

## Donate

Support the project at [donate.asbih.com](https://donate.asbih.com/).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
