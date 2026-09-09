const { readFileSync } = require('node:fs')

const tag = process.env.RELEASE_TAG ?? ''
const tagPattern = /^v([0-9]+)\.([0-9]+)\.([0-9]+)-rev([0-9]+)$/
const tagMatch = tag.match(tagPattern)

if (!tagMatch) {
  console.error(
    '::error::Release tag must match v<major>.<minor>.<patch>-rev<revision>',
  )
  process.exit(1)
}

const source = readFileSync('startos/versions/current.ts', 'utf8')
const manifestVersions = [
  ...source.matchAll(/^\s*version:\s*'([^']+)'\s*,\s*$/gm),
]

if (manifestVersions.length !== 1) {
  console.error(
    `::error::Expected exactly one version field in startos/versions/current.ts, found ${manifestVersions.length}`,
  )
  process.exit(1)
}

const expectedVersion = `${tagMatch[1]}.${tagMatch[2]}.${tagMatch[3]}:${tagMatch[4]}`
const manifestVersion = manifestVersions[0][1]

if (manifestVersion !== expectedVersion) {
  console.error(
    `::error::Release tag ${tag} resolves to ${expectedVersion}, but startos/versions/current.ts declares ${manifestVersion}`,
  )
  process.exit(1)
}

console.log(`Validated ${tag} against package version ${manifestVersion}`)
