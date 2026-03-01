"""Add content, status, and per-post metric columns to posts table.
Create post_demographics table.

Run once after deploying this feature:
    python scripts/migrate_002_post_content.py

Idempotent: safe to run multiple times (checks for column/table existence).
"""

import sqlite3

from app.config import settings


def migrate() -> None:
    conn = sqlite3.connect(str(settings.db_path))
    cursor = conn.cursor()

    # Add new columns to posts table
    cursor.execute("PRAGMA table_info(posts)")
    existing = {row[1] for row in cursor.fetchall()}

    post_columns = [
        ("content", "TEXT"),
        ("status", "VARCHAR(20)"),
        ("saves", "INTEGER"),
        ("sends", "INTEGER"),
        ("profile_views", "INTEGER"),
        ("followers_gained", "INTEGER"),
        ("reposts", "INTEGER"),
    ]

    for col_name, col_type in post_columns:
        if col_name not in existing:
            cursor.execute(
                f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}"
            )
            print(f"Added column: posts.{col_name}")
        else:
            print(f"Column already exists: posts.{col_name}")

    # Create post_demographics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_demographics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            category VARCHAR NOT NULL,
            value VARCHAR NOT NULL,
            percentage FLOAT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, category, value)
        )
    """)
    print("Ensured post_demographics table exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
