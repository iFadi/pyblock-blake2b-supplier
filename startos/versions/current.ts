import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:11',
  releaseNotes: [
    'Pin the multi-architecture Python base image, the complete added Alpine package set, and all Python dependencies to immutable versions and hashes.',
    'Keep Tor at the StartOS-tested 0.4.9.11-r0 build and fail closed if any locked dependency artifact changes or becomes unavailable.',
    'Bound each Tor-routed HTTP publication to a 30-second end-to-end deadline.',
    'Refuse to publish while the Bitcoin node block tip trails its known header tip, even when initial block download is false.',
    'Fail closed when node block, header, or initial-block-download synchronization data is missing or malformed, and resume automatically after synchronization.',
    'Restore the Docker, Buildx, QEMU, and containerd prerequisites omitted from the failed rev7 pre-release attempt.',
    'Add an ephemeral-key GitHub Actions dry run that exercises both release architectures without publishing.',
    'Keep rev6 and rev7 as immutable failed pre-release attempts; neither produced a GitHub Release.',
    'Add GitHub Actions package builds and signed GitHub Release automation without changing runtime behavior.',
    'Keep the stored RPC password when a later Configure save leaves the masked field blank.',
    'Require an RPC password on the first Configure save and allow explicit password rotation thereafter.',
    'Avoid returning RPC passwords to the Configure form or disclosing configuration identifiers in logs.',
    'Add direct automated coverage for password initialization, retention, rotation, and non-disclosure.',
  ].join('\n'),
  migrations: {
    up: async () => {},
    down: async () => {},
  },
})
