# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |

## Reporting a vulnerability

Please **do not** file a public GitHub issue for security vulnerabilities.

Use [GitHub private vulnerability reporting](https://github.com/iFadi/pyblock-blake2b-supplier/security/advisories/new).
A response will be sent within 5 business days. If private reporting is
temporarily unavailable, open a GitHub issue with `[SECURITY CONTACT]` in the
title and no vulnerability details; the maintainer will establish a private
channel.

Include in your report:
- Description of the vulnerability and potential impact
- Steps to reproduce or proof-of-concept (privately, not in the public issue)
- StartOS and package version affected
- Whether you have already developed a fix

## Scope

The following are in scope:

- The Python supplier code (`supplier/`)
- The StartOS TypeScript integration (`startos/`)
- The container entrypoint and Tor configuration (`scripts/`, `docker/`)
- Any credential, key, or address disclosure path

The following are out of scope:

- Vulnerabilities in the PyBLOCK pool operator infrastructure
- Vulnerabilities in Bitcoin Knots or StartOS itself
- Theoretical issues with no realistic attack path on a standard StartOS device

## Security design notes

See the Security section of [README.md](README.md) for the threat model and
key design decisions (no inbound ports, Tor-or-fail, credential isolation).

The masked RPC password is never returned in Configure form defaults. A blank
subsequent submission retains the exact stored value, while a nonblank value
rotates it without trimming or normalization. Logs record only whether the
password was kept or updated, never its value or length.
