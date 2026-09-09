import { VersionGraph } from '@start9labs/start-sdk'
import { current } from './current.js'

export const versions = VersionGraph.of({ current, other: [] })
