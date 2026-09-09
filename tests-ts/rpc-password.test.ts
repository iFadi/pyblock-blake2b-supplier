import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildConfigFormDefaults,
  resolveRpcPassword,
  rpcPasswordAuditMessage,
} from '../startos/actions/rpc-password.js'

test('rejects a blank password on the first save', () => {
  assert.throws(
    () => resolveRpcPassword('', undefined),
    /RPC Password is required the first time configuration is saved\./,
  )
})

test('retains the exact stored password on a later blank save', () => {
  const stored = '  exact stored credential  '
  assert.deepEqual(resolveRpcPassword('', stored), {
    value: stored,
    status: 'kept',
  })
})

test('rotates to the exact nonblank value without transforming it', () => {
  const submitted = '  rotated credential  '
  assert.deepEqual(resolveRpcPassword(submitted, 'old credential'), {
    value: submitted,
    status: 'updated',
  })
})

test('audit output discloses neither the password nor its length', () => {
  const password = 'credential-that-must-not-appear'
  const resolved = resolveRpcPassword(password, 'old credential')
  const message = rpcPasswordAuditMessage(resolved.status)

  assert.equal(message, 'Configuration saved; RPC password updated')
  assert.equal(message.includes(password), false)
  assert.equal(message.includes(String(password.length)), false)
})

test('form defaults never return or serialize the stored password', () => {
  const password = 'credential-that-must-not-reach-the-browser'
  const defaults = buildConfigFormDefaults({
    'payout-address': 'bc1qexample0000000000000000000000000000000000',
    'supplier-name': null,
    'rpc-host': 'bitcoind.embassy',
    'rpc-port': 8332,
    'rpc-user': 'supplier',
    'rpc-password': password,
    network: 'tor',
  })

  assert.equal('rpc-password' in defaults, false)
  assert.equal(JSON.stringify(defaults).includes(password), false)
})
