#!/usr/bin/env python3
"""
scripts/seed_acceptance_operators.py

Seeds two test operators (op_a, op_b) into the existing users_store
for the acceptance harness. Prints their IDs to stdout so the operator
can paste them into tests/acceptance/config.local.json.

Run manually:
    python scripts/seed_acceptance_operators.py

Idempotent: if an operator already exists at the chosen username, the
script reports it and continues without overwriting.

# TODO: adjust import to match actual users_store module if it relocates.
# Current layout (verified): users_store.py at repo root.
"""
from __future__ import annotations

import os
import sys
import time

# Make the repo root importable when running from anywhere.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bcrypt  # type: ignore  # already a dep of the existing app.py
import users_store  # type: ignore


OPERATORS = [
    {
        "username": "op_a@clarityos.test",
        "handle": "op_a",
        "tier": "Operator",
    },
    {
        "username": "op_b@clarityos.test",
        "handle": "op_b",
        "tier": "Operator",
    },
]


def _hash_password(plaintext: str) -> tuple[bytes, str]:
    """Return (password_hash, salt) using bcrypt. Matches the convention
    expected by users_store.create_user."""
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(plaintext.encode("utf-8"), salt)
    return pw_hash, salt.decode("utf-8")


def _ensure_user(spec: dict) -> str:
    """Create the user if absent; return its username (which serves as id
    in the users_store layout)."""
    existing = users_store.get_user(spec["username"])
    if existing is not None:
        print(f"[seed] exists  → {spec['username']} (tier={existing.get('tier')})")
        return spec["username"]

    # Bootstrap secret — placeholder; the harness regenerates per-run secrets
    # and the seed user does not need a stable password for acceptance work.
    placeholder_secret = f"acceptance-seed-{spec['handle']}-bootstrap"
    pw_hash, salt = _hash_password(placeholder_secret)

    users_store.create_user(
        username=spec["username"],
        password_hash=pw_hash,
        salt=salt,
        tier=spec["tier"],
        created_at=time.time(),
    )
    print(f"[seed] created → {spec['username']} (tier={spec['tier']})")
    return spec["username"]


def main() -> int:
    print("=== seeding acceptance operators ===")
    ids: list[str] = []
    for spec in OPERATORS:
        ids.append(_ensure_user(spec))
    print()
    print("operator IDs (paste into tests/acceptance/config.local.json):")
    for spec, oid in zip(OPERATORS, ids):
        print(f"  {spec['handle']}: {oid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
