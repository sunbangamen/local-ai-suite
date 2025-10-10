#!/usr/bin/env python3
"""
Approval CLI Tool
관리자가 대기 중인 승인 요청을 조회하고 승인/거부하는 CLI 도구

Usage:
    python scripts/approval_cli.py
    python scripts/approval_cli.py --continuous  # 지속적으로 실행
"""

import asyncio
import aiosqlite
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich import box

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "mcp-server"))

# DB 경로 설정
DEFAULT_DB_PATH = Path("/mnt/e/ai-data/sqlite/security.db")

console = Console()


async def get_pending_requests(db_path: Path, limit: int = 20):
    """대기 중인 승인 요청 조회"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                request_id,
                tool_name,
                user_id,
                role,
                request_data,
                requested_at,
                expires_at,
                CAST((julianday(expires_at) - julianday('now')) * 86400 AS INTEGER) AS seconds_left
            FROM approval_requests
            WHERE status = 'pending' AND datetime('now') < expires_at
            ORDER BY requested_at ASC
            LIMIT ?
        """, (limit,))
        requests = await cursor.fetchall()
        return [dict(row) for row in requests]


async def approve_request(db_path: Path, request_id: str, responder_id: str, reason: str):
    """승인 요청 승인 (with audit logging)"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # 요청 정보 조회
        cursor = await db.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?",
            (request_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Request not found"

        request_data = dict(row)
        if request_data['status'] != 'pending':
            return False, f"Request already {request_data['status']}"

        # 승인 처리
        await db.execute("""
            UPDATE approval_requests
            SET status = 'approved',
                responder_id = ?,
                response_reason = ?,
                responded_at = datetime('now')
            WHERE request_id = ? AND status = 'pending'
        """, (responder_id, reason, request_id))
        await db.commit()

        # 감사 로그 기록
        try:
            await db.execute("""
                INSERT INTO security_audit_logs (
                    user_id, tool_name, action, status,
                    error_message, execution_time_ms, request_data, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                request_data['user_id'],
                request_data['tool_name'],
                'approval_granted',
                'approved',
                None,
                None,
                json.dumps({
                    "request_id": request_id,
                    "responder_id": responder_id,
                    "reason": reason
                }),
            ))
            await db.commit()
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to log approval: {e}[/yellow]")

        return True, "Approved successfully"


