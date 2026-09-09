"""Config loader for pyblock-blake2b-supplier.

StartOS writes config values (from the UI form) to /root/start9/config.yaml.
This module reads and validates that file, exposing a typed Config object.
"""

import os
import re
import urllib.parse

import yaml

CONFIG_PATH = os.environ.get("PYBLOCK_CONFIG_PATH", "/root/start9/config.yaml")

# Proven from the PyBLOCK join script source:
PYBLOCK_CLEARNET_URL = "http://pool.pyblock.xyz:5800/"
PYBLOCK_ONION_URL = (
    "http://qzhxvlnzfir7pwmsheadahe6hejqkvb3z5nn35ils32hptgpwuzabhyd.onion/"
)

_ADDR_RE = re.compile(
    r'^(bc1[qp][a-z0-9]{6,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$'
)


class ConfigError(Exception):
    pass


class Config:
    def __init__(
        self,
        payout_address: str,
        rpc_host: str,
        rpc_port: int,
        rpc_user: str,
        rpc_password: str,
        network: str,
        supplier_name: str | None,
    ):
        self.payout_address = payout_address
        self.rpc_host = rpc_host
        self.rpc_port = rpc_port
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.network = network
        self.supplier_name = supplier_name

        if network == "tor":
            self.pyblock_url = PYBLOCK_ONION_URL
        else:
            self.pyblock_url = PYBLOCK_CLEARNET_URL

    @property
    def pyblock_endpoint(self) -> tuple[str, int]:
        """(host, port) of the publish target, for the Tor circuit smoke test."""
        parts = urllib.parse.urlsplit(self.pyblock_url)
        return parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80)

    @property
    def uses_tor(self) -> bool:
        return self.network == "tor"

    @classmethod
    def load(cls, path: str = CONFIG_PATH) -> "Config":
        try:
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise ConfigError(f"Config not found at {path} — configure the service in StartOS UI")
        except yaml.YAMLError as e:
            raise ConfigError(f"Config parse error: {e}")

        addr = raw.get("payout-address", "").strip()
        if not addr:
            raise ConfigError("payout-address is required")
        if not _ADDR_RE.match(addr):
            raise ConfigError(
                f"payout-address '{addr}' is not a valid BLAKE2b-chain address "
                "(expected bc1q…, bc1p…, 1…, or 3…)"
            )

        # rpc-host is written by the StartOS runtime from the resolved bitcoind
        # bridge address before the daemon starts. There is deliberately no
        # default and no URL form: this package only ever talks to the local
        # node it declares as a dependency, so an unresolved bridge must be a
        # hard failure rather than a guess at a hostname.
        rpc_host = str(raw.get("rpc-host") or "").strip()
        if not rpc_host:
            raise ConfigError(
                "rpc-host is empty — the local Bitcoin node bridge address could not "
                "be resolved. Ensure a BLAKE2b-capable Bitcoin node is installed and "
                "running on this server, then restart this service."
            )
        if "://" in rpc_host or "/" in rpc_host:
            raise ConfigError(
                f"rpc-host '{rpc_host}' must be a bare host or IP address, not a URL — "
                "this service connects only to the local Bitcoin node"
            )

        try:
            rpc_port = int(raw.get("rpc-port", 8332))
        except (TypeError, ValueError):
            raise ConfigError("rpc-port must be an integer")
        if not (1024 <= rpc_port <= 65535):
            raise ConfigError(f"rpc-port {rpc_port} out of range [1024, 65535]")

        rpc_user = raw.get("rpc-user", "").strip()
        if not rpc_user:
            raise ConfigError("rpc-user is required")

        rpc_password = raw.get("rpc-password", "")
        if not rpc_password:
            raise ConfigError("rpc-password is required")

        network = raw.get("network", "tor").strip().lower()
        if network not in ("tor", "clearnet"):
            raise ConfigError(f"network must be 'tor' or 'clearnet', got '{network}'")

        supplier_name = raw.get("supplier-name") or None
        if supplier_name:
            supplier_name = str(supplier_name).strip() or None

        return cls(
            payout_address=addr,
            rpc_host=rpc_host,
            rpc_port=rpc_port,
            rpc_user=rpc_user,
            rpc_password=rpc_password,
            network=network,
            supplier_name=supplier_name,
        )
