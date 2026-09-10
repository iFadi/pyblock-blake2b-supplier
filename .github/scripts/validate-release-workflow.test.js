const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { test } = require('node:test')

function exactlyOne(source, pattern, description) {
  const matches = [...source.matchAll(pattern)]
  assert.equal(matches.length, 1, `expected one ${description}, found ${matches.length}`)
  return matches[0][1]
}

test('release workflow literals match the current StartOS version', () => {
  const versionSource = readFileSync('startos/versions/current.ts', 'utf8')
  const workflow = readFileSync('.github/workflows/release.yml', 'utf8')
  const version = exactlyOne(
    versionSource,
    /^\s*version:\s*'([^']+)'\s*,\s*$/gm,
    'current package version',
  )
  const versionMatch = version.match(/^([0-9]+\.[0-9]+\.[0-9]+):([0-9]+)$/)
  assert.ok(versionMatch, `unsupported package version: ${version}`)
  const expectedTag = `v${versionMatch[1]}-rev${versionMatch[2]}`

  assert.equal(
    exactlyOne(workflow, /^\s*default:\s*(v[^\s]+)\s*$/gm, 'dispatch tag default'),
    expectedTag,
  )
  assert.equal(
    exactlyOne(workflow, /^\s*EXPECTED_VERSION:\s*([^\s]+)\s*$/gm, 'expected version'),
    version,
  )
  assert.equal(
    exactlyOne(workflow, /^\s*--title\s+"([^"]+)"\s*\\\s*$/gm, 'release title'),
    version,
  )
})
