const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const { readFileSync } = require('node:fs')
const { test } = require('node:test')
const yaml = require('js-yaml-patched')

const stagePath = '.github/workflows/release-stage.yml'
const promotePath = '.github/workflows/release-promote.yml'
const stage = readFileSync(stagePath, 'utf8')
const promote = readFileSync(promotePath, 'utf8')
const stageDocument = yaml.load(stage)
const promoteDocument = yaml.load(promote)

function matches(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1])
}

function exactly(source, pattern, expected, description) {
  const actual = matches(source, pattern)
  assert.deepEqual(actual, expected, description)
}

test('all release version surfaces match the authoritative StartOS version', () => {
  const versionSource = readFileSync('startos/versions/current.ts', 'utf8')
  const versions = matches(versionSource, /^\s*version:\s*'([^']+)'\s*,\s*$/gm)
  assert.deepEqual(versions, ['1.0.0:12'])
  const versionMatch = versions[0].match(/^([0-9]+\.[0-9]+\.[0-9]+):([0-9]+)$/)
  assert.ok(versionMatch)
  const expectedTag = `v${versionMatch[1]}-rev${versionMatch[2]}`

  exactly(`${stage}\n${promote}`, /^\s*default:\s*(v[^\s]+)\s*$/gm,
    [expectedTag, expectedTag], 'dispatch defaults must match')
  exactly(`${stage}\n${promote}`, /^\s*EXPECTED_VERSION:\s*([^\s]+)\s*$/gm,
    [versions[0], versions[0]], 'manifest expectations must match')
  exactly(promote, /^\s*--title\s+"([^"]+)"\s*\\\s*$/gm,
    [versions[0]], 'release title must match')
})

test('tag pushes cannot stage, rebuild, or publish', () => {
  for (const [path, workflow] of [[stagePath, stage], [promotePath, promote]]) {
    assert.match(workflow, /^on:\n  workflow_dispatch:/m, `${path} must be manual only`)
    assert.doesNotMatch(workflow, /^\s{2}push:/m, `${path} must not accept push`)
    assert.doesNotMatch(workflow, /^\s{2}pull_request:/m, `${path} must not accept pull requests`)
  }
})

test('parsed workflow semantics preserve least privilege and phase separation', () => {
  assert.deepEqual(Object.keys(stageDocument.on), ['workflow_dispatch'])
  assert.deepEqual(Object.keys(promoteDocument.on), ['workflow_dispatch'])
  assert.deepEqual(stageDocument.permissions, {})
  assert.deepEqual(promoteDocument.permissions, {})
  assert.deepEqual(Object.keys(stageDocument.jobs), [
    'validate-source',
    'build-signed',
    'assemble-stage',
  ])
  assert.deepEqual(Object.keys(promoteDocument.jobs), ['validate-request', 'promote'])
  assert.deepEqual(stageDocument.jobs['assemble-stage'].permissions, {
    contents: 'read',
    'id-token': 'write',
    attestations: 'write',
  })
  assert.deepEqual(promoteDocument.jobs.promote.permissions, {
    actions: 'read',
    attestations: 'read',
    contents: 'write',
  })
  assert.deepEqual(
    stageDocument.jobs['build-signed'].strategy.matrix.include.map(({ architecture }) => architecture),
    ['x86_64', 'aarch64'],
  )
  assert.equal(stageDocument.jobs['build-signed'].environment, 'release-staging')
  assert.equal(promoteDocument.jobs.promote.environment, 'release-promotion')
})

test('every embedded workflow shell program parses as Bash', () => {
  for (const [path, document] of [[stagePath, stageDocument], [promotePath, promoteDocument]]) {
    for (const [jobName, job] of Object.entries(document.jobs)) {
      for (const step of job.steps) {
        if (!step.run) continue
        const result = spawnSync('bash', ['-n'], { input: step.run, encoding: 'utf8' })
        assert.equal(result.status, 0, `${path}:${jobName}:${step.name}\n${result.stderr}`)
      }
    }
  }
})

