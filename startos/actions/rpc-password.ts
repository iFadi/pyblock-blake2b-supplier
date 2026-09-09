export type RpcPasswordStatus = 'kept' | 'updated'

export interface ResolvedRpcPassword {
  value: string
  status: RpcPasswordStatus
}

export class MissingInitialRpcPasswordError extends Error {
  constructor() {
    super('RPC Password is required the first time configuration is saved.')
    this.name = 'MissingInitialRpcPasswordError'
  }
}

export interface StoredConfigForForm {
  'payout-address': string
  'supplier-name': string | null
  'rpc-host': string
  'rpc-port': number
  'rpc-user': string
  'rpc-password': string
  network: 'tor' | 'clearnet'
}

/** Build browser-visible defaults without ever returning the stored secret. */
export const buildConfigFormDefaults = (existing: StoredConfigForForm) => ({
  'payout-address': existing['payout-address'] || undefined,
  'supplier-name': existing['supplier-name'],
  'rpc-host': existing['rpc-host'] || null,
  'rpc-port': existing['rpc-port'],
  'rpc-user': existing['rpc-user'] || undefined,
  network: existing.network,
})

/**
 * Resolve a password submitted by the masked Configure field.
 *
 * An exactly empty submission means "keep the stored password". Whitespace is
 * credential data and is therefore neither trimmed nor otherwise transformed.
 */
export const resolveRpcPassword = (
  submitted: string | null | undefined,
  stored: string | null | undefined,
): ResolvedRpcPassword => {
  const candidate = submitted ?? ''

  if (candidate !== '') {
    return { value: candidate, status: 'updated' }
  }

  if (stored !== null && stored !== undefined && stored !== '') {
    return { value: stored, status: 'kept' }
  }

  throw new MissingInitialRpcPasswordError()
}

/** A deliberately non-sensitive audit message: never add values or lengths. */
export const rpcPasswordAuditMessage = (status: RpcPasswordStatus): string =>
  `Configuration saved; RPC password ${status}`
