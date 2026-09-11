# PyBLOCK BLAKE2b Template Supplier — Instructions

## What this service does

This service connects to your local Bitcoin Knots BLAKE2b node, retrieves a block template
(using `getblocktemplate` with rules `segwit` and `blake2b`), and publishes it to the PyBLOCK
pool every ~20 seconds and instantly on every new block. Carousel miners build on your template;
if one finds the block, your payout address receives a coinbase split on-chain, non-custodially.

Publishing is outbound-only — no inbound ports are opened on your StartOS device.

## Before you begin

A BLAKE2b-capable Bitcoin node (`bitcoind` ≥ 29.4.1) must be installed and running on this
server. It is a **required** dependency: this service reads `getblocktemplate` from the local
node only, and there is no option to point it at a remote node.

Two settings are **required** in your `bitcoin.conf`:

| Setting | Value | Why |
|---|---|---|
| `datacarrier` | `0` | Templates containing OP_RETURN data fail PyBLOCK's `spam` gate and are rejected outright. |
| `blockreservedweight` | `100000` | PyBLOCK's DATUM pool pays every identity inside the coinbase — on a large window that is hundreds of outputs (≈124 WU each). The node must reserve weight for them so the coinbase never displaces transactions. |

Restart the node after adding or changing these settings.

## First-run configuration

After installation, StartOS creates a critical **Configure PyBLOCK BLAKE2b Supplier** task. Open
that task (or go to **Actions & Config → Configure**) and fill in:

| Field | Description |
|---|---|
| **Payout Address** | Your BLAKE2b-chain address (bc1q…, bc1p…, 1…, or 3…). BLAKE2b-chain coinbase payouts go here. |
| **Supplier Name** | Display name on PyBLOCK's suppliers page. Leave blank to be listed by node user agent and payout address. |
| **RPC Host** | Read-only. Resolved automatically from the local Bitcoin node dependency each time the service starts. |
| **RPC Port** | Read-only. Resolved automatically alongside RPC Host (8332 by default). |
| **RPC Username** | The `rpcuser` configured on your Bitcoin Knots BLAKE2b node. |
| **RPC Password** | The `rpcpassword` configured on your node. Required on the first save; later, leave blank to keep it or enter a value to replace it. It is never displayed back to you. |
| **Network Mode** | **Tor** (recommended — IP never sent to PyBLOCK) or **Clearnet**. |

**RPC Host** and **RPC Port** are shown so you can see which node the supplier talks to, but they
cannot be edited. The address is resolved from the local node's bridge binding on every start, so
it stays correct even if the node is reinstalled or moved.

**RPC Password** is intentionally left blank when the form opens, so the stored secret is never
echoed back into your browser. On the first save you must enter a password. On later saves, leave
the field blank to retain the exact stored password, or enter a new value to rotate it. Passwords
are preserved exactly as entered and are never written to the service logs.

Complete this task while the service is stopped, then start the supplier. For later credential or
payout changes, stop the service, run **Configure** again, and start it.

> **Tor note**: The service uses Tor by default. Before it will report healthy it opens a real
> circuit to PyBLOCK's onion service through the container's own Tor daemon. If that circuit
> cannot be built, the service reports `tor_unavailable` and keeps retrying — it never falls back
> to clearnet.

## Health Checks

The service publishes a single health check, **PyBLOCK Publisher**, which reports the state
recorded by the supplier loop:

| Result | Meaning |
|---|---|
| **Success** | `healthy_active` — PyBLOCK accepted your most recent template. |
| **Loading** | `node_unsynced` — the node is in initial block download, its block tip trails its known headers, or synchronization data is invalid. Publication remains paused until synchronized. |
| **Starting** | The supplier has started but has not yet reached its first template. |
| **Failure** | Any other state — see below. |

The check fails closed. It reports success only when the recorded state is fresh **and** the
supplier process that wrote it is still alive:

- The supplier writes a `starting` marker before it initialises anything, so a crash during
  startup can never look like "not started yet".
- Every record carries a timestamp. A record older than 60 seconds is reported as **stale**, not
  as whatever the loop last managed to write. (Adjustable via the `PYBLOCK_HEALTH_MAX_AGE_S`
  environment variable.)
- Every record carries the supplier's process ID. If that process is gone, the check reports the
  service as failed and includes the last state it recorded for diagnosis.
- If the supplier exits on an unhandled error, it records `failed` before terminating.

### Common failure reasons

- `config_error`: A required value is missing or invalid. The exact reason appears in the health
  message — open **Actions → Configure** and correct it. If it says the RPC host could not be
  resolved, install and start a BLAKE2b-capable Bitcoin node, then restart this service.
- `node_unavailable`: The node's JSON-RPC endpoint could not be reached, or rejected the
  credentials. Check **RPC Username** and **RPC Password**.
- `gbt_unsupported`: Your node rejected the `blake2b` rule — it is not a BLAKE2b-capable build.
  Only Bitcoin Knots ≥ 29.4 (rc4) following the BLAKE2b fork supports this.
- `tor_unavailable`: Tor is selected but a circuit to PyBLOCK could not be built. The message
  names the specific SOCKS failure. Clearnet is never substituted.
- `pyblock_rejected`: PyBLOCK rejected your template. The most common cause is OP_RETURN
  transactions in the template — set `datacarrier=0` and restart the node.
- `node_unsynced`: Node synchronization is incomplete or cannot be verified. Wait for the block and header tips to match and for IBD to complete.

## PyBLOCK Ingest Responses

Every template `POST` returns a JSON body. The supplier maps these to the health states above.

| HTTP | Body | Meaning |
|---|---|---|
| `200` | `{"ok": true, "gate": "passed"}` | Accepted — template built on the current tip. |
| `200` | `{"ok": true, "gate": "dedup"}` | Accepted — identical content already validated; this is normal and not an error. |
| `200` | `{"ok": false, "gate": "spam", "reason": "…"}` | Rejected — `datacarrier=0` is missing from your node's `bitcoin.conf`. Add it and restart the node. |
| `200` | `{"ok": false, "gate": "knots", "reason": "…"}` | Rejected — wrong node version. PyBLOCK requires Bitcoin Knots ≥ 29.4.1 / `knots20260508` on the BLAKE2b fork. |
| `200` | `{"ok": false, "gate": "unverified"}` | Rejected — `getblocktemplate mode=proposal` failed on the pool node; the template was not valid against the current tip. |
| `429` | `{"ok": false, "reason": "rate limited — max 30 posts/min per IP"}` | Rate limited. The supplier publishes at most ~3 posts/min (height change or 20-second interval), well under the limit; this should never appear in normal operation. |

## Supplier Dashboard

Every supplier has a public status page at:

```
https://b.pyblock.xyz:8443/supplier.php?s=<first 16 characters of sha256(payout_address)>
```

This page shows your live/fresh/paused status and the number of templates declared. It is the
canonical way to confirm that PyBLOCK is receiving your templates.

You do not need to compute the hash yourself: run the **Supplier Dashboard** action in the
service's Actions list. It shows the URL as a copyable string derived from your saved payout
address; copy it into a browser to open the page. If the payout address has not been saved yet,
or the stored value is not a valid address, the action explains what to fix instead of showing
a URL.

## Payout Terms

PyBLOCK states the reward split as: **96% miner · 3% supplier · 1% PyBLOCK** for the Carousel.
These are pool-operator terms and are not guaranteed by this software. Verify current terms at
https://b.pyblock.xyz:8443/suppliers.php before relying on them.

## Stopping / Uninstalling

Stopping this service stops template publishing immediately. Your node, wallet, and funds are
unaffected. No data is lost on the node side.
