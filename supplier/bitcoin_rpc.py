"""Bitcoin JSON-RPC client.

Communicates with the local Bitcoin Knots BLAKE2b node over HTTP basic auth.
Never proxied through Tor — the node is a local StartOS service.
"""

import json
import urllib.request
import urllib.error
import base64
from typing import Any

GBT_RULES = {"rules": ["segwit", "blake2b"]}


class RPCError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class BitcoinRPC:
    def __init__(self, config):
        self.url = f"http://{config.rpc_host}:{config.rpc_port}/"
        creds = f"{config.rpc_user}:{config.rpc_password}"
        self._auth = "Basic " + base64.b64encode(creds.encode()).decode()
        self._id = 0

    def call(self, method: str, params: list | None = None) -> Any:
        self._id += 1
        payload = json.dumps({
            "jsonrpc": "1.1",
            "id": self._id,
            "method": method,
            "params": params or [],
        }).encode()
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "Authorization": self._auth,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
            except Exception:
                raise RPCError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise RPCError(f"Connection failed: {e.reason}")
        except Exception as e:
            raise RPCError(f"RPC error: {e}")

        if body.get("error"):
            err = body["error"]
            raise RPCError(err.get("message", str(err)), code=err.get("code"))
        return body["result"]

    def getblockchaininfo(self) -> dict:
        return self.call("getblockchaininfo")

    def getnetworkinfo(self) -> dict:
        return self.call("getnetworkinfo")

    def getblockcount(self) -> int:
        return self.call("getblockcount")

    def getblocktemplate(self) -> dict:
        """Call getblocktemplate with segwit+blake2b rules.

        RPCError with code -8 ("unknown rule: blake2b") means the node is not
        a BLAKE2b-capable build — health state: gbt_unsupported.
        """
        return self.call("getblocktemplate", [GBT_RULES])
