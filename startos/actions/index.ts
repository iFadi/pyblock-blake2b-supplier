import { sdk } from '../sdk.js'
import { config } from './config.js'

export const actions = sdk.Actions.of().addAction(config)
