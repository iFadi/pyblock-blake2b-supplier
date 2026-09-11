import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:12',
  releaseNotes: [
    'Add Supplier Dashboard action: displays the operator\'s personal PyBLOCK dashboard URL, derived automatically from the configured payout address. No manual SHA256 calculation needed.',
  ].join('\n'),
  migrations: {
    up: async () => {},
    down: async () => {},
  },
})
