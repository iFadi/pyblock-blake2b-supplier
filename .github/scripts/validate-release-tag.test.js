const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const { test } = require('node:test')

const validator = '.github/scripts/validate-release-tag.js'

function validate(tag) {
  return spawnSync(process.execPath, [validator], {
    cwd: process.cwd(),
    encoding: 'utf8',
    env: { ...process.env, RELEASE_TAG: tag },
  })
}

test('accepts the exact revision-8 tag', () => {
  const result = validate('v1.0.0-rev8')
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /Validated v1\.0\.0-rev8 against package version 1\.0\.0:8/)
})

for (const tag of ['v1.0.0-rev6', 'v1.0.0-rev7']) {
  test(`rejects immutable failed tag ${tag}`, () => {
    const result = validate(tag)
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /resolves to 1\.0\.0:[67].*declares 1\.0\.0:8/)
  })
}

test('rejects malformed tags', () => {
  const result = validate('v1.0.0-rev8-extra')
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /must match/)
})

test('rejects a valid-shaped version mismatch', () => {
  const result = validate('v1.0.1-rev8')
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /resolves to 1\.0\.1:8.*declares 1\.0\.0:8/)
})
