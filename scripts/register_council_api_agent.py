"""Register or rotate the Engineering Core machine identity in Supabase.

The raw token is read only from the process environment. Only its SHA-256
hash is sent to Supabase and neither the token nor hash is printed.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


AGENT_ID = "yj64-engineering-core"
SCOPES = ["council:submit", "council:read", "council:cancel"]


def main() -> int:
    base_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    token = os.environ.get("YJ64_COUNCIL_AGENT_TOKEN", "").strip()

    if not base_url.startswith("https://") or not service_key or len(token) < 32:
        print("Missing or invalid Supabase configuration or agent token.", file=sys.stderr)
        return 2

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    endpoint = (
        base_url
        + "/rest/v1/yj64_council_api_agents?on_conflict="
        + urllib.parse.quote("agent_id", safe="")
    )
    payload = json.dumps({
        "agent_id": AGENT_ID,
        "token_hash": token_hash,
        "scopes": SCOPES,
        "enabled": True,
    }, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": "Bearer " + service_key,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                print("Supabase agent registration failed.", file=sys.stderr)
                return 1
    except urllib.error.HTTPError as exc:
        print(
            "Supabase agent registration failed (HTTP "
            + str(exc.code)
            + "). Response body intentionally suppressed.",
            file=sys.stderr,
        )
        return 1
    except (urllib.error.URLError, TimeoutError, OSError):
        print("Supabase agent registration failed due to a network error.", file=sys.stderr)
        return 1

    print("Registered agent yj64-engineering-core; raw token was not emitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
