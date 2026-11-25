#!/usr/bin/env python3
"""Idempotently reconcile Open WebUI PersistentConfig audio keys in webui.db."""

import argparse
import json
import os
import sqlite3
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Open WebUI persistent audio config.")
    parser.add_argument("--db", required=True, help="Path to Open WebUI webui.db")
    parser.add_argument("--config-json", required=True, help="JSON object of config keys to desired values")
    parser.add_argument("--check", action="store_true", help="Dry-run without writing changes")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print("UNCHANGED: db does not exist yet")
        return 0

    desired = json.loads(args.config_json)
    conn = sqlite3.connect(args.db, timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'config'"
        ).fetchone()
        if not table_exists:
            print("UNCHANGED: config table does not exist yet")
            return 0

        changed_keys = []
        now = int(time.time())
        for key, value in desired.items():
            encoded = json.dumps(value)
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            if row is None or row[0] != encoded:
                changed_keys.append(key)
                if not args.check:
                    conn.execute(
                        "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                        (key, encoded, now),
                    )

        if changed_keys and not args.check:
            conn.commit()

        if changed_keys:
            print("CHANGED: " + ", ".join(changed_keys))
        else:
            print("UNCHANGED")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
