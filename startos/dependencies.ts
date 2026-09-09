import { i18n } from './i18n/index.js'
import { sdk } from './sdk.js'

/**
 * bitcoind is a hard requirement, not a convenience.
 *
 * The supplier's only job is to relay `getblocktemplate` output from a
 * BLAKE2b-capable Bitcoin Knots node on this device. There is no remote-node
 * mode: an operator-supplied RPC URL would put a third party between the
 * supplier and the templates it signs its payout address into, so the RPC
 * endpoint is always resolved from this dependency's bridge binding (see
 * `bitcoindRpcBridge` in utils.ts).
 *
 * The StartOS package uses a flavor/downstream ExVer that does not reliably
 * track the upstream Knots binary version. Therefore the package-level range
 * is intentionally broad; runtime health checks enforce the capabilities that
 * matter here: BLAKE2b getblocktemplate support, sync state, and PyBLOCK
 * template acceptance.
 *
 * `healthChecks` is deliberately empty: the BLAKE2b Knots build is a fork, and
 * naming health check ids it may not export would leave the requirement
 * permanently unsatisfiable. Node sync and `getblocktemplate` support are
 * checked directly by this package's own health check instead.
 */
export const setDependencies = sdk.setupDependencies(async ({ effects }) => ({
  bitcoind: {
    kind: 'running' as const,
    versionRange: '*',
    healthChecks: [],
  },
}))
