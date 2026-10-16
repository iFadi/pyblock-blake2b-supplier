import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:15',
  releaseNotes: [
    'Migrated from Start SDK 2.0.9 to 3.0.6 (StartOS 0.4.0.2 baseline): the bitcoind dependency is now declared with the SDK v3 Dependency/Dependencies builder instead of the removed manifest dependency literal and setupDependencies pattern.',
    'Added the required `launchable` field to the Supplier Dashboard action result, as SDK v3 now requires every field on an action result value.',
    'Updated the health-check SubContainer call to the SDK v3 named-options exec signature; behavior and the 30-second timeout are unchanged.',
    'Dropped the redundant typescript, @types/node, and @vercel/ncc devDependencies now supplied directly by the SDK, and the eslint/js-yaml bundled-advisory patch workaround the SDK no longer needs.',
    'No functional or Tor/clearnet behavior change for operators; this is a packaging and toolchain migration only.',
  ].join('\n'),
  migrations: {
    up: async () => {},
    down: async () => {},
  },
})
