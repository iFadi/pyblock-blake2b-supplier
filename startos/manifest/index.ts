import { setupManifest } from '@start9labs/start-sdk'
import { short, long } from './i18n.js'

export const manifest = setupManifest({
  id: 'pyblock-blake2b-supplier',
  title: 'PyBLOCK BLAKE2b Supplier',
  license: 'MIT',
  packageRepo: 'https://github.com/iFadi/pyblock-blake2b-supplier',
  upstreamRepo: 'https://github.com/iFadi/pyblock-blake2b-supplier',
  marketingUrl: 'https://b.pyblock.xyz:8443/suppliers.php',
  donationUrl: 'https://donate.asbih.com/',
  description: { short, long },
  volumes: ['main'],
  images: {
    main: {
      source: {
        dockerBuild: {},
      },
      arch: ['x86_64', 'aarch64'],
    },
  },
  dependencies: {
    bitcoind: {
      description:
        'BLAKE2b-capable Bitcoin full node on this device. Required: the supplier reads getblocktemplate from a local node only.',
      optional: false,
      s9pk: null,
    },
  },
})
