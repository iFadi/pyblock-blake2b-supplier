# Updating

## Determining the upstream version

This package wraps a custom Python supplier, not an upstream Docker image.
The package ExVer is set in `startos/versions/current.ts` → the `version` field.
The Docker image is built from the local `Dockerfile` (`dockerBuild: {}`).

## Applying the bump

1. Increment the package ExVer in `startos/versions/current.ts`. For a
   packaging-only change, increment the revision after the colon. This
   revision 10 deterministic-build candidate sets the ExVer to `1.0.0:10`.
2. Put the newest release notes first in the same file.
3. Run `npm ci`, `npm audit --audit-level=high`, `npm run check`, `npm test`,
   `npm run build`, and the Python test suite.
4. Build each supported architecture and inspect the resulting `.s9pk` before
   publishing it.
5. Update the dependency locks using the procedure in `CONTRIBUTING.md`, then
   run the lock validation tests. Never update a version without its artifact
   digest or hash evidence.
