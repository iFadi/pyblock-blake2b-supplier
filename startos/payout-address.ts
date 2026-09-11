/**
 * Payout address grammar accepted by PyBLOCK: bech32 (`bc1q…`), taproot
 * (`bc1p…`), P2PKH (`1…`) and P2SH (`3…`). Kept in sync with the identical
 * expression in `supplier/config.py`, which validates the file again at load
 * time — the daemon must never trust that this file was written by the action.
 *
 * This module deliberately has no StartOS SDK imports so that every consumer —
 * the Configure form pattern, the Configure execution check, and the Supplier
 * Dashboard derivation — shares one expression that plain unit tests can also
 * exercise.
 */
export const payoutAddressPattern =
  '^(bc1[qp][a-z0-9]{6,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$'

export const payoutAddressRegex = new RegExp(payoutAddressPattern)
