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

## Scope note

This package is an integration layer. It does not implement a Bitcoin node, a
pool server, or a mining algorithm. Changes that increase the external
dependency surface (new network connections, new configuration fields, new
system calls) warrant extra scrutiny.
