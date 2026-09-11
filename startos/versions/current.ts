import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:12',
  releaseNotes: [
    'Add a Supplier Dashboard action that shows your PyBLOCK supplier status page URL as a copyable string, derived from the configured payout address. No manual SHA256 calculation needed.',
  ].join('\n'),
  migrations: {
    up: async () => {},
    down: async () => {},
  },
})
