import { actions } from '../actions/index.js'
import { config } from '../actions/config.js'
import { restoreInit } from '../backups.js'
import { setDependencies } from '../dependencies.js'
import { configFile } from '../fileModels/config.yaml.js'
import { i18n } from '../i18n/index.js'
import { sdk } from '../sdk.js'
import { versions } from '../versions/index.js'

/**
 * Require the operator to supply the payout address and dedicated node RPC
 * credentials before StartOS allows the service to start. The task is
 * idempotent and is automatically completed when its Configure action runs.
 */
export const requireConfiguration = sdk.setupOnInit(async effects => {
  const existing = await configFile.read().const(effects)
  const configured = Boolean(
    existing?.['payout-address'] &&
      existing?.['rpc-user'] &&
      existing?.['rpc-password'],
  )

  if (!configured) {
    await sdk.action.createOwnTask(effects, config, 'critical', {
      reason: i18n(
        'Configure the BLAKE2b payout address and dedicated Bitcoin Knots RPC credentials before starting the supplier.',
      ),
    })
  }
})

export const init = sdk.setupInit(
  restoreInit,
  versions,
  setDependencies,
  actions,
  requireConfiguration,
)

// Required by the StartOS 0.4 lifecycle ABI for update, uninstall, and
// shutdown. Omitting this export makes every update fail before replacement.
export const uninit = sdk.setupUninit(versions)
