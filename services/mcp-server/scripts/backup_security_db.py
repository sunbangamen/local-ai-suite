#!/usr/bin/env python3
"""
Security Database Backup Script
Performs WAL checkpoint and creates timestamped backup

Usage:
    python backup_security_db.py [--output-dir /path/to/backups]
"""

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_database import get_security_database


async def backup_database(output_dir: Path) -> Path:
    """
    Backup security database with WAL checkpoint

    Returns:
        Path to backup file
    """
    db = get_security_database()
    db_path = db.db_path

    # Ensure database exists
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Checkpoint WAL (flush to main database)
    print("Checkpointing WAL...")
    await db.checkpoint()

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"security_backup_{timestamp}.db"
    backup_path = output_dir / backup_filename

    # Copy database file
    print(f"Copying database: {db_path} -> {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Get database info
    db_info = await db.get_db_info()
    print("\nBackup completed:")
    print(f"  Backup file: {backup_path}")
    print(f"  Database size: {db_info['db_size_mb']} MB")
    print(f"  WAL size: {db_info['wal_size_mb']} MB")

    # Verify backup integrity
    import aiosqlite

    async with aiosqlite.connect(backup_path) as conn:
        async with conn.execute("PRAGMA integrity_check") as cursor:
            result = await cursor.fetchone()
            if result[0] == "ok":
                print("  Integrity check: PASSED")
            else:
                print(f"  Integrity check: FAILED - {result[0]}")
                raise RuntimeError("Backup integrity check failed")

    return backup_path


async def restore_database(backup_path: Path) -> None:
    """
    Restore database from backup

    Args:
        backup_path: Path to backup file
    """
    db = get_security_database()
    db_path = db.db_path

    # Verify backup exists
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Verify backup integrity
    import aiosqlite

    async with aiosqlite.connect(backup_path) as conn:
        async with conn.execute("PRAGMA integrity_check") as cursor:
            result = await cursor.fetchone()
            if result[0] != "ok":
                raise RuntimeError(f"Backup integrity check failed: {result[0]}")

    # Backup current database (if exists)
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = db_path.parent / f"security_before_restore_{timestamp}.db"
        print(f"Backing up current database: {current_backup}")
        shutil.copy2(db_path, current_backup)

    # Restore from backup
    print(f"Restoring database from: {backup_path}")
    shutil.copy2(backup_path, db_path)

    print(f"Database restored successfully: {db_path}")


async def cleanup_old_backups(backup_dir: Path, keep_days: int = 7) -> None:
    """
    Remove backups older than N days

    Args:
        backup_dir: Directory containing backups
        keep_days: Number of days to keep backups
    """
    from datetime import timedelta

    cutoff_time = datetime.now() - timedelta(days=keep_days)
    removed_count = 0

    for backup_file in backup_dir.glob("security_backup_*.db"):
        # Extract timestamp from filename
        try:
            timestamp_str = backup_file.stem.split("_", 2)[2]  # security_backup_YYYYMMDD_HHMMSS
            file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if file_time < cutoff_time:
                print(f"Removing old backup: {backup_file}")
                backup_file.unlink()
                removed_count += 1
        except (ValueError, IndexError):
            print(f"Skipping invalid backup filename: {backup_file}")

    print(f"\nRemoved {removed_count} backups older than {keep_days} days")


async def main():
    parser = argparse.ArgumentParser(description="Security database backup utility")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/mnt/e/ai-data/sqlite/backups"),
        help="Backup output directory",
    )
    parser.add_argument("--restore", type=Path, help="Restore database from backup file")
    parser.add_argument(
        "--cleanup", type=int, metavar="DAYS", help="Cleanup backups older than N days"
    )

    args = parser.parse_args()

    if args.restore:
        # Restore mode
        await restore_database(args.restore)
    elif args.cleanup:
        # Cleanup mode
        await cleanup_old_backups(args.output_dir, args.cleanup)
    else:
        # Backup mode
        backup_path = await backup_database(args.output_dir)
        print(f"\n✅ Backup successful: {backup_path}")


if __name__ == "__main__":
    asyncio.run(main())
