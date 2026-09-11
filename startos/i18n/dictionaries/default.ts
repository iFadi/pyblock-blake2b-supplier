export const DEFAULT_LANG = 'en_US'

/**
 * Every user-facing string in the package, in display order. `setupI18n` keys
 * translations by numeric index, so the index of a string here is its
 * translation key — derive both structures from this one list rather than
 * maintaining the indices by hand.
 *
 * Append new strings at the end. Reordering or removing an entry renumbers the
 * ones after it and would silently remap existing translations.
 */
const keys = [
  'Starting PyBLOCK BLAKE2b Supplier',
  'PyBLOCK Publisher',
  'Template accepted — active on the PyBLOCK Carousel',
  'Supplier health state is unavailable — the service may still be starting',
  'Configure',
  'Set the payout address, node RPC credentials, and PyBLOCK transport',
  'Payout Address',
  'The BLAKE2b-chain address that receives your supplier coinbase split.',
  'Must begin with bc1q, bc1p, 1 or 3.',
  'Supplier Name',
  'Display name on the PyBLOCK suppliers page. Leave blank to be listed by node user agent and payout address.',
  'RPC Host',
  'Resolved automatically from the local Bitcoin node dependency. This package supplies templates from a local node only.',
  'RPC Port',
  'RPC Username',
  'The rpcuser configured on your Bitcoin Knots BLAKE2b node.',
  'RPC Password',
  'The rpcpassword configured on your Bitcoin Knots BLAKE2b node. Enter it on every save — it is never displayed back to you.',
  'Network Mode',
  'Transport used to reach PyBLOCK. Tor keeps your IP address private, and the supplier fails rather than silently falling back to clearnet.',
  'Tor (recommended)',
  'Clearnet',
  'Configuration Saved',
  'The supplier was restarted with the new configuration.',
  'The new configuration will be used the next time the service starts.',
  'Payout Address is required.',
  'Payout Address is not a valid BLAKE2b-chain address. It must begin with bc1q, bc1p, 1 or 3.',
  'RPC Username is required.',
  'RPC Password is required.',
  'Waiting for the local Bitcoin node',
  'Configure the BLAKE2b payout address and dedicated Bitcoin Knots RPC credentials before starting the supplier.',
  'The rpcpassword configured on your Bitcoin Knots BLAKE2b node. It is never displayed. Leave blank to keep the stored password, or enter a value to set or replace it.',
  'RPC Password is required the first time configuration is saved.',
  'Supplier Dashboard',
  'Open your personal supplier dashboard on the PyBLOCK network. The URL is derived from your payout address — no manual SHA256 calculation needed.',
  'Not configured — save a payout address first.',
] as const

type Key = (typeof keys)[number]

export const defaultDict = Object.fromEntries(
  keys.map((key, index) => [key, index]),
) as Record<Key, number>

export const translations = {
  en_US: Object.fromEntries(
    keys.map((key, index) => [index, key]),
  ) as Record<number, string>,
}
