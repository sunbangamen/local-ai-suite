#!/usr/bin/env python3
"""
Apply Approval Workflow Schema
승인 워크플로우 테이블을 기존 security.db에 추가

Usage:
    python scripts/apply_approval_schema.py
    python scripts/apply_approval_schema.py --db-path /path/to/security.db
"""

import asyncio
import aiosqlite
import argparse
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path("/mnt/e/ai-data/sqlite/security.db")
SCHEMA_PATH = Path(__file__).parent / "approval_schema.sql"


async def apply_schema(db_path: Path, schema_path: Path):
    """Apply approval workflow schema to database"""
    print(f"Applying schema from {schema_path}")
    print(f"Target database: {db_path}")

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False

    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}")
        return False

    try:
        # Read schema
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Apply schema
        async with aiosqlite.connect(db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys=ON")

            # Execute schema
            await db.executescript(schema_sql)
            await db.commit()

            # Verify table creation
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='approval_requests'"
            )
            result = await cursor.fetchone()

            if result:
                print("✓ approval_requests table created successfully")

                # Check if view was created
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='view' AND name='pending_approvals'"
                )
                result = await cursor.fetchone()
                if result:
                    print("✓ pending_approvals view created successfully")

                # Show table info
                cursor = await db.execute("PRAGMA table_info(approval_requests)")
                columns = await cursor.fetchall()
                print(f"\nTable structure ({len(columns)} columns):")
                for col in columns:
                    print(f"  - {col[1]} ({col[2]})")

                return True
            else:
                print("✗ Failed to create approval_requests table")
                return False

    except Exception as e:
        print(f"Error applying schema: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    parser = argparse.ArgumentParser(description="Apply Approval Workflow Schema")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help="Database path")
    parser.add_argument("--schema-path", type=str, default=str(SCHEMA_PATH), help="Schema file path")

    args = parser.parse_args()

    db_path = Path(args.db_path)
    schema_path = Path(args.schema_path)

    success = await apply_schema(db_path, schema_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
