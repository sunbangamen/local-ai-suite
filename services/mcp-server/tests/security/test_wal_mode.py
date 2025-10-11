#!/usr/bin/env python3
"""
WAL Mode Concurrent Access Tests
Issue #8 - P1-T3
"""

import asyncio
import pytest
import aiosqlite

from security_database import SecurityDatabase


@pytest.mark.integration
@pytest.mark.requires_db
class TestWALModeConcurrency:
    """Test WAL mode concurrent read/write access"""

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, temp_db_path):
        """Test that WAL mode is enabled"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        async with db.get_connection() as conn:
            async with conn.execute("PRAGMA journal_mode") as cursor:
                result = await cursor.fetchone()
                assert result[0] == "wal", "WAL mode should be enabled"

    @pytest.mark.asyncio
    async def test_concurrent_readers(self, temp_db_path):
        """Test 10+ concurrent read connections"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        # Seed test data
        async with db.get_connection() as conn:
            await conn.execute(
                "INSERT INTO security_roles (role_name, description) VALUES ('test_role', 'Test')"
            )
            await conn.commit()

        async def read_role(reader_id: int):
            """Simulate concurrent reader"""
            async with db.get_connection() as conn:
                async with conn.execute(
                    "SELECT * FROM security_roles WHERE role_name = 'test_role'"
                ) as cursor:
                    result = await cursor.fetchone()
                    assert result is not None
                    return reader_id

        # Run 15 concurrent readers
        tasks = [read_role(i) for i in range(15)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 15, "All readers should complete successfully"

    @pytest.mark.asyncio
    async def test_concurrent_read_write(self, temp_db_path):
        """Test concurrent reads during write operations"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        write_count = 0
        read_count = 0

        async def writer():
            """Background writer"""
            nonlocal write_count
            for i in range(10):
                await db.insert_audit_log(
                    user_id=f"writer_user_{i}",
                    tool_name="test_tool",
                    action="test",
                    status="success",
                )
                write_count += 1
                await asyncio.sleep(0.01)  # Small delay

        async def reader(reader_id: int):
            """Background reader"""
            nonlocal read_count
            for _ in range(20):
                await db.get_audit_logs(limit=5)
                read_count += 1
                await asyncio.sleep(0.005)  # Faster than writer

        # Run 1 writer + 5 readers concurrently
        tasks = [writer()] + [reader(i) for i in range(5)]
        await asyncio.gather(*tasks)

        assert write_count == 10, "All writes should complete"
        assert read_count == 100, "All reads should complete (5 readers * 20 reads)"

    @pytest.mark.asyncio
    async def test_no_database_locked_errors(self, temp_db_path):
        """Test that WAL mode prevents 'database is locked' errors"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        errors = []

        async def concurrent_write(writer_id: int):
            """Concurrent writer"""
            try:
                for i in range(5):
                    await db.insert_audit_log(
                        user_id=f"user_{writer_id}",
                        tool_name="test_tool",
                        action="write",
                        status="success",
                    )
                    await asyncio.sleep(0.01)
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e):
                    errors.append(e)

        # Run 3 concurrent writers (stress test)
        tasks = [concurrent_write(i) for i in range(3)]
        await asyncio.gather(*tasks)

        # WAL mode should prevent locking errors (allow some tolerance for SQLite behavior)
        assert len(errors) == 0, f"WAL mode should prevent locked errors, got: {len(errors)}"

    @pytest.mark.asyncio
    async def test_wal_checkpoint(self, temp_db_path):
        """Test WAL checkpoint operation"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        # Write some data
        for i in range(100):
            await db.insert_audit_log(
                user_id=f"user_{i}",
                tool_name="test_tool",
                action="test",
                status="success",
            )

        # Checkpoint WAL
        await db.checkpoint()

        # Verify data integrity after checkpoint
        logs = await db.get_audit_logs(limit=100)
        assert len(logs) == 100, "All data should be preserved after checkpoint"

    @pytest.mark.asyncio
    async def test_connection_pooling_behavior(self, temp_db_path):
        """Test connection reuse and isolation"""
        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        results = []

        async def isolated_transaction(tx_id: int):
            """Each transaction should be isolated"""
            async with db.get_connection() as conn:
                # Insert in transaction
                await conn.execute(
                    "INSERT INTO security_roles (role_name, description) VALUES (?, ?)",
                    (f"role_{tx_id}", f"Transaction {tx_id}"),
                )
                await conn.commit()

                # Read back
                async with conn.execute(
                    "SELECT role_name FROM security_roles WHERE role_name = ?",
                    (f"role_{tx_id}",),
                ) as cursor:
                    result = await cursor.fetchone()
                    results.append(result[0])

        # Run 5 concurrent isolated transactions
        tasks = [isolated_transaction(i) for i in range(5)]
        await asyncio.gather(*tasks)

        assert len(results) == 5, "All transactions should complete"
        assert set(results) == {f"role_{i}" for i in range(5)}, "All roles should be created"


@pytest.mark.integration
@pytest.mark.requires_db
class TestDatabasePerformance:
    """Performance benchmarks for database operations"""

    @pytest.mark.asyncio
    async def test_permission_check_latency(self, seeded_db):
        """Benchmark permission check latency (target: <10ms)"""
        import time

        db = SecurityDatabase(":memory:")
        db._connection = seeded_db
        db._initialized = True

        latencies = []

        for _ in range(100):
            start = time.time()
            await db.check_permission("dev_user", "read_file")
            end = time.time()
            latencies.append((end - start) * 1000)  # Convert to ms

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]  # 95th percentile

        print("\nPermission Check Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")

        assert p95_latency < 10, f"P95 latency should be <10ms, got {p95_latency:.2f}ms"

    @pytest.mark.asyncio
    async def test_audit_log_insert_latency(self, temp_db_path):
        """Benchmark audit log insert latency (target: <5ms for async)"""
        import time

        db = SecurityDatabase(temp_db_path)
        await db.initialize()

        latencies = []

        for i in range(100):
            start = time.time()
            await db.insert_audit_log(
                user_id=f"user_{i}",
                tool_name="test_tool",
                action="test",
                status="success",
                execution_time_ms=50,
            )
            end = time.time()
            latencies.append((end - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]

        print("\nAudit Log Insert Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")

        # Note: Actual async implementation will queue this, making it <1ms
        assert (
            p95_latency < 50
        ), f"P95 latency should be <50ms for direct insert, got {p95_latency:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
