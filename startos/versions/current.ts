import { VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '1.0.0:14',
  releaseNotes: [
    'Bound each Tor readiness attempt to 10 seconds inside the existing 180-second readiness window, preventing a live supplier from crossing the 60-second health staleness threshold while a target is unavailable.',
    'Refresh failing health before blocking Tor probes and preserve the precise dependency failure across retries.',
    'Distinguish a local Tor failure from a PyBLOCK publish target that Tor cannot reach.',
    'Suppress duplicate application progress logs while continuing to refresh the health record on every attempt.',
    'Preserve fail-closed Tor behavior; no automatic clearnet fallback was added.',
    'Re-pin the runtime image Tor package to a currently published Alpine build after the previously locked version was superseded and removed from the mirror.',
  ].join('\n'),
  migrations: {
    up: async () => {},
    down: async () => {},
  },
})
