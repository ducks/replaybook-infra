#!/usr/bin/env python3
import hashlib
import hmac
import os
import sqlite3


database = os.environ["SESSION_DATABASE"]
old_secret = os.environ["OLD_SESSION_SECRET"].encode()
new_secret = os.environ["NEW_SESSION_SECRET"].encode()


def sign(secret: bytes, session_id: str) -> str:
    return hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()


with sqlite3.connect(database, timeout=30) as connection:
    connection.execute("BEGIN IMMEDIATE")
    rows = connection.execute(
        "SELECT session_id, signature FROM sessions WHERE revoked = 0"
    ).fetchall()
    migrated = 0
    for session_id, stored_signature in rows:
        if hmac.compare_digest(stored_signature, sign(old_secret, session_id)):
            connection.execute(
                "UPDATE sessions SET signature = ? WHERE session_id = ?",
                (sign(new_secret, session_id), session_id),
            )
            migrated += 1
print(f"migrated {migrated} active sessions")
