import { T } from '@start9labs/start-sdk'
import { sdk } from './sdk.js'

/**
 * Mountpoint of the `main` volume inside the supplier subcontainer. The Python
 * process reads its config and writes its health/PID state here.
 */
export const dataMountpoint = '/root/start9'

/** Path of the config file, relative to the root of the `main` volume. */
export const configSubpath = 'config.yaml'

/**
 * bitcoind's host contract. `rpc` is the host id the bitcoind package binds its
 * JSON-RPC listener on, and 8332 is the container-side port of that binding.
 * These are the dependency's published identifiers, not an address: the address
 * itself is always resolved at runtime by {@link bitcoindRpcBridge}.
 */
export const bitcoindRpcHostId = 'rpc'
export const bitcoindRpcPort = 8332

/** A resolved `host` / `port` pair, as the Python supplier consumes it. */
export type RpcEndpoint = {
  host: string
  port: number
}

/**
 * Split a `host:port` address into its parts, accepting the bracketed IPv6 form
 * (`[::1]:8332`) as well as IPv4/hostnames. Returns `null` when the address is
 * not a well-formed host/port pair, so callers never write a half-parsed
 * endpoint into the config.
 */
export const parseHostPort = (address: string): RpcEndpoint | null => {
  const match = /^(?:\[([^\]]+)\]|([^:]+)):(\d+)$/.exec(address.trim())
  if (!match) return null

  const host = match[1] ?? match[2]
  const port = Number(match[3])
  if (!host || !Number.isInteger(port) || port < 1 || port > 65535) return null

  return { host, port }
}

/**
 * bitcoind's JSON-RPC endpoint over the LXC bridge (`10.0.3.1:<port>`).
 *
 * Resolved through `getBridgeAddress` rather than rebuilt from
 * `net.assignedPort` / `net.assignedSslPort`: which of those is populated is a
 * property of how bitcoind bound the port, not something this package may
 * assume. Read with `.const()`, so `main` re-fires — and the supplier restarts
 * against the new address — whenever bitcoind is installed, uninstalled, or
 * changes its binding, and never on a plain bitcoind update.
 *
 * Resolves `null` while bitcoind is absent. There is deliberately no fallback
 * address: this package supplies templates from a local node only.
 */
export const bitcoindRpcBridge = async (
  effects: T.Effects,
): Promise<RpcEndpoint | null> => {
  const address = await sdk.host
    .getBridgeAddress(effects, {
      packageId: 'bitcoind',
      hostId: bitcoindRpcHostId,
      internalPort: bitcoindRpcPort,
      ssl: false,
    })
    .const()

  return address === null ? null : parseHostPort(address)
}
