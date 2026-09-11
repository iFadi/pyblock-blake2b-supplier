import assert from 'node:assert/strict'
import test from 'node:test'
import {
  configUnreadableAuditMessage,
  dashboardBaseUrl,
  supplierDashboardResult,
  supplierDashboardUrl,
  supplierSid,
  type StoredConfigReader,
} from '../startos/actions/supplier-dashboard.js'

// Expected values were computed independently with `printf '%s' <addr> | sha256sum`.
const bech32Address = 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4'
const bech32Sid = '6cd42dab0217b54f'
const p2pkhAddress = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
const p2pkhSid = '31a9d2e8a70a091d'

const rpcPassword = 'rpc-credential-that-must-not-appear'

/** A reader that resolves a full on-disk config, including the RPC secret. */
const storedConfig = (payoutAddress: string): StoredConfigReader => {
  const stored = {
    'payout-address': payoutAddress,
    'supplier-name': null,
    'rpc-host': '10.0.3.1',
    'rpc-port': 8332,
    'rpc-user': 'supplier',
    'rpc-password': rpcPassword,
    network: 'tor',
  }
  return async () => stored
}

/** Capture `console.warn` output emitted while `fn` runs. */
const captureWarnings = async (fn: () => Promise<unknown>) => {
  const lines: string[] = []
  const original = console.warn
  console.warn = (...args: unknown[]) => {
    lines.push(args.map(String).join(' '))
  }
  try {
    await fn()
  } finally {
    console.warn = original
  }
  return lines
}

test('sid is the first 16 hex characters of sha256(payout address)', () => {
  assert.equal(supplierSid(bech32Address), bech32Sid)
  assert.equal(supplierSid(p2pkhAddress), p2pkhSid)
  assert.equal(
    supplierDashboardUrl(bech32Address),
    `${dashboardBaseUrl}?s=${bech32Sid}`,
  )
})

test('a valid stored address yields the exact copyable dashboard URL', async () => {
  const result = await supplierDashboardResult(storedConfig(bech32Address))

  assert.deepEqual(result, {
    version: '1',
    title: 'Supplier Dashboard',
    message:
      'Copy this URL into a browser to view your supplier status page. It is derived from your payout address.',
    result: {
      type: 'single',
      value: `https://b.pyblock.xyz:8443/supplier.php?s=${bech32Sid}`,
      copyable: true,
      qr: false,
      masked: false,
    },
  })
})

test('accepts every address family the Configure action accepts', async () => {
  const result = await supplierDashboardResult(storedConfig(p2pkhAddress))

  assert.equal(result.result?.type, 'single')
  assert.equal(
    result.result?.value,
    `https://b.pyblock.xyz:8443/supplier.php?s=${p2pkhSid}`,
  )
})

test('surrounding whitespace is trimmed before validation and hashing', async () => {
  const result = await supplierDashboardResult(storedConfig(`  ${bech32Address}\n`))

  assert.equal(result.result?.type, 'single')
  assert.equal(result.result?.value, supplierDashboardUrl(bech32Address))
})

for (const [label, reader] of [
  ['no config file', async () => null],
  ['empty address', storedConfig('')],
  ['blank address', storedConfig('   ')],
] as const satisfies ReadonlyArray<readonly [string, StoredConfigReader]>) {
  test(`${label} produces a not-configured message and no URL`, async () => {
    const result = await supplierDashboardResult(reader)

    assert.equal(result.version, '1')
    assert.equal(result.title, 'Supplier Dashboard')
    assert.match(result.message ?? '', /Not configured yet\. Open Configure/)
    assert.equal(result.result, null)
    assert.equal(JSON.stringify(result).includes('supplier.php'), false)
  })
}

for (const invalid of [
  'not-an-address',
  'bc1qTOOSHORT',
  'bc1q' + 'x'.repeat(90),
  '0A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
  '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa; DROP',
]) {
  test(`invalid stored address ${JSON.stringify(invalid)} is rejected without hashing`, async () => {
    const result = await supplierDashboardResult(storedConfig(invalid))

    assert.equal(result.result, null)
    assert.match(result.message ?? '', /not a valid BLAKE2b-chain address/)
    const serialized = JSON.stringify(result)
    assert.equal(serialized.includes('supplier.php'), false)
    assert.equal(serialized.includes(supplierSid(invalid)), false)
    assert.equal(serialized.includes(invalid.trim()), false)
  })
}

test('a config read failure is reported generically and never echoes the error', async () => {
  // Mimic a YAML parser error that quotes the offending line of config.yaml.
  const parserError = new Error(
    `bad indentation at line 6: rpc-password: ${rpcPassword}`,
  )
  let result: Awaited<ReturnType<typeof supplierDashboardResult>> | undefined

  const warnings = await captureWarnings(async () => {
    result = await supplierDashboardResult(async () => {
      throw parserError
    })
  })

  assert.ok(result)
  assert.equal(result.version, '1')
  assert.equal(result.title, 'Supplier Dashboard')
  assert.match(result.message ?? '', /could not be read\. Open Configure/)
  assert.equal(result.result, null)

  const serialized = JSON.stringify(result)
  assert.equal(serialized.includes(rpcPassword), false)
  assert.equal(serialized.includes('bad indentation'), false)
  assert.equal(serialized.includes('supplier.php'), false)

  assert.deepEqual(warnings, [configUnreadableAuditMessage])
  assert.equal(configUnreadableAuditMessage.includes(rpcPassword), false)
})

test('a non-Error rejection is handled the same way', async () => {
  const warnings = await captureWarnings(async () => {
    const result = await supplierDashboardResult(async () => {
      throw 'EACCES'
    })
    assert.equal(result.result, null)
    assert.equal(JSON.stringify(result).includes('EACCES'), false)
  })
  assert.equal(warnings.length, 1)
})

test('result discloses neither the raw payout address nor the RPC password', async () => {
  const result = await supplierDashboardResult(storedConfig(bech32Address))
  const serialized = JSON.stringify(result)

  assert.equal(serialized.includes(rpcPassword), false)
  assert.equal(serialized.includes(bech32Address), false)
  assert.equal(serialized.includes(bech32Sid), true)
  assert.equal(result.result?.type === 'single' && result.result.masked, false)
})
