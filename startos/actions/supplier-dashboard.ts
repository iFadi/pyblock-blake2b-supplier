import { createHash } from 'node:crypto'
import type { T } from '@start9labs/start-sdk'
import { i18n } from '../i18n/index.js'
import { payoutAddressRegex } from '../payout-address.js'

/**
 * Public PyBLOCK supplier status page. The `s` query parameter selects the
 * supplier; see `instructions.md` → "Supplier Dashboard".
 */
export const dashboardBaseUrl = 'https://b.pyblock.xyz:8443/supplier.php'

/**
 * The subset of the stored config the dashboard derivation is allowed to see.
 * Declared here, like `StoredConfigForForm`, so this module never imports the
 * SDK-backed file model and stays testable with plain `node --test`.
 */
export interface StoredPayoutConfig {
  'payout-address': string
}

/**
 * Reads the stored config, resolving `null` when no file has been written yet.
 * Rejects when the file exists but cannot be read or parsed (I/O failure,
 * malformed YAML). The action supplies `configFile.read().once()`.
 */
export type StoredConfigReader = () => Promise<StoredPayoutConfig | null>

/** The only result version the SDK accepts from an action's execution function. */
export type DashboardActionResult = Extract<T.ActionResult, { version: '1' }>

/**
 * PyBLOCK identifies a supplier by the first 16 hex characters of
 * `sha256(payout_address)`. Callers must validate the address first: hashing
 * an arbitrary string produces a syntactically fine but meaningless URL.
 */
export const supplierSid = (payoutAddress: string): string =>
  createHash('sha256').update(payoutAddress, 'utf8').digest('hex').slice(0, 16)

export const supplierDashboardUrl = (payoutAddress: string): string =>
  `${dashboardBaseUrl}?s=${supplierSid(payoutAddress)}`

/** Fixed-text audit line: never append the error, the path, or any config value. */
export const configUnreadableAuditMessage =
  'Supplier Dashboard: config.yaml could not be read or parsed; no URL derived'

const title = i18n('Supplier Dashboard')

const withoutUrl = (message: string): DashboardActionResult => ({
  version: '1',
  title,
  message,
  result: null,
})

/**
 * Build the Supplier Dashboard action result from the stored configuration.
 *
 * The URL is derived only from a payout address that passes the same
 * `payoutAddressRegex` the Configure action enforces, so a missing, blank,
 * hand-edited, or otherwise invalid value yields an operator-facing message
 * instead of a bogus link. Failures while reading the file are reported
 * generically: parser errors can quote the offending line, and the file holds
 * the node's RPC password, so no error text reaches the UI or the logs.
 */
export const supplierDashboardResult = async (
  readConfig: StoredConfigReader,
): Promise<DashboardActionResult> => {
  let stored: StoredPayoutConfig | null
  try {
    stored = await readConfig()
  } catch {
    console.warn(configUnreadableAuditMessage)
    return withoutUrl(
      i18n(
        'The stored configuration could not be read. Open Configure and save it again, then retry.',
      ),
    )
  }

  const raw = stored?.['payout-address']
  const payoutAddress = typeof raw === 'string' ? raw.trim() : ''

  if (!payoutAddress) {
    return withoutUrl(
      i18n('Not configured yet. Open Configure and save a payout address first.'),
    )
  }

  if (!payoutAddressRegex.test(payoutAddress)) {
    return withoutUrl(
      i18n(
        'The stored payout address is not a valid BLAKE2b-chain address, so no dashboard URL can be derived. Open Configure and save a valid address.',
      ),
    )
  }

  return {
    version: '1',
    title,
    message: i18n(
      'Copy this URL into a browser to view your supplier status page. It is derived from your payout address.',
    ),
    result: {
      type: 'single',
      value: supplierDashboardUrl(payoutAddress),
      copyable: true,
      qr: false,
      masked: false,
    },
  }
}
