#!/usr/bin/env python3
"""
Security Database Data Seeding Script
Populate default roles, permissions, and test users

Usage:
    python seed_security_data.py [--reset]
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_database import get_security_database, init_database


# Default roles configuration
DEFAULT_ROLES = [
    {
        "role_name": "guest",
        "description": "Read-only access to files and logs",
        "is_system_role": 1,
        "permissions": [
            "read_file",
            "list_files",
            "rag_search",
            "ai_chat",
            "git_status",
            "git_log",
            "git_diff"
        ]
    },
    {
        "role_name": "developer",
        "description": "Developer access with code execution and Git operations",
        "is_system_role": 1,
        "permissions": [
            "read_file",
            "write_file",
            "list_files",
            "execute_python",
            "execute_bash",
            "rag_search",
            "ai_chat",
            "git_status",
            "git_log",
            "git_diff",
            "git_add",
            "web_screenshot",
            "web_scrape",
            "web_analyze_ui",
            "get_current_model"
        ]
    },
    {
        "role_name": "admin",
        "description": "Full administrative access to all MCP tools",
        "is_system_role": 1,
        "permissions": [
            "read_file",
            "write_file",
            "list_files",
            "execute_python",
            "execute_bash",
            "rag_search",
            "ai_chat",
            "git_status",
            "git_log",
            "git_diff",
            "git_add",
            "git_commit",
            "web_screenshot",
            "web_scrape",
            "web_analyze_ui",
            "web_automate",
            "notion_create_page",
            "notion_search",
            "web_to_notion",
            "switch_model",
            "get_current_model"
        ]
    }
]

# All 18 MCP tools + permissions
ALL_PERMISSIONS = [
    # File operations
    {"name": "read_file", "resource_type": "file", "action": "read", "sensitivity": "MEDIUM"},
    {"name": "write_file", "resource_type": "file", "action": "write", "sensitivity": "HIGH"},
    {"name": "list_files", "resource_type": "file", "action": "read", "sensitivity": "LOW"},

    # Code execution
    {"name": "execute_python", "resource_type": "tool", "action": "execute", "sensitivity": "CRITICAL"},
    {"name": "execute_bash", "resource_type": "tool", "action": "execute", "sensitivity": "CRITICAL"},

    # RAG & AI
    {"name": "rag_search", "resource_type": "tool", "action": "read", "sensitivity": "LOW"},
    {"name": "ai_chat", "resource_type": "tool", "action": "execute", "sensitivity": "LOW"},

    # Git operations
    {"name": "git_status", "resource_type": "tool", "action": "read", "sensitivity": "LOW"},
    {"name": "git_log", "resource_type": "tool", "action": "read", "sensitivity": "LOW"},
    {"name": "git_diff", "resource_type": "tool", "action": "read", "sensitivity": "MEDIUM"},
    {"name": "git_add", "resource_type": "tool", "action": "write", "sensitivity": "MEDIUM"},
    {"name": "git_commit", "resource_type": "tool", "action": "write", "sensitivity": "HIGH"},

    # Web automation
    {"name": "web_screenshot", "resource_type": "tool", "action": "execute", "sensitivity": "LOW"},
    {"name": "web_scrape", "resource_type": "tool", "action": "execute", "sensitivity": "MEDIUM"},
    {"name": "web_analyze_ui", "resource_type": "tool", "action": "execute", "sensitivity": "LOW"},
    {"name": "web_automate", "resource_type": "tool", "action": "execute", "sensitivity": "HIGH"},

    # Notion integration
    {"name": "notion_create_page", "resource_type": "tool", "action": "write", "sensitivity": "MEDIUM"},
    {"name": "notion_search", "resource_type": "tool", "action": "read", "sensitivity": "LOW"},
    {"name": "web_to_notion", "resource_type": "tool", "action": "write", "sensitivity": "MEDIUM"},

    # Model management
    {"name": "switch_model", "resource_type": "tool", "action": "execute", "sensitivity": "HIGH"},
    {"name": "get_current_model", "resource_type": "tool", "action": "read", "sensitivity": "LOW"},
]

# Test users
TEST_USERS = [
    {"user_id": "guest_user", "username": "Guest User", "role_name": "guest"},
    {"user_id": "dev_user", "username": "Developer User", "role_name": "developer"},
    {"user_id": "admin_user", "username": "Admin User", "role_name": "admin"},
]


async def seed_permissions(db) -> Dict[str, int]:
    """
    Seed permissions and return mapping of permission_name -> permission_id

    Uses INSERT OR IGNORE for idempotency
    """
    permission_map = {}

    print("Seeding permissions...")
    async with db.get_connection() as conn:
        for perm in ALL_PERMISSIONS:
            # Insert with OR IGNORE (idempotent)
            await conn.execute(
                """
                INSERT OR IGNORE INTO security_permissions
                (permission_name, resource_type, action, sensitivity_level, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    perm["name"],
                    perm["resource_type"],
                    perm["action"],
                    perm["sensitivity"],
                    f"{perm['action'].capitalize()} permission for {perm['name']}"
                )
            )

            # Get permission_id (either newly inserted or existing)
            async with conn.execute(
                "SELECT permission_id FROM security_permissions WHERE permission_name = ?",
                (perm["name"],)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    permission_map[perm["name"]] = row[0]
                    print(f"  ✓ Permission ready: {perm['name']} (ID={row[0]})")

        await conn.commit()

    print(f"✅ {len(permission_map)} permissions ready\n")
    return permission_map


async def seed_roles(db, permission_map: Dict[str, int]) -> Dict[str, int]:
    """
    Seed roles and their permissions
    Returns mapping of role_name -> role_id

    Uses INSERT OR IGNORE for idempotency
    """
    role_map = {}

    print("Seeding roles...")
    async with db.get_connection() as conn:
        for role_config in DEFAULT_ROLES:
            # Insert with OR IGNORE
            await conn.execute(
                """
                INSERT OR IGNORE INTO security_roles (role_name, description, is_system_role)
                VALUES (?, ?, ?)
                """,
                (
                    role_config["role_name"],
                    role_config["description"],
                    role_config["is_system_role"]
                )
            )

            # Get role_id
            async with conn.execute(
                "SELECT role_id FROM security_roles WHERE role_name = ?",
                (role_config["role_name"],)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    role_id = row[0]
                    role_map[role_config["role_name"]] = role_id
                    print(f"  ✓ Role ready: {role_config['role_name']} (ID={role_id})")

            # Clear existing role-permission mappings for idempotency
            await conn.execute(
                "DELETE FROM security_role_permissions WHERE role_id = ?",
                (role_id,)
            )

            # Insert role-permission mappings
            for perm_name in role_config["permissions"]:
                if perm_name in permission_map:
                    perm_id = permission_map[perm_name]
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO security_role_permissions (role_id, permission_id)
                        VALUES (?, ?)
                        """,
                        (role_id, perm_id)
                    )
                else:
                    print(f"  ⚠️  Unknown permission: {perm_name}")

            print(f"    → {len(role_config['permissions'])} permissions assigned")

        await conn.commit()

    print(f"✅ {len(role_map)} roles ready\n")
    return role_map


async def seed_users(db, role_map: Dict[str, int]) -> None:
    """
    Seed test users

    Uses INSERT OR REPLACE for idempotency
    """
    print("Seeding test users...")
    async with db.get_connection() as conn:
        for user in TEST_USERS:
            role_id = role_map.get(user["role_name"])
            if not role_id:
                print(f"  ⚠️  Unknown role for user {user['user_id']}: {user['role_name']}")
                continue

            # INSERT OR REPLACE (upsert)
            await conn.execute(
                """
                INSERT OR REPLACE INTO security_users (user_id, username, role_id)
                VALUES (?, ?, ?)
                """,
                (user["user_id"], user["username"], role_id)
            )
            print(f"  ✓ User ready: {user['user_id']} ({user['role_name']})")

        await conn.commit()

    print(f"✅ {len(TEST_USERS)} test users ready\n")


async def reset_database(db) -> None:
    """Reset database (delete all data)"""
    print("⚠️  Resetting database (deleting all data)...")

    async with db.get_connection() as conn:
        # Delete in correct order (respecting foreign keys)
        await conn.execute("DELETE FROM security_role_permissions")
        await conn.execute("DELETE FROM security_audit_logs")
        await conn.execute("DELETE FROM security_sessions")
        await conn.execute("DELETE FROM security_users")
        await conn.execute("DELETE FROM security_permissions")
        await conn.execute("DELETE FROM security_roles")
        await conn.commit()

    print("✅ Database reset complete\n")


async def verify_seeding(db) -> None:
    """Verify seeded data"""
    print("Verifying seeded data...")

    async with db.get_connection() as conn:
        # Count roles
        async with conn.execute("SELECT COUNT(*) FROM security_roles") as cursor:
            role_count = (await cursor.fetchone())[0]

        # Count permissions
        async with conn.execute("SELECT COUNT(*) FROM security_permissions") as cursor:
            perm_count = (await cursor.fetchone())[0]

        # Count users
        async with conn.execute("SELECT COUNT(*) FROM security_users") as cursor:
            user_count = (await cursor.fetchone())[0]

        # Count role-permission mappings
        async with conn.execute("SELECT COUNT(*) FROM security_role_permissions") as cursor:
            mapping_count = (await cursor.fetchone())[0]

    print(f"  Roles: {role_count}")
    print(f"  Permissions: {perm_count}")
    print(f"  Users: {user_count}")
    print(f"  Role-Permission Mappings: {mapping_count}")
    print()

    # Test permission check
    result, reason = await db.check_permission("dev_user", "execute_python")
    print(f"Test query: dev_user can execute_python? {result} ({reason})")

    result, reason = await db.check_permission("guest_user", "execute_python")
    print(f"Test query: guest_user can execute_python? {result} ({reason})")

    print("\n✅ Verification complete!")


async def main():
    parser = argparse.ArgumentParser(description="Seed security database with default data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before seeding (DELETE ALL DATA)"
    )

    args = parser.parse_args()

    # Initialize database
    await init_database()
    db = get_security_database()

    # Reset if requested
    if args.reset:
        await reset_database(db)

    # Seed data
    permission_map = await seed_permissions(db)
    role_map = await seed_roles(db, permission_map)
    await seed_users(db, role_map)

    # Verify
    await verify_seeding(db)


if __name__ == "__main__":
    asyncio.run(main())
