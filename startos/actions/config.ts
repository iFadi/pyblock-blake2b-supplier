import { i18n } from '../i18n/index.js'
import {
  configFile,
  mergeConfig,
  payoutAddressPattern,
  payoutAddressRegex,
} from '../fileModels/config.yaml.js'
import { sdk } from '../sdk.js'
import { bitcoindRpcBridge, bitcoindRpcPort } from '../utils.js'
import {
  buildConfigFormDefaults,
  MissingInitialRpcPasswordError,
  resolveRpcPassword,
  rpcPasswordAuditMessage,
} from './rpc-password.js'

const { InputSpec, Value } = sdk

/**
 * Placeholder shown for RPC Host / RPC Port while bitcoind is not installed or
 * not yet running. Both fields are display-only — see the note on `rpc-host`.
 */
const unresolved = i18n('Waiting for the local Bitcoin node')

export const inputSpec = InputSpec.of({
  'payout-address': Value.text({
    name: i18n('Payout Address'),
    description: i18n(
      'The BLAKE2b-chain address that receives your supplier coinbase split.',
    ),
    required: true,
    default: null,
    patterns: [
      {
        regex: payoutAddressPattern,
        description: i18n('Must begin with bc1q, bc1p, 1 or 3.'),
      },
    ],
  }),
  'supplier-name': Value.text({
    name: i18n('Supplier Name'),
    description: i18n(
      'Display name on the PyBLOCK suppliers page. Leave blank to be listed by node user agent and payout address.',
    ),
    required: false,
    default: null,
  }),
  // RPC Host and RPC Port are shown so the operator can see which node the
  // supplier talks to, but are not editable: the address is resolved from the
  // bitcoind dependency's bridge binding in main.ts on every start. There is no
  // remote-node mode, so there is nothing here for a user to set.
  'rpc-host': Value.dynamicText(async ({ effects }) => {
    const bitcoind = await bitcoindRpcBridge(effects)
    return {
      name: i18n('RPC Host'),
      description: i18n(
        'Resolved automatically from the local Bitcoin node dependency. This package supplies templates from a local node only.',
      ),
      required: false,
      default: bitcoind?.host ?? null,
      placeholder: unresolved,
      disabled: i18n(
        'Resolved automatically from the local Bitcoin node dependency. This package supplies templates from a local node only.',
      ),
    }
  }),
  'rpc-port': Value.dynamicNumber(async ({ effects }) => {
    const bitcoind = await bitcoindRpcBridge(effects)
    return {
      name: i18n('RPC Port'),
      description: i18n(
        'Resolved automatically from the local Bitcoin node dependency. This package supplies templates from a local node only.',
      ),
      required: false,
      default: bitcoind?.port ?? bitcoindRpcPort,
      integer: true,
      min: 1,
      max: 65535,
      disabled: i18n(
        'Resolved automatically from the local Bitcoin node dependency. This package supplies templates from a local node only.',
      ),
    }
  }),
  'rpc-user': Value.text({
    name: i18n('RPC Username'),
    description: i18n(
      'The rpcuser configured on your Bitcoin Knots BLAKE2b node.',
    ),
    required: true,
    default: null,
  }),
  'rpc-password': Value.text({
    name: i18n('RPC Password'),
    description: i18n(
      'The rpcpassword configured on your Bitcoin Knots BLAKE2b node. It is never displayed. Leave blank to keep the stored password, or enter a value to set or replace it.',
    ),
    required: false,
    default: null,
    masked: true,
  }),
  network: Value.select({
    name: i18n('Network Mode'),
    description: i18n(
      'Transport used to reach PyBLOCK. Tor keeps your IP address private, and the supplier fails rather than silently falling back to clearnet.',
    ),
    values: {
      tor: i18n('Tor (recommended)'),
      clearnet: i18n('Clearnet'),
    },
    default: 'tor',
  }),
})

export const config = sdk.Action.withInput(
  // id
  'config',

  // metadata
  async ({ effects }) => ({
    name: i18n('Configure'),
    description: i18n(
      'Set the payout address, node RPC credentials, and PyBLOCK transport',
    ),
    warning: null,
    // First-run configuration is a critical task and must be completed while
    // the service is stopped. Later credential rotation follows the same safe
    // stop -> configure -> start sequence.
    allowedStatuses: 'only-stopped',
    group: null,
    visibility: 'enabled',
  }),

  // form input specification
  inputSpec,

  // pre-fill the form from the stored config
  async ({ effects }) => {
    const existing = await configFile.read().once()
    if (!existing) return null

    // The helper deliberately omits rpc-password. A blank submission is
    // resolved against the stored value only during execution.
    return buildConfigFormDefaults(existing)
  },

  // execution
  async ({ effects, input }) => {
    const payoutAddress = (input['payout-address'] ?? '').trim()
    if (!payoutAddress) throw new Error(i18n('Payout Address is required.'))
    if (!payoutAddressRegex.test(payoutAddress)) {
      throw new Error(
        i18n(
          'Payout Address is not a valid BLAKE2b-chain address. It must begin with bc1q, bc1p, 1 or 3.',
        ),
      )
    }

    const rpcUser = (input['rpc-user'] ?? '').trim()
    if (!rpcUser) throw new Error(i18n('RPC Username is required.'))

    const existing = await configFile.read().once()
    let rpcPassword
    try {
      rpcPassword = resolveRpcPassword(
        input['rpc-password'],
        existing?.['rpc-password'],
      )
    } catch (error) {
      if (!(error instanceof MissingInitialRpcPasswordError)) throw error
      throw new Error(
        i18n('RPC Password is required the first time configuration is saved.'),
      )
    }

    const supplierName = (input['supplier-name'] ?? '').trim() || null

    // RPC host/port are display-only in the form; main.ts overwrites them from
    // the bitcoind bridge address on every start. Persist whatever is already
    // known so the file is complete in the meantime.
    await mergeConfig({
      'payout-address': payoutAddress,
      'supplier-name': supplierName,
      'rpc-user': rpcUser,
      'rpc-password': rpcPassword.value,
      network: input.network,
    })

    // Never log configuration values, the password, or the password length.
    console.info(rpcPasswordAuditMessage(rpcPassword.status))

    return {
      version: '1' as const,
      title: i18n('Configuration Saved'),
      message: i18n(
        'The new configuration will be used the next time the service starts.',
      ),
      result: null,
    }
  },
)
