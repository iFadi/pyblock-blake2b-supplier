import { T } from '@start9labs/start-sdk'
import { configFile, mergeConfig } from './fileModels/config.yaml.js'
import { i18n } from './i18n/index.js'
import { sdk } from './sdk.js'
import { bitcoindRpcBridge, dataMountpoint } from './utils.js'

/**
 * Emits one JSON object — `{"result": ..., "message": ...}` — describing the
 * supplier's current health, and always exits 0. The evaluation (staleness,
 * liveness of the daemon process, and the state the loop last recorded) lives
 * in `supplier/healthcheck.py`, where it is unit tested.
 */
const HEALTH_CHECK_CMD = ['/usr/local/bin/health-check.sh']

/** Health results the script may report, mapped straight onto StartOS results. */
const HEALTH_RESULTS = [
  'success',
  'failure',
  'loading',
  'starting',
] as const satisfies ReadonlyArray<T.NamedHealthCheckResult['result']>

type HealthResult = (typeof HEALTH_RESULTS)[number]

const isHealthResult = (value: unknown): value is HealthResult =>
  HEALTH_RESULTS.includes(value as HealthResult)

export const main = sdk.setupMain(async ({ effects }) => {
  console.info(i18n('Starting PyBLOCK BLAKE2b Supplier'))

  // bitcoind's JSON-RPC endpoint over the LXC bridge, written into config.yaml
  // before the daemon reads it. Resolved reactively: the address changes only
  // on bitcoind install / uninstall / port change, so main re-fires and the
  // supplier restarts against the new address on exactly those events.
  //
  // While bitcoind is absent this is null and the RPC endpoint is left as it
  // was; bitcoind is a required dependency, so the service is not expected to
  // run in that state, and the supplier reports node_unavailable if it does.
  const bitcoind = await bitcoindRpcBridge(effects)
  if (bitcoind) {
    await mergeConfig({
      'rpc-host': bitcoind.host,
      'rpc-port': bitcoind.port,
    })
    console.info(
      `Resolved bitcoind RPC bridge address: ${bitcoind.host}:${bitcoind.port}`,
    )
  } else {
    console.warn(
      'bitcoind RPC bridge address is unresolved — the supplier will report node_unavailable until the node is installed and running',
    )
  }

  // Read once: Configure is only available while the service is stopped, so
  // the next start always sees the newly saved transport selection.
  const network = (await configFile.read((c) => c.network).once()) ?? 'tor'
  console.info(`Network mode: ${network}`)

  const mounts = sdk.Mounts.of().mountVolume({
    volumeId: 'main',
    subpath: null,
    mountpoint: dataMountpoint,
    readonly: false,
  })

  const sub = sdk.SubContainer.of(
    effects,
    { imageId: 'main' },
    mounts,
    'pyblock-sub',
  )

  return sdk.Daemons.of(effects).addDaemon('primary', {
    subcontainer: sub,
    exec: { command: ['/usr/local/bin/docker_entrypoint.sh'] },
    ready: {
      display: i18n('PyBLOCK Publisher'),
      fn: async () => {
        const res = await sub.exec(HEALTH_CHECK_CMD, {}, 30_000)
        const stdout = res.stdout.toString().trim()

        let parsed: unknown
        try {
          parsed = JSON.parse(stdout)
        } catch {
          // No parseable output means the health reporter itself could not
          // run — treat that as unhealthy rather than as "not yet reporting".
          return {
            result: 'failure',
            message:
              stdout ||
              res.stderr.toString().trim() ||
              i18n(
                'Supplier health state is unavailable — the service may still be starting',
              ),
          }
        }

        const { result, message } = parsed as {
          result?: unknown
          message?: unknown
        }

        if (!isHealthResult(result)) {
          return {
            result: 'failure',
            message: i18n(
              'Supplier health state is unavailable — the service may still be starting',
            ),
          }
        }

        const text =
          typeof message === 'string' && message
            ? message
            : i18n('Template accepted — active on the PyBLOCK Carousel')

        // `loading` and `failure` require a message; the others accept one.
        return { result, message: text } as T.NamedHealthCheckResult
      },
    },
    requires: [],
  })
})
