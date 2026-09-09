export { actions } from './actions/index.js'
export { createBackup } from './backups.js'
export { setDependencies } from './dependencies.js'
export { init, uninit } from './init/index.js'
export { main } from './main.js'
import { buildManifest } from '@start9labs/start-sdk'
import { manifest as sdkManifest } from './manifest/index.js'
import { versions } from './versions/index.js'
export const manifest = buildManifest(versions, sdkManifest)
