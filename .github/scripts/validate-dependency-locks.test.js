const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { test } = require('node:test')

const expectedIndex =
  'sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a'
const expectedPlatforms = {
  'linux/amd64':
    'sha256:78e98729f8fc4099e53cffb3fe59fd15b18dfa4ace8c914dee0cefa5320068eb',
  'linux/arm64/v8':
    'sha256:6c251882dcd56a1b1f20e174a09465f68a6b85c1d066becd954889099177ec34',
}

const expectedApks = [
  'libbsd=0.12.2-r0',
  'libcap2=2.78-r0',
  'libevent=2.1.13-r0',
  'libmd=1.2.0-r0',
  'libseccomp=2.6.0-r2',
  'netcat-openbsd=1.234.1-r0',
  'su-exec=0.3-r0',
  'tor=0.4.9.11-r0',
  'zstd-libs=1.5.7-r2',
]

function nonemptyLines(path) {
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((line) => line.trim() !== '')
}

test('every Docker stage uses the locked multi-architecture OCI index', () => {
  const dockerfile = readFileSync('Dockerfile', 'utf8')
  const froms = [...dockerfile.matchAll(/^FROM\s+(\S+)/gm)].map((match) => match[1])
  assert.deepEqual(froms, [
    `python:3.12-alpine@${expectedIndex}`,
    `python:3.12-alpine@${expectedIndex}`,
  ])

  const lock = JSON.parse(readFileSync('docker/base-images.lock.json', 'utf8'))
  assert.equal(lock.image, 'python:3.12-alpine')
  assert.equal(lock.indexDigest, expectedIndex)
  assert.deepEqual(lock.platforms, expectedPlatforms)
  for (const digest of [lock.indexDigest, ...Object.values(lock.platforms)]) {
    assert.match(digest, /^sha256:[a-f0-9]{64}$/)
  }
})

test('the complete runtime APK addition set is exact and Tor is artifact-hashed', () => {
  const apkLines = nonemptyLines('docker/runtime-apk.lock')
  assert.deepEqual(apkLines, expectedApks)
  for (const requirement of apkLines) {
    assert.match(requirement, /^[a-z0-9][a-z0-9+._-]*=[^=\s]+-r[0-9]+$/)
  }

  const torHashes = Object.fromEntries(
    nonemptyLines('docker/tor-apk-sha256.lock').map((line) => line.split(' ')),
  )
  assert.deepEqual(torHashes, {
    aarch64: '212e8e837ec2fc774efd0de72c7e99ffc3b940ed069bf78e37cd7e6dd8b9ea03',
    x86_64: '61bc9aea9de0fffae3c9a7eb437d288cb6007fff768d2b67c696f66702256efb',
  })

  const installer = readFileSync('scripts/install-runtime-apks.sh', 'utf8')
  assert.match(installer, /tor_version=0\.4\.9\.11-r0/)
  assert.match(installer, /sha256sum (?:--check|-c)/)
  assert.match(installer, /amd64\) alpine_arch=x86_64/)
  assert.match(installer, /arm64\) alpine_arch=aarch64/)
  assert.match(installer, /apk info -v \| sort > "\$installed_before"/)
  assert.match(installer, /comm -13 "\$installed_before" "\$installed_after"/)
  assert.match(installer, /comm -23 "\$installed_before" "\$installed_after"/)
  assert.match(installer, /diff -u "\$apk_lock" "\$added_after"/)
  assert.match(installer, /replaced or removed base-image packages/)
  assert.doesNotMatch(installer, /apk\s+(?:upgrade|update)/)
})

test('all Python requirement entries are exact and hash-locked', () => {
  for (const path of ['requirements-runtime.txt', 'requirements-test.txt']) {
    const source = readFileSync(path, 'utf8')
    const logicalLines = source.replace(/\\\n\s*/g, ' ').split('\n')
    for (const line of logicalLines) {
      const requirement = line.trim()
      if (!requirement || requirement.startsWith('-r ')) continue
      assert.match(requirement, /^[A-Za-z0-9][A-Za-z0-9._-]*==[^\s]+\s+/)
      assert.match(requirement, /--hash=sha256:[a-f0-9]{64}(?:\s|$)/)
    }
  }

  const dockerfile = readFileSync('Dockerfile', 'utf8')
  assert.equal((dockerfile.match(/--require-hashes/g) ?? []).length, 2)
  assert.doesNotMatch(dockerfile, /pip\s+install(?![^\n]*--require-hashes)/)
})
