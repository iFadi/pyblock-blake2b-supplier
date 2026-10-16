# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- Package workflow (`.github/workflows/package.yml`) no longer consumes `Start9Labs/start-technologies/.github/workflows/build.yml` as a reusable workflow. That workflow's own transitive steps invoke `actions/checkout@v6` and `Start9Labs/start-technologies/.github/actions/*@master` by mutable ref, so pinning only its own commit SHA did not make the resulting build trustworthy. The package workflow is now repository-owned: it builds the `x86_64` and `aarch64` candidates directly with every external action pinned to an immutable commit SHA, preserving the existing two-architecture behavior and ephemeral (non-persistent) signing key semantics.
- Re-pinned `docker/setup-qemu-action`, `docker/setup-docker-action`, and `docker/setup-buildx-action` to their reviewed `v4.4.0`/`v5.5.0`/`v4.4.1` commit SHAs, and `actions/attest-build-provenance` to its reviewed `v4.2.2` commit SHA, in `release-stage.yml`.
- Extended `.github/scripts/validate-release-workflow.test.js` to also validate `package.yml`: every external action must be pinned to a full commit SHA, and none of `package.yml`, `release-stage.yml`, or `release-promote.yml` may delegate to an externally-owned reusable workflow.
- `package.yml`'s `actions/checkout` step now sets `persist-credentials: false`, so untrusted `pull_request` build steps cannot read a persisted repository token out of git configuration.
- Hardened `package.yml`'s ephemeral signing-key handling: key material is now written under `umask 077` and explicitly `chmod 0600`, and a new always-running cleanup step removes `$HOME/.startos/id.key.pem` and `.startos/build.key.pem` (and their now-empty directories) and proves both are absent before the build artifact is uploaded — the cleanup step runs even when the build step fails, and artifact upload only proceeds if cleanup succeeds. `validate-release-workflow.test.js` now asserts this ordering and semantics so it cannot regress.

## [1.0.0-rev15] — 2026-10-16

### Changed
- Migrated `@start9labs/start-sdk` from `2.0.9` to `3.0.6`. This is a deliberate SDK migration, not a routine dependency bump: SDK v3 removes the inline manifest `dependencies` literal and the `setupDependencies`/`checkDependencies` pattern in favor of a `Dependency`/`Dependencies` builder passed to both `buildManifest` and `setupInit`. `startos/dependencies.ts` now declares the `bitcoind` requirement with `sdk.Dependency.required(...)`, preserving the exact same runtime requirement (`versionRange: '*'`, `kind: 'running'`, `healthChecks: []`, for the documented reason that the BLAKE2b Knots fork does not reliably export standard health check ids) and is wired into `buildManifest` (`startos/index.ts`) and `setupInit` (`startos/init/index.ts`) as the SDK now requires.
- Updated the Supplier Dashboard action's `single` result to set the now-required `launchable: false` field; SDK v3.0.6 requires every field on an action result value.
- Updated the health-check `SubContainer.exec` call to the SDK v3 named-options signature (`{ timeout: 30_000 }` instead of a third positional argument); the 30-second timeout and health-check behavior are unchanged.
- StartOS minimum compatibility is now `0.4.0.2`, the default `osVersion` SDK 3.0.6 writes into the manifest (SDK v3's documented minimum). `README.md` now states this explicitly instead of the generic "StartOS 0.4".
- Bumped the canonical package version to `1.0.0:15` and updated every release identity surface (`release-stage.yml`, `release-promote.yml`, `.github/scripts/validate-release-tag.test.js`, `.github/scripts/validate-release-workflow.test.js`) to match.

### Removed
- Dropped the `typescript`, `@types/node`, and `@vercel/ncc` direct `devDependencies`: SDK 3.0.6 now declares these itself (`typescript ^6.0.3`, `@vercel/ncc ^0.38.4`, `@types/node ^22.19.0`), and they resolve from the SDK's own dependency tree without a redundant top-level declaration. `prettier` is similarly SDK-supplied and was never declared directly. TypeScript 7, `@vercel/ncc` 0.45.0, and `@types/node` 26.6.5 — the versions Dependabot's PR #7 proposed — were not adopted; none are required by this migration, and none are the versions the SDK itself now pins.
- Removed `scripts/patch-bundled-advisories.js` and its `postinstall` hook. SDK 2.0.9 shipped `eslint` and `typescript-eslint` as `bundleDependencies`, packing a vulnerable transitive `brace-expansion`/`js-yaml` inside the SDK tarball where npm `overrides` could not reach them; the patch script worked around that by overwriting the packed copies on every install. SDK 3.0.6 ships only `@start9labs/start-core` as a bundled dependency — `eslint` and `typescript-eslint` install normally and already resolve to patched versions (`brace-expansion@1.1.21`/`@5.0.12`, `js-yaml@4.3.2`) through ordinary npm resolution. Running the old patch script against the new tree produced `extraneous`/`invalid` phantom package copies under the SDK's own `node_modules` and broke the SDK's `lint.mjs` runner's module resolution; `npm audit --audit-level=high` reports zero vulnerabilities without it. `js-yaml` is kept as a direct `devDependency` (unaliased) because `.github/scripts/validate-release-workflow.test.js` uses it directly to parse workflow YAML, independent of the removed SDK-patching concern.

### Added
- Added `.prettierrc` pointing at the SDK's shared Prettier config, per the SDK's documented project layout — the SDK's own `s9pk.mk` build gate (`make x86` / `make arm`, used by `release-stage.yml` and `package.yml`) now runs a `FORMAT_CHECK` step and a bundled ESLint pass (`node_modules/@start9labs/start-sdk/lint.mjs`) against `startos/` as part of every package build, which SDK 2.0.9 did not. `startos/` was reformatted to pass it; no behavior changed.

## [1.0.0-rev14] — 2026-10-16

### Fixed
- Bound each Tor readiness attempt to 10 seconds inside the existing 180-second readiness window, preventing a live supplier from crossing the 60-second health staleness threshold while a target is unavailable.
- Refresh failing health before blocking Tor probes and preserve the precise dependency failure across retries.
- Distinguish a local Tor failure from a PyBLOCK publish target that Tor cannot reach.
- Suppress duplicate application progress logs while continuing to refresh the health record on every attempt.
- Preserve fail-closed Tor behavior; no automatic clearnet fallback was added.
- Re-pin the runtime image's Tor APK to `tor-0.4.9.14-r0`, the version now published on Alpine edge/community; the previously locked `0.4.9.11-r0` build was superseded and removed from the mirror, breaking runtime image builds with a 404. Both architecture SHA-256 hashes were independently re-verified against the live, signature-verified package index, and `docker/runtime-apk.lock` was regenerated from an actual install run to also pick up `libseccomp` moving to `2.6.1-r0` in the current closure.

## [1.0.0-rev13] — 2026-09-11

### Added
- **Supplier Dashboard action:** a user-invoked StartOS action that displays the operator's PyBLOCK supplier status page URL as a copyable string. The URL (`https://b.pyblock.xyz:8443/supplier.php?s=<sid>`) is computed from the first 16 hex characters of `sha256(payout_address)` — no manual calculation needed. The address is validated with the same rule as the Configure action before hashing; a missing, blank, or invalid address, or an unreadable `config.yaml`, produces an operator-facing message instead of a URL and never echoes configuration contents.

### Fixed
- Dashboard URL query parameter corrected from `?sid=` to `?s=` to match the PyBLOCK supplier portal's actual URL scheme.

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
