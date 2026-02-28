"""Add cohort analysis columns to the posts table.

Run once after deploying this feature:
    python scripts/migrate_001_cohort_columns.py

Idempotent: safe to run multiple times (checks for column existence).
"""

import sqlite3

from app.config import settings


def migrate() -> None:
    conn = sqlite3.connect(str(settings.db_path))
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(posts)")
    existing = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("topic", "VARCHAR(50)"),
        ("content_format", "VARCHAR(30)"),
        ("hook_style", "VARCHAR(30)"),
        ("length_bucket", "VARCHAR(20)"),
        ("post_hour", "INTEGER"),
    ]

    for col_name, col_type in migrations:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
