#!/usr/bin/env python3
"""
Memory Database Schema Migration Script

이전 스키마의 메모리 DB를 최신 구조로 업그레이드합니다.
주요 변경 사항:
- conversation_embeddings 테이블에 id 컬럼 추가
- sync_status, synced_at 컬럼 추가
- qdrant_point_id 컬럼 추가

사용법:
    python scripts/migrate_memory_schema.py [--dry-run] [--project PROJECT_ID]

    --dry-run: 실제 변경 없이 마이그레이션 계획만 출력
    --project: 특정 프로젝트만 마이그레이션 (없으면 전체)
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# 메모리 디렉토리 경로
AI_MEMORY_DIR = os.getenv('AI_MEMORY_DIR', '/mnt/e/ai-data/memory')
PROJECTS_DIR = Path(AI_MEMORY_DIR) / 'projects'


def check_schema_version(db_path: Path) -> Tuple[bool, str]:
    """
    데이터베이스 스키마 버전 확인

    Returns:
        (needs_migration, reason)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # conversation_embeddings 테이블 구조 확인
        cursor.execute("PRAGMA table_info(conversation_embeddings)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        conn.close()

        # 필수 컬럼 확인
        required_columns = {
            'id': 'INTEGER',
            'conversation_id': 'INTEGER',
            'embedding_vector': 'BLOB',
            'sync_status': 'TEXT',
            'synced_at': 'TEXT',
            'qdrant_point_id': 'TEXT',
            'created_at': 'DATETIME'
        }

        missing_columns = []
        for col_name, col_type in required_columns.items():
            if col_name not in columns:
                missing_columns.append(col_name)

        if missing_columns:
            return True, f"누락된 컬럼: {', '.join(missing_columns)}"

        return False, "스키마가 최신 상태입니다"

    except Exception as e:
        return False, f"스키마 확인 오류: {str(e)}"


def migrate_database(db_path: Path, dry_run: bool = False) -> bool:
    """
    데이터베이스 스키마 마이그레이션 실행

    Args:
        db_path: 마이그레이션할 DB 파일 경로
        dry_run: True면 실제 변경하지 않음

    Returns:
        성공 여부
    """
    try:
        # 백업 생성
        if not dry_run:
            backup_path = db_path.parent / f"{db_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"  ✅ 백업 생성됨: {backup_path.name}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 현재 스키마 확인
        cursor.execute("PRAGMA table_info(conversation_embeddings)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        migrations = []

        # 1. id 컬럼이 없으면 추가 (PRIMARY KEY로 재생성 필요)
        if 'id' not in existing_columns:
            migrations.append("id PRIMARY KEY로 테이블 재생성")

            if not dry_run:
                # 기존 데이터 백업
                cursor.execute("""
                    CREATE TABLE conversation_embeddings_old AS
                    SELECT * FROM conversation_embeddings
                """)

                # 새 테이블 생성
                cursor.execute("DROP TABLE conversation_embeddings")
                cursor.execute("""
                    CREATE TABLE conversation_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id INTEGER NOT NULL,
                        embedding_vector BLOB NOT NULL,
                        sync_status TEXT DEFAULT 'pending',
                        synced_at TEXT,
                        qdrant_point_id TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                    )
                """)

                # 데이터 복원 (embedding_vector가 NULL인 행은 제외)
                cursor.execute("""
                    INSERT INTO conversation_embeddings
                    (conversation_id, embedding_vector, created_at)
                    SELECT conversation_id, embedding_vector,
                           COALESCE(created_at, CURRENT_TIMESTAMP)
                    FROM conversation_embeddings_old
                    WHERE embedding_vector IS NOT NULL
                """)

                cursor.execute("DROP TABLE conversation_embeddings_old")

        else:
            # id 컬럼이 있으면 개별 컬럼 추가
            if 'sync_status' not in existing_columns:
                migrations.append("sync_status 컬럼 추가")
                if not dry_run:
                    cursor.execute("""
                        ALTER TABLE conversation_embeddings
                        ADD COLUMN sync_status TEXT DEFAULT 'pending'
                    """)

            if 'synced_at' not in existing_columns:
                migrations.append("synced_at 컬럼 추가")
                if not dry_run:
                    cursor.execute("""
                        ALTER TABLE conversation_embeddings
                        ADD COLUMN synced_at TEXT
                    """)

            if 'qdrant_point_id' not in existing_columns:
                migrations.append("qdrant_point_id 컬럼 추가")
                if not dry_run:
                    cursor.execute("""
                        ALTER TABLE conversation_embeddings
                        ADD COLUMN qdrant_point_id TEXT
                    """)

        # 인덱스 생성
        if not dry_run:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_conversation
                ON conversation_embeddings(conversation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_sync_status
                ON conversation_embeddings(sync_status)
            """)

        if not dry_run:
            conn.commit()
            print(f"  ✅ 마이그레이션 적용됨: {', '.join(migrations)}")
        else:
            print(f"  📋 적용될 변경사항: {', '.join(migrations)}")

        conn.close()
        return True

    except Exception as e:
        print(f"  ❌ 마이그레이션 실패: {str(e)}")
        if not dry_run:
            conn.rollback()
        return False


def find_memory_databases() -> List[Path]:
    """메모리 데이터베이스 파일 목록 반환"""
    if not PROJECTS_DIR.exists():
        print(f"❌ 프로젝트 디렉토리를 찾을 수 없습니다: {PROJECTS_DIR}")
        return []

    databases = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            db_path = project_dir / 'memory.db'
            if db_path.exists():
                databases.append(db_path)

    return sorted(databases)


def main():
    parser = argparse.ArgumentParser(
        description='메모리 데이터베이스 스키마를 최신 버전으로 마이그레이션'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 변경 없이 마이그레이션 대상만 표시'
    )
    parser.add_argument(
        '--project',
        type=str,
        help='특정 프로젝트 ID만 마이그레이션'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("메모리 데이터베이스 스키마 마이그레이션")
    print("=" * 60)
    print()

    if args.dry_run:
        print("🔍 DRY RUN 모드 - 실제 변경 없이 확인만 수행합니다\n")

    # 데이터베이스 목록 가져오기
    databases = find_memory_databases()

    if args.project:
        databases = [db for db in databases if args.project in str(db)]
        if not databases:
            print(f"❌ 프로젝트의 데이터베이스를 찾을 수 없습니다: {args.project}")
            return 1

    if not databases:
        print("❌ 메모리 데이터베이스를 찾을 수 없습니다")
        return 1

    print(f"{len(databases)}개의 데이터베이스를 발견했습니다\n")

    # 마이그레이션 필요 여부 확인
    to_migrate = []
    up_to_date = []

    for db_path in databases:
        project_id = db_path.parent.name
        needs_migration, reason = check_schema_version(db_path)

        if needs_migration:
            to_migrate.append((db_path, project_id, reason))
        else:
            up_to_date.append((db_path, project_id))

    # 결과 출력
    if up_to_date:
        print(f"✅ 최신 상태 ({len(up_to_date)}개):")
        for db_path, project_id in up_to_date:
            print(f"   • {project_id}")
        print()

    if to_migrate:
        print(f"🔄 마이그레이션 필요 ({len(to_migrate)}개):")
        for db_path, project_id, reason in to_migrate:
            print(f"   • {project_id}: {reason}")
        print()

        # 마이그레이션 실행
        if not args.dry_run:
            confirm = input("마이그레이션을 진행하시겠습니까? [y/N]: ")
            if confirm.lower() != 'y':
                print("❌ 마이그레이션이 취소되었습니다")
                return 0
            print()

        success_count = 0
        for db_path, project_id, reason in to_migrate:
            print(f"{project_id} 마이그레이션 중...")
            if migrate_database(db_path, args.dry_run):
                success_count += 1
            print()

        print("=" * 60)
        if args.dry_run:
            print(f"📋 {len(to_migrate)}개의 데이터베이스가 마이그레이션될 예정입니다")
        else:
            print(f"✅ {success_count}/{len(to_migrate)}개의 데이터베이스 마이그레이션 완료")

        if success_count < len(to_migrate):
            print(f"⚠️  실패: {len(to_migrate) - success_count}개")
            return 1
    else:
        print("✅ 모든 데이터베이스가 최신 상태입니다!")

    return 0


if __name__ == '__main__':
    sys.exit(main())