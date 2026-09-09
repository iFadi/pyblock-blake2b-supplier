import { StartSdk } from '@start9labs/start-sdk'
import { manifest } from './manifest/index.js'

export const sdk = StartSdk.of().withManifest(manifest).build(true)
