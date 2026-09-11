import { createHash } from 'node:crypto'
import { i18n } from '../i18n/index.js'
import { configFile } from '../fileModels/config.yaml.js'
import { sdk } from '../sdk.js'

const NOT_CONFIGURED = i18n('Not configured — save a payout address first.')

function supplierSid(payoutAddress: string): string {
  return createHash('sha256').update(payoutAddress).digest('hex').slice(0, 16)
}

export const dashboardUrl = sdk.Action.withoutInput(
  'dashboard-url',

  async ({ effects }) => ({
    name: i18n('Supplier Dashboard'),
    description: i18n(
      'Open your personal supplier dashboard on the PyBLOCK network. The URL is derived from your payout address — no manual SHA256 calculation needed.',
    ),
    warning: null,
    allowedStatuses: 'any',
    group: null,
    visibility: 'enabled',
  }),

  async ({ effects }) => {
    const cfg = await configFile.read().once()
    const payoutAddress = cfg?.['payout-address']?.trim() ?? ''

    if (!payoutAddress) {
      return {
        version: '1' as const,
        title: i18n('Supplier Dashboard'),
        message: NOT_CONFIGURED,
        result: null,
      }
    }

    const sid = supplierSid(payoutAddress)
    const url = `https://b.pyblock.xyz:8443/supplier.php?sid=${sid}`

    return {
      version: '1' as const,
      title: i18n('Supplier Dashboard'),
      message: null,
      result: {
        type: 'single' as const,
        value: url,
        copyable: true,
        qr: false,
        masked: false,
      },
    }
  },
)
