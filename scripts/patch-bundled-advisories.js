#!/usr/bin/env node
/**
 * Post-install patch: replace bundled-but-vulnerable transitive dependencies
 * shipped inside @start9labs/start-sdk with their patched versions.
 *
 * Context: @start9labs/start-sdk@2.0.9 declares eslint and typescript-eslint
 * in bundleDependencies, so they (and their transitive deps) are packed inside
 * the SDK tarball. npm overrides cannot reach inBundle packages; this script
 * patches them in-place after every install so the disk matches what the
 * lockfile declares.
 *
 * Advisories addressed:
 *   brace-expansion: GHSA-3jxr-9vmj-r5cp, GHSA-mh99-v99m-4gvg, GHSA-rgw5-rvv9-x895
 *   js-yaml:         GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj, GHSA-2883-xcg3-v3hh
 *
 * Remove this script once @start9labs/start-sdk ships these deps at patched versions.
 */
'use strict';

const { rmSync, cpSync, readFileSync, existsSync } = require('fs');
const { join, resolve } = require('path');

const ROOT = resolve(__dirname, '..');
const SDK_NM = join(ROOT, 'node_modules/@start9labs/start-sdk/node_modules');

// Bail out silently if the SDK is not installed (e.g. npm install --ignore-scripts).
if (!existsSync(SDK_NM)) {
  process.exit(0);
}

const patches = [
  ['@eslint/config-array/node_modules/brace-expansion',                 'brace-expansion-v1', 'brace-expansion', '1.1.18'],
  ['@eslint/eslintrc/node_modules/brace-expansion',                     'brace-expansion-v1', 'brace-expansion', '1.1.18'],
  ['eslint/node_modules/brace-expansion',                               'brace-expansion-v1', 'brace-expansion', '1.1.18'],
  ['@typescript-eslint/typescript-estree/node_modules/brace-expansion', 'brace-expansion-v5', 'brace-expansion', '5.0.9'],
  ['@eslint/eslintrc/node_modules/js-yaml',                             'js-yaml-patched',    'js-yaml',         '4.3.2'],
];

try {
  for (const [relTarget, alias, pkgName, ver] of patches) {
    const source = join(ROOT, 'node_modules', alias);
    const target = join(SDK_NM, relTarget);
    if (!existsSync(source)) {
      throw new Error(`locked patch package is missing: ${alias}`);
    }
    const sourcePkg = JSON.parse(readFileSync(join(source, 'package.json'), 'utf8'));
    if (sourcePkg.name !== pkgName || sourcePkg.version !== ver) {
      throw new Error(
        `unexpected ${alias} package: ${sourcePkg.name}@${sourcePkg.version}; expected ${pkgName}@${ver}`
      );
    }
    rmSync(target, { recursive: true, force: true });
    cpSync(source, target, { recursive: true });
    const installedVer = JSON.parse(readFileSync(join(target, 'package.json'), 'utf8')).version;
    console.log(`  [patch] ${pkgName}@${installedVer}  →  ${relTarget}`);
  }

  console.log('[pyblock postinstall] Bundled advisory patches applied successfully.');
} catch (err) {
  console.error('[pyblock postinstall] Patch script failed:', err.message);
  process.exit(1);
}
