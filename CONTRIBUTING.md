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

The Release workflow accepts only tags in the form
`v<major>.<minor>.<patch>-rev<revision>` (for example, `v1.0.0-rev10`). It
requires an exact match between the tag and `startos/versions/current.ts`
(`v1.0.0-rev10` maps to `1.0.0:10`), requires the `DEV_KEY` repository secret,
and creates an initial GitHub **prerelease** containing the signed x86_64 and
aarch64 `.s9pk` files plus `SHA256SUMS`. Its local jobs reproduce the pinned
official workflow's QEMU, Docker, Buildx, and containerd image-store setup,
pin every external action by immutable SHA, and checksum-verify the exact
`start-cli` v2.0.0 binaries before building or inspecting packages. Only the
isolated tag-release key-provision step receives the persistent repository
`DEV_KEY`; the workflow removes key material after each matrix build. It
verifies package names, architectures, version, release notes, and the manifest
git hash before using `gh` to create the prerelease. It does not publish to a
StartOS registry or S3.

A manual Release workflow dispatch is a non-publishing rehearsal. Set its
`release_tag` input to the tag intended for the checked-out package version. It
validates the same tag-to-version contract, generates ephemeral keys, runs the
same two-architecture packaging jobs, and uploads one-day verification
artifacts. The manual path does not reference `DEV_KEY`, and its release job is
disabled. Run and review this dry run before creating a release tag.

## Dependency lock maintenance

The Docker build has three reproducibility boundaries:

- `docker/base-images.lock.json` records the immutable OCI index digest and the
  linux/amd64 and linux/arm64 child manifests. Both Dockerfile stages use the
  index digest, so BuildKit selects the locked child for the target platform.
- `docker/runtime-apk.lock` pins every Alpine package added above the base
  image. The base image digest fixes all packages already present in that
  image. Tor 0.4.9.11-r0 is downloaded as the exact architecture-specific,
  Alpine-signed APK and checked against `docker/tor-apk-sha256.lock` because
  Alpine's mutable package index no longer selects that tested version.
- `requirements-runtime.txt` and `requirements-test.txt` pin every Python
  package and require SHA-256 verification. PyYAML contains separate accepted
  wheel hashes for x86_64 and aarch64; pure-Python wheels share one hash.

All three boundaries fail closed: a missing version, changed artifact, unknown
architecture, omitted hash, or changed image digest stops the build or the
regression suite. The remaining inputs are the checked-out source tree,
BuildKit/start-cli implementation, and host kernel/emulation. The `.s9pk`
signature is intentionally not byte-for-byte reproducible because signing can
introduce build-specific material; validate the embedded manifest, source
identity, image contents, and checksums for each exact candidate instead.

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

1. In **Settings → Secrets and variables → Actions**, configure `DEV_KEY` as a
   repository secret. Never store the key in Git, command history, workflow
   inputs, issue text, or logs.
2. Confirm the intended release commit is on `main` and all CI and Package
   workflow checks have passed. Manually run the Release workflow with
   `release_tag=v1.0.0-rev10`; verify both ephemeral dry-run artifacts were
   produced and confirm that no GitHub Release was created.
3. Update the example tag below, then create and push one annotated tag:

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
   git tag -a "$RELEASE_TAG" -m "Release $RELEASE_TAG"
   git push origin "refs/tags/$RELEASE_TAG"
   ```

4. In GitHub Actions, verify the Release workflow completed successfully.
   Then inspect the GitHub prerelease and independently verify both architecture
   `.s9pk` assets against `SHA256SUMS` before deciding whether to promote or
   announce it. Promotion from prerelease remains a separate maintainer action.

Creating the tag is the deployment action: do not reuse or move a published
release tag. Repository visibility changes remain separate, manual
administrative actions and are not performed by these workflows.

## Scope note

This package is an integration layer. It does not implement a Bitcoin node, a
pool server, or a mining algorithm. Changes that increase the external
dependency surface (new network connections, new configuration fields, new
system calls) warrant extra scrutiny.
