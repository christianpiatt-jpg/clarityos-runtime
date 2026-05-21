"""
SOS Runtime — Cloud Run + IAM + audience preflight.

Drop-in, founder-authored. Run from a terminal BEFORE configuring the
WordPress connector plugin so JWT / audience / IAM-binding issues
surface here (where the error messages are loud) instead of in WP
Admin (where the same failures route through ``WP_Error`` and need
deeper bisection).

Why this proves the JWT chain even though /health is "public":
    The Cloud Run service is deployed with ``--no-allow-unauthenticated``
    (see ``cloudbuild.yaml``), which means Cloud Run IAM gates EVERY
    request at ingress, regardless of the in-app handler's auth
    posture. So:
        * Valid JWT + audience match    → 200 from /health
        * Invalid JWT / bad signature   → 401 from Cloud Run platform
        * Audience mismatch             → 401 from Cloud Run IAM
        * Service account lacks roles/run.invoker → 403
        * Cloud Run cold-boot / OOM     → 5xx from Cloud Run platform
    /health is the cheapest, lowest-cardinality probe that still
    exercises the full IAM chain.

Install:
    pip install google-auth requests

Run:
    export SOS_SERVICE_ACCOUNT_JSON='{...full SA JSON...}'
    export SOS_CLOUD_RUN_URL='https://os-runtime-xxxxx-uc.a.run.app'
    python preflight.py
"""
import json
import os
import sys
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession


def main():
    sa_json = os.getenv("SOS_SERVICE_ACCOUNT_JSON")
    run_url = os.getenv("SOS_CLOUD_RUN_URL")

    if not sa_json or not run_url:
        print(
            "ERROR: Set SOS_SERVICE_ACCOUNT_JSON and SOS_CLOUD_RUN_URL env vars.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        info = json.loads(sa_json)
    except json.JSONDecodeError:
        print(
            "ERROR: SOS_SERVICE_ACCOUNT_JSON is not valid JSON.",
            file=sys.stderr,
        )
        sys.exit(1)

    audience = run_url.rstrip("/")
    creds = service_account.IDTokenCredentials.from_service_account_info(
        info,
        target_audience=audience,
    )

    authed_session = AuthorizedSession(creds)

    health_url = f"{audience}/health"
    print(f"→ GET {health_url}")
    resp = authed_session.get(health_url, timeout=10)

    print(f"Status: {resp.status_code}")
    print("Body:")
    print(resp.text)

    if resp.status_code == 200:
        print("\nOK: Cloud Run + IAM + audience are correctly wired.")
    else:
        print(
            "\nFAIL: Non-200 from /health — check service account roles, "
            "audience, and URL."
        )


if __name__ == "__main__":
    main()
