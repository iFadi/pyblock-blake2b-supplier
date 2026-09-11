import { FileHelper, YAML, z } from '@start9labs/start-sdk'
import * as fs from 'node:fs/promises'
import { sdk } from '../sdk.js'
import { bitcoindRpcPort, configSubpath } from '../utils.js'

/**
 * On-disk shape of `config.yaml`.
 *
 * Every field is lenient (`.catch(...)`): the file model has to be able to read
 * a partially written or hand-edited file so `main` can repair it, and so the
 * Config action can prefill from it. Strict validation of user input happens in
 * the action's execution function, and again in `supplier/config.py` before the
 * daemon uses any of it.
 */
export const shape = z.object({
  'payout-address': z.string().catch(''),
  'supplier-name': z.string().nullable().catch(null),
  // Resolved from the bitcoind dependency's bridge address by main.ts. Never
  // user-supplied: this package supports a local node only.
  'rpc-host': z.string().catch(''),
  'rpc-port': z.number().int().min(1).max(65535).catch(bitcoindRpcPort),
  'rpc-user': z.string().catch(''),
  'rpc-password': z.string().catch(''),
  network: z.enum(['tor', 'clearnet']).catch('tor'),
})

export type Config = z.infer<typeof shape>

export const configFile = FileHelper.yaml(
  { base: sdk.volumes.main, subpath: configSubpath },
  shape,
)

/** An all-defaults config, used as the base when no file exists yet. */
export const emptyConfig = (): Config => shape.parse({})

/**
 * Merge `patch` into the on-disk config and replace the file atomically.
 *
 * The write goes to a sibling temp file which is then `rename(2)`d over the
 * target, so a reader — the Python daemon, or its health check — only ever
 * observes the complete old file or the complete new one, never a truncated
 * one. `FileHelper.write`/`merge` overwrite in place, which does not give that
 * guarantee, so they are deliberately not used for the write path.
 *
 * The file carries the node's RPC password, so it is created 0600.
 */
export const mergeConfig = async (patch: Partial<Config>): Promise<Config> => {
  const existing = (await configFile.read().once()) ?? emptyConfig()
  const next = shape.parse({ ...existing, ...patch })

  const path = sdk.volumes.main.subpath(configSubpath)
  const tmp = `${path}.tmp`

  await fs.mkdir(sdk.volumes.main.path, { recursive: true })
  await fs.writeFile(tmp, YAML.stringify(next), { mode: 0o600 })
  await fs.rename(tmp, path)

  return next
}