async def reject_request(db_path: Path, request_id: str, responder_id: str, reason: str):
    """승인 요청 거부 (with audit logging)"""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # 요청 정보 조회
        cursor = await db.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?",
            (request_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Request not found"

        request_data = dict(row)
        if request_data['status'] != 'pending':
            return False, f"Request already {request_data['status']}"

        # 거부 처리
        await db.execute("""
            UPDATE approval_requests
            SET status = 'rejected',
                responder_id = ?,
                response_reason = ?,
                responded_at = datetime('now')
            WHERE request_id = ? AND status = 'pending'
        """, (responder_id, reason, request_id))
        await db.commit()

        # 감사 로그 기록
        try:
            await db.execute("""
                INSERT INTO security_audit_logs (
                    user_id, tool_name, action, status,
                    error_message, execution_time_ms, request_data, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                request_data['user_id'],
                request_data['tool_name'],
                'approval_rejected',
                'rejected',
                reason,  # rejection reason as error_message
                None,
                json.dumps({
                    "request_id": request_id,
                    "responder_id": responder_id
                }),
            ))
            await db.commit()
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to log rejection: {e}[/yellow]")

        return True, "Rejected successfully"


def display_requests(requests):
    """승인 요청 목록을 Rich Table로 표시"""
    if not requests:
        console.print("[yellow]No pending approval requests[/yellow]")
        return {}, None

    table = Table(title="Pending Approval Requests", box=box.ROUNDED)
    table.add_column("Short ID", style="cyan", no_wrap=True)
    table.add_column("Tool", style="magenta")
    table.add_column("User", style="green")
    table.add_column("Role", style="blue")
    table.add_column("Requested", style="yellow")
    table.add_column("Expires In", style="red")

    short_id_map = {}
    for req in requests:
        request_id = req['request_id']
        short_id = request_id[:8]

        # 중복 short ID 체크
        if short_id in short_id_map and short_id_map[short_id] != request_id:
            console.print(f"[red]Warning: Duplicate Short ID detected ({short_id}). Using full UUID.[/red]")
            short_id = request_id
        short_id_map[short_id] = request_id

        # 시간 포맷팅
        requested_at = req['requested_at']
        seconds_left = req['seconds_left']
        if seconds_left > 60:
            expires_in = f"{seconds_left // 60}m {seconds_left % 60}s"
        else:
            expires_in = f"{seconds_left}s"

        table.add_row(
            short_id,
            req['tool_name'],
            req['user_id'],
            req['role'],
            requested_at.split('.')[0],  # Remove microseconds
            expires_in
        )

    console.print(table)
    return short_id_map, requests


async def interactive_mode(db_path: Path, responder_id: str):
    """대화형 모드로 승인 처리"""
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold green]Approval Workflow CLI[/bold green]\n"
            f"DB: {db_path}\n"
            f"Responder: {responder_id}",
            border_style="green"
        ))

        # 대기 중인 요청 조회
        requests = await get_pending_requests(db_path)
        short_id_map, request_list = display_requests(requests)

        if not requests:
            console.print("\n[yellow]No pending requests. Waiting for new requests...[/yellow]")
            if not Confirm.ask("Continue monitoring?", default=True):
                break
            await asyncio.sleep(5)
            continue

        # 사용자 입력
        console.print("\n[bold]Actions:[/bold]")
        console.print("  [cyan]Enter Short ID[/cyan] - Process specific request")
        console.print("  [cyan]r[/cyan] - Refresh")
        console.print("  [cyan]q[/cyan] - Quit")

        choice = Prompt.ask("\nYour choice", default="r")

        if choice == 'q':
            console.print("[yellow]Exiting...[/yellow]")
            break

        if choice == 'r':
            continue

        # 요청 처리
        full_request_id = short_id_map.get(choice, choice)
        if full_request_id not in short_id_map.values():
            console.print(f"[red]Invalid request ID: {choice}[/red]")
            await asyncio.sleep(2)
            continue

        # 요청 상세 정보 표시
        selected_req = next((r for r in request_list if r['request_id'] == full_request_id), None)
        if selected_req:
            console.print(Panel(
                f"[bold]Request Details[/bold]\n\n"
                f"ID: {selected_req['request_id']}\n"
                f"Tool: {selected_req['tool_name']}\n"
                f"User: {selected_req['user_id']}\n"
                f"Role: {selected_req['role']}\n"
                f"Requested: {selected_req['requested_at']}\n"
                f"Data: {selected_req['request_data'][:100]}...",
                border_style="cyan"
            ))

        # 승인/거부 선택
        action = Prompt.ask("Action", choices=["approve", "reject", "skip"], default="skip")

        if action == "skip":
            continue

        reason = Prompt.ask("Reason")

        # 처리 실행
        if action == "approve":
            success, message = await approve_request(db_path, full_request_id, responder_id, reason)
        else:
            success, message = await reject_request(db_path, full_request_id, responder_id, reason)

        if success:
            console.print(f"[green]✓ {message}[/green]")
        else:
            console.print(f"[red]✗ {message}[/red]")

        await asyncio.sleep(1)


async def single_run(db_path: Path):
    """한 번만 실행하고 종료"""
    requests = await get_pending_requests(db_path)
    display_requests(requests)


async def main():
    parser = argparse.ArgumentParser(description="Approval Workflow CLI")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Database path")
    parser.add_argument("--responder", type=str, default="cli_admin", help="Responder ID")
    parser.add_argument("--continuous", action="store_true", help="Run in continuous mode")
    parser.add_argument("--list-only", action="store_true", help="List requests and exit")

    args = parser.parse_args()
    db_path = Path(args.db)

    # DB 존재 확인
    if not db_path.exists():
        console.print(f"[red]Error: Database not found at {db_path}[/red]")
        sys.exit(1)

    try:
        if args.list_only:
            await single_run(db_path)
        else:
            await interactive_mode(db_path, args.responder)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
