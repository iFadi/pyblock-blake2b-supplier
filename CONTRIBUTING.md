# Contributing

Thanks for your interest in contributing.

## Reporting bugs

Open a [GitHub issue](https://github.com/iFadi/pyblock-blake2b-supplier/issues)
with:
- StartOS version
- Package version (visible in the About panel)
- Health state and message at the time of the problem
- Steps to reproduce

For security issues, see [SECURITY.md](SECURITY.md) instead of filing a
public issue.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes. Run the test suite before opening a pull request:

   ```sh
   # TypeScript type check
   npm ci
   npm run check
   npm test

   # Python unit tests (install the hash-locked test dependencies first)
   python3 -m pip install --require-hashes -r requirements-test.txt
   python3 -m pytest tests/ -v

   # Full test suite via Docker
   docker build --target test -t pyblock-blake2b-supplier-test .
   ```

3. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit
   messages (`feat:`, `fix:`, `chore:`, `docs:`, etc.).
4. Open a pull request against `main` with a clear description of what changed
   and why.

## Code style

- Python: follow existing style; no external formatter is enforced, but keep
  lines under 100 characters.
- TypeScript: the project uses `tsc --noEmit` for type checking; no separate
  linter is configured.
- No dead code, commented-out blocks, or `TODO` left in production paths.

## Testing

New TypeScript action logic should come with tests in `tests-ts/`, and new
Python logic should come with tests in `tests/`. The existing Python suite covers
config validation, RPC client, health state machine, Tor probe, and PyBLOCK
publisher. Mirror the existing test style (plain `pytest`, no third-party
fixtures beyond `unittest.mock`).

## Packaging workflows

The Package workflow runs for pull requests, pushes to `main`, and manual
dispatches. Its official reusable build-workflow caller is pinned to a fixed
upstream commit and receives no `DEV_KEY`; the reusable workflow generates an
ephemeral signing key and uploads temporary `.s9pk` GitHub Actions artifacts.
These artifacts are suitable only for verification and testing, not release
distribution. The upstream workflow transitively invokes mutable helper-action
references, so this accepted trust boundary is intentionally limited to
non-secret, non-distributable Package builds.

Release publication is split into two manual workflows. A tag push is inert:
neither workflow listens for `push`, and creating a tag never rebuilds or
publishes a package.

**Release Stage** accepts the exact full source SHA and a tag-shaped candidate
name. The workflow must itself be dispatched from that SHA and accepts only
tags in the form `v<major>.<minor>.<patch>-rev<revision>` that exactly match
`startos/versions/current.ts` (`v1.0.0-rev10` maps to `1.0.0:10`). It builds
and signs x86_64 and aarch64 once, validates the resulting manifests, package
version, architecture, `gitHash`, locked dependency inventories, and checksums,
then attests and uploads the exact bytes as one private GitHub Actions artifact
retained for three days. Staging creates no tag and no GitHub Release.

Only the `Build and sign candidate once` step references `DEV_KEY`. It writes
the key with mode `0600`, unsets the environment value before invoking the
build, and removes both key copies before any inspection or upload. The secret
must be an environment secret in `release-staging`; ordinary CI, Package,
pull-request, push, assembly, and promotion jobs cannot access it.

**Release Promote** is a separate manual workflow. It requires the approved
Release Stage run ID, exact source SHA, and exact tag. It rejects a staging run
from another workflow or source, a failed run, a missing, ambiguous, or expired
artifact, a metadata/checksum mismatch, an invalid attestation, a tag that is
not a GitHub-verified signed annotated tag at the exact source commit, an
inactive/mismatched tag-protection ruleset, and an existing release. It
downloads the staged bytes without building or signing and publishes only the
two attested `.s9pk` files and their staged `SHA256SUMS` as a prerelease. It
does not publish to a StartOS registry or S3.

GitHub configuration is part of the release trust boundary and must be created
manually; these workflows do not alter repository settings:

- Create a `release-staging` Environment and store `DEV_KEY` there. Restrict
  deployment branches/tags to trusted refs; optional required reviewers add a
  second gate before the signing jobs.
- Create a `release-promotion` Environment with required reviewers (including
  the explicit release approver), prevent self-review, and restrict deployment
  refs. Do not configure `DEV_KEY` in this environment.
- Create an active tag ruleset targeting exactly
  `refs/tags/v*.*.*-rev*` with creation, update, and deletion restrictions.
  Give only the intended maintainer role a bypass path for initial creation.
  Set repository variable `RELEASE_TAG_RULESET_ID` to that ruleset's numeric
  ID. Promotion checks the ruleset and separately requires GitHub's signature
  verification for the annotated tag object.
- Keep Actions artifact attestations enabled and allow the workflows' declared
  `id-token`/`attestations` permissions. Promotion has no signing secret and no
  build permission; its sole write permission is `contents: write` for the
  GitHub prerelease.

## Dependency lock maintenance

The Docker build has three reproducibility boundaries:

- `docker/base-images.lock.json` records the immutable OCI index digest and the
  linux/amd64 and linux/arm64 child manifests. Both Dockerfile stages use the
  index digest, so BuildKit selects the locked child for the target platform.
- `docker/runtime-apk.lock` pins every Alpine package added above the base
  image. The installer records the pre-install and post-install inventories on
  each architecture, rejects replacement/removal of a base package, and
  requires the complete added closure to equal the lock exactly. The base image
  digest fixes packages already present in that image. Tor 0.4.9.11-r0 is
  downloaded as the exact architecture-specific, Alpine-signed APK and checked
  against `docker/tor-apk-sha256.lock` because Alpine's mutable package index no
  longer selects that tested version.
- `requirements-runtime.txt` and `requirements-test.txt` pin every Python
  package and require SHA-256 verification. PyYAML contains separate accepted
  wheel hashes for x86_64 and aarch64; pure-Python wheels share one hash.

All three boundaries fail closed: a missing version, changed artifact, unknown
architecture, omitted hash, changed closure, or changed image digest stops the
build or regression suite. This is not a claim of whole-image or `.s9pk` byte
reproducibility. BuildKit execution, the checksum-pinned `start-cli` binary,
runner kernel/emulation, archive metadata, and signature generation remain
boundaries that can change output bytes. The stage workflow therefore builds
and signs once, records checksums and inventories, attests those exact outputs,
and requires promotion to reuse those bytes rather than reproduce them.

To update a lock:

1. Resolve and review artifacts independently for linux/amd64 and linux/arm64.
   Record OCI child digests and SHA-256 values from authoritative registries or
   downloaded artifacts; do not infer one architecture from the other.
2. Update the smallest applicable lock and the Dockerfile index digest. Keep
   exact `name=version-rN` APK entries for the complete added package closure.
3. Run `npm test`, then build both Docker targets with cache disabled. Inside
   each runtime image, record `apk info -v` and `python -m pip list --format=freeze`.
4. Build and inspect each `.s9pk` architecture. Record its SHA-256, manifest
   version, architecture, git hash, and dependency inventory before any tag or
   publication decision. Evidence for one architecture is not proof for the
   other.

The immutable `v1.0.0-rev6` and `v1.0.0-rev7` tags are failed pre-release
attempts. Neither attempt published a GitHub Release or package, and neither tag
may be moved or reused.

### Maintainer release runbook

1. Complete the Environment, ruleset, repository-variable, and attestation
   setup above. Never store `DEV_KEY` in Git, command history, workflow inputs,
   issue text, logs, repository-level secrets, or `release-promotion`.
2. Confirm the intended release commit is on `main` and all CI and Package
   checks have passed. Dispatch **Release Stage** from that exact commit with
   `source_sha=<full SHA>` and `release_tag=v1.0.0-rev10`. Record the successful
   run ID. Download the private x86_64 candidate from that run, verify it against
   `SHA256SUMS`, and target-test that exact signed package on StartOS. Confirm
   staging created neither a tag nor a GitHub Release.
3. After explicit approval of those exact staged bytes, create and push one
   signed annotated tag at the staged source commit. The tag ruleset must be
   active; never move or reuse a release tag:

   ```sh
   git switch main
   git pull --ff-only origin main
   RELEASE_TAG=v1.0.0-rev10
   printf '%s\n' "$RELEASE_TAG" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+-rev[0-9]+$'
   grep -F "version: '1.0.0:10'" startos/versions/current.ts
   git ls-remote --exit-code --tags origin "refs/tags/$RELEASE_TAG" && {
     echo "Tag already exists on origin" >&2
     exit 1
   }
   test "$(git rev-parse HEAD)" = '<staged full source SHA>'
   git tag -s "$RELEASE_TAG" -m "Release $RELEASE_TAG"
   git push origin "refs/tags/$RELEASE_TAG"
   ```

4. Dispatch **Release Promote** from the exact tagged source with the recorded
   `staging_run_id`, full `source_sha`, and `release_tag`. Approve the protected
   `release-promotion` Environment only after comparing all three values with
   the reviewed stage. The workflow verifies and publishes without rebuilding.
5. Inspect the resulting GitHub prerelease and independently verify both
   architecture assets against `SHA256SUMS` before announcement or any separate
   visibility/state change.

Neither tag creation nor tag push is an automated deployment trigger.
Repository visibility and prerelease-to-final changes remain separate manual
administrative actions and are not performed by these workflows.

## Scope note

This package is an integration layer. It does not implement a Bitcoin node, a
pool server, or a mining algorithm. Changes that increase the external
dependency surface (new network connections, new configuration fields, new
system calls) warrant extra scrutiny.
