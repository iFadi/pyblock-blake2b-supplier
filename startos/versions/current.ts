import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:5',
  releaseNotes: [
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
