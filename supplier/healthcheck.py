"""StartOS health check entry point.

Invoked by the runtime inside the service container. Reads the health state
recorded by the supplier loop, evaluates it fail-closed (see supplier.health)
and prints a single JSON object on stdout:

    {"result": "<startos result>", "message": "<human readable>"}

Always exits 0. A non-zero exit would be reported by the runtime as an opaque
script failure and the message below — which is the whole point of the check —
would be lost.
"""

import json
import sys

from supplier.health import read_state

# Internal states map onto the StartOS health check vocabulary. Anything not
# listed here is a failure: the default is chosen so that a state added later
# without updating this table degrades to "failing", never to "success".
STARTOS_RESULT = {
    "healthy_active": "success",
    "starting": "starting",
    "no_state": "starting",
    "node_unsynced": "loading",
}


def evaluate() -> dict:
    state = read_state()
    result = STARTOS_RESULT.get(state["state"], "failure")
    message = state["message"]
    return {"result": result, "message": message}


def main() -> None:
    try:
        payload = evaluate()
    except Exception as e:  # noqa: BLE001 — the check itself must never crash
        payload = {
            "result": "failure",
            "message": f"Health check failed to run: {type(e).__name__}: {e}",
        }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
