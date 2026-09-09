export const short = {
  en_US: 'Publish your BLAKE2b block template to the PyBLOCK Carousel',
}

export const long = {
  en_US: `Connects to your local Bitcoin Knots BLAKE2b node, calls getblocktemplate (rules: segwit + blake2b), and pushes the template to the PyBLOCK pool on every new block and every ~20 seconds for mempool updates.

Outbound-only: no inbound ports opened. Tor is used by default so your IP is never sent to PyBLOCK.

REQUIREMENTS:
1. Bitcoin Knots ≥ 29.4.1 BLAKE2b build running on this StartOS device with datacarrier=0 in bitcoin.conf.
2. RPC credentials configured in the Config action.
3. A BLAKE2b-chain address (bc1q…, bc1p…, 1…, or 3…) for BLAKE2b-chain coinbase payouts.`,
}
