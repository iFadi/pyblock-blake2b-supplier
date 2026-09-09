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

   # Python unit tests (requires pyyaml, PySocks, pytest)
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
dispatches. The official reusable build workflow generates an ephemeral
signing key for every run and uploads temporary `.s9pk` GitHub Actions
artifacts. These artifacts are suitable only for verification and testing;
they are not distributable release artifacts.

The Release workflow accepts only tags in the form
`v<major>.<minor>.<patch>-rev<revision>` (for example, `v1.0.0-rev6`). It
requires an exact match between the tag and `startos/versions/current.ts`
(`v1.0.0-rev6` maps to `1.0.0:6`), requires the `DEV_KEY` repository secret,
attaches the signed `.s9pk` files to a GitHub Release, and includes SHA-256
hashes in the release notes. Only this tag-triggered workflow uses the
persistent repository `DEV_KEY`, and its GitHub Release assets are the
distributable release artifacts. It does not publish to a StartOS registry or
S3.

### Maintainer release runbook

1. In **Settings → Secrets and variables → Actions**, configure `DEV_KEY` as a
   repository secret. Never store the key in Git, command history, workflow
   inputs, issue text, or logs.
2. Confirm the intended release commit is on `main` and all CI and Package
   workflow checks have passed.
3. Update the example tag below, then create and push one annotated tag:

   ```sh
   git switch main
   git pull --ff-only origin main
   RELEASE_TAG=v1.0.0-rev6
   printf '%s\n' "$RELEASE_TAG" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+-rev[0-9]+$'
   grep -F "version: '1.0.0:6'" startos/versions/current.ts
   git ls-remote --exit-code --tags origin "refs/tags/$RELEASE_TAG" && {
     echo "Tag already exists on origin" >&2
     exit 1
   }
   git tag -a "$RELEASE_TAG" -m "Release $RELEASE_TAG"
   git push origin "refs/tags/$RELEASE_TAG"
   ```

4. In GitHub Actions, verify the Release workflow completed successfully.
   Then inspect the GitHub Release and verify that both architecture `.s9pk`
   assets and their SHA-256 hashes are present before announcing the release.

Creating the tag is the deployment action: do not reuse or move a published
release tag. Repository visibility changes remain separate, manual
administrative actions and are not performed by these workflows.

## Scope note

This package is an integration layer. It does not implement a Bitcoin node, a
pool server, or a mining algorithm. Changes that increase the external
dependency surface (new network connections, new configuration fields, new
system calls) warrant extra scrutiny.
