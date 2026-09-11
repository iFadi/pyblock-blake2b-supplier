import { sdk } from '../sdk.js'
import { config } from './config.js'
import { dashboardUrl } from './dashboard-url.js'

export const actions = sdk.Actions.of().addAction(config).addAction(dashboardUrl)