test('staging is source-pinned, secret-isolated, two-architecture, and non-publishing', () => {
  assert.match(stage, /group: release-stage-\$\{\{ inputs\.source_sha \}\}/)
  assert.match(stage, /test "\$DISPATCH_SHA" = "\$SOURCE_SHA"/)
  assert.match(stage, /test "\$checked_out_sha" = "\$SOURCE_SHA"/)
  assert.match(stage, /staging must precede tagging/)
  assert.equal((stage.match(/gh release view "\$RELEASE_TAG"/g) ?? []).length, 1)
  assert.match(stage, /environment: release-staging/)
  assert.equal((stage.match(/secrets\.DEV_KEY/g) ?? []).length, 1)
  assert.equal((stage.match(/make "\$BUILD_TARGET"/g) ?? []).length, 1)
  assert.match(stage, /unset DEV_KEY/)
  assert.match(stage, /trap cleanup_key EXIT/)
  assert.match(stage, /test ! -e "\$HOME\/\.startos\/id\.key\.pem"/)
  exactly(stage, /^\s{12}architecture:\s*(x86_64|aarch64)\s*$/gm,
    ['x86_64', 'aarch64'], 'stage architecture matrix must be exact')
  assert.match(stage, /EXPECTED_VERSION: 1\.0\.0:12/)
  assert.match(stage, /\.gitHash \/\/ empty/)
  assert.match(stage, /runtimeApkClosureSha256/)
  assert.match(stage, /pythonRuntimeRequirementsSha256/)
  assert.match(stage, /sha256sum --check --strict/)
  assert.match(stage, /actions\/attest-build-provenance@[0-9a-f]{40} # v3/)
  assert.match(stage, /retention-days: 3/)
  assert.doesNotMatch(stage, /gh release create/)
  assert.doesNotMatch(stage, /contents: write/)
})

test('promotion pins one prior run and rejects substitution or expiry', () => {
  assert.match(promote, /environment: release-promotion/)
  assert.match(promote, /actions: read/)
  assert.match(promote, /attestations: read/)
  assert.match(promote, /contents: write/)
  assert.match(promote, /\.path == "\.github\/workflows\/release-stage\.yml"/)
  assert.match(promote, /\.head_sha == \$source/)
  assert.match(promote, /\.conclusion == "success"/)
  assert.match(promote, /test "\$count" -eq 1/)
  assert.match(promote, /\.expired == false/)
  assert.match(promote, /\.workflow_run\.id == \$runId/)
  assert.match(promote, /run-id: \$\{\{ inputs\.staging_run_id \}\}/)
  assert.match(promote, /name: release-stage-\$\{\{ needs\.validate-request\.outputs\.source-sha \}\}/)
  assert.match(promote, /gh attestation verify/)
  assert.match(promote, /--signer-workflow "\$GH_REPO\/\.github\/workflows\/release-stage\.yml"/)
  assert.match(promote, /sha256sum --check --strict SHA256SUMS/)
  assert.match(promote, /\.runId == \$runId/)
  assert.match(promote, /\.sourceSha == \$source/)
  assert.match(promote, /\.releaseTag == \$tag/)
})

test('promotion verifies the protected signed annotated tag and refuses overwrite', () => {
  assert.match(promote, /repos\/\$GH_REPO\/rulesets\/\$RULESET_ID/)
  assert.match(promote, /\.target == "tag"/)
  assert.match(promote, /\.enforcement == "active"/)
  for (const rule of ['creation', 'update', 'deletion']) {
    assert.match(promote, new RegExp(`index\\("${rule}"\\) != null`))
  }
  assert.match(promote, /test "\$\(jq -r '\.object\.type' <<<"\$ref"\)" = tag/)
  assert.match(promote, /\.object\.sha == \$source/)
  assert.match(promote, /\.verification\.verified == true/)
  assert.equal((promote.match(/gh release view "\$RELEASE_TAG"/g) ?? []).length, 2)
  assert.equal((promote.match(/gh release create "\$RELEASE_TAG"/g) ?? []).length, 1)
  assert.match(promote, /--verify-tag/)
})

test('promotion cannot build or access the persistent signing key', () => {
  assert.doesNotMatch(promote, /DEV_KEY|secrets\./)
  assert.doesNotMatch(promote, /\bmake\s|docker\/setup-|docker (?:build|buildx)|start-cli init-key/)
  assert.doesNotMatch(promote, /attest-build-provenance|id-token: write/)
  assert.equal((promote.match(/start-cli s9pk inspect/g) ?? []).length, 1)
})

test('every external workflow dependency is immutable', () => {
  for (const [path, workflow] of [[stagePath, stage], [promotePath, promote]]) {
    const uses = matches(workflow, /^\s*uses:\s*[^@\s]+@([^\s]+)(?:\s+#.*)?$/gm)
    assert.ok(uses.length > 0, `${path} must use pinned actions`)
    for (const ref of uses) {
      assert.match(ref, /^[0-9a-f]{40}$/, `${path} contains mutable action ref ${ref}`)
    }
  }
})
