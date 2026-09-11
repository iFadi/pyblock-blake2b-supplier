import { i18n } from '../i18n/index.js'
import { configFile } from '../fileModels/config.yaml.js'
import { sdk } from '../sdk.js'
import { supplierDashboardResult } from './supplier-dashboard.js'

/**
 * User-invoked action that shows the operator's PyBLOCK supplier status page
 * URL as a copyable string. It is not a Property: StartOS renders the result in
 * a modal only when the action is run, and whether the string is clickable is
 * up to the client, so the UI text tells the operator to copy it.
 *
 * Derivation, validation, and failure handling live in
 * `supplier-dashboard.ts` so they can be unit tested without the SDK runtime.
 */
export const dashboardUrl = sdk.Action.withoutInput(
  'dashboard-url',

  async ({ effects }) => ({
    name: i18n('Supplier Dashboard'),
    description: i18n(
      'Show the URL of your personal PyBLOCK supplier status page, derived from your payout address — no manual SHA256 calculation needed.',
    ),
    warning: null,
    allowedStatuses: 'any',
    group: null,
    visibility: 'enabled',
  }),

  async ({ effects }) => supplierDashboardResult(() => configFile.read().once()),
)
