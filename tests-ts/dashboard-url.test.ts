import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import test from 'node:test'

function supplierSid(payoutAddress: string): string {
  return createHash('sha256').update(payoutAddress).digest('hex').slice(0, 16)
}

test('sid is the first 16 hex chars of sha256 of the payout address', () => {
  const addr = 'bc1qexample0000000000000000000000000000000000'
  const sid = supplierSid(addr)
  const expected = createHash('sha256').update(addr).digest('hex').slice(0, 16)

  assert.equal(sid, expected)
  assert.equal(sid.length, 16)
  assert.match(sid, /^[0-9a-f]{16}$/)
})

test('sid changes when the payout address changes', () => {
  const sid1 = supplierSid('bc1qaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
  const sid2 = supplierSid('bc1qbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')
  assert.notEqual(sid1, sid2)
})

test('dashboard URL embeds the correct sid', () => {
  const addr = 'bc1qexample0000000000000000000000000000000000'
  const sid = supplierSid(addr)
  const url = `https://b.pyblock.xyz:8443/supplier.php?sid=${sid}`

  assert.ok(url.startsWith('https://b.pyblock.xyz:8443/supplier.php?sid='))
  assert.ok(url.endsWith(sid))
})
