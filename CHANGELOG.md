# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0-rev12] — 2026-09-11

### Added
- **Supplier Dashboard action:** displays the operator's personal PyBLOCK dashboard URL directly in the StartOS app UI. The URL (`https://b.pyblock.xyz:8443/supplier.php?sid=<sid>`) is computed from the first 16 hex characters of `sha256(payout_address)` — no manual calculation needed. Shows a clear placeholder when the app has not been configured yet.

## [1.0.0-rev11] — 2026-09-11

### Added
- Bound each Tor-routed HTTP publication to a 30-second end-to-end deadline.
- Fail-closed synchronization gate: refuse to publish while the Bitcoin node block tip trails its known header tip, even when initial block download reports false; resume automatically after synchronization.
- Fail closed when node block, header, or IBD synchronization data is missing or malformed.

### Changed
- Pinned the multi-architecture Python base image, the complete added Alpine package set (including Tor at the StartOS-tested `0.4.9.11-r0` build), and all Python dependencies to immutable versions and verified hashes.
- CI pipeline split into two phases: `release-stage` builds and signs into a private artifact bundle; `release-promote` downloads the staged bytes, verifies attestations and the protected annotated tag, and publishes without rebuilding.
- Fail closed if any locked dependency artifact changes or becomes unavailable.

### Fixed
- `jq -c` normalization in the `assemble-stage` step to ensure consistent compact JSON comparison of `runtimeApks`.

## [1.0.0-rev8] — 2026-09-10

### Added
- Ephemeral-key GitHub Actions dry run that exercises both release architectures (x86_64 and aarch64) without publishing.
- GitHub Actions package builds and signed GitHub Release automation.
- Direct automated test coverage for RPC password initialization, retention, rotation, and non-disclosure.

### Fixed
- Restored the Docker, Buildx, QEMU, and containerd prerequisites omitted from the failed rev7 pre-release attempt.

### Security
- Keep the stored RPC password when a later Configure save leaves the masked field blank (prevents accidental credential loss).
- Require an RPC password on the first Configure save and allow explicit rotation thereafter.
- Never return RPC passwords to the Configure form or disclose configuration identifiers in service logs.

---

*Releases before v1.0.0-rev8 were superseded before publication or are internal only.*
*Rev6 and rev7 produced no GitHub Release; they remain as immutable audit tags.*
