# Updating

## Determining the upstream version

This package wraps a custom Python supplier, not an upstream Docker image.
The package ExVer is set in `startos/versions/current.ts` → the `version` field.
The Docker image is built from the local `Dockerfile` (`dockerBuild: {}`).

## Applying the bump

1. Increment the package ExVer in `startos/versions/current.ts`. For a
   packaging-only change, increment the revision after the colon. For example,
   revision 11 (the CI staging fix) set the ExVer to `1.0.0:11`, and revision
   12 (the Supplier Dashboard action) sets it to `1.0.0:12`.
2. Put the newest release notes first in the same file.
3. Update every release surface that names the candidate to the same version:
   the `release_tag` dispatch defaults and `EXPECTED_VERSION` in
   `.github/workflows/release-stage.yml` and `release-promote.yml`, the
   `--title` in `release-promote.yml`, and the expectations in
   `.github/scripts/validate-release-tag.test.js` and
   `validate-release-workflow.test.js`. `npm test` fails until all of them
   agree with `current.ts`. Add the new revision to `CHANGELOG.md`; leave
   earlier entries as history.
4. Run `npm ci`, `npm audit --audit-level=high`, `npm run check`, `npm test`,
   `npm run build`, and the Python test suite.
5. Build each supported architecture and inspect the resulting `.s9pk` before
   publishing it.
6. Update the dependency locks using the procedure in `CONTRIBUTING.md`, then
   run the lock validation tests. Never update a version without its artifact
   digest or hash evidence.
