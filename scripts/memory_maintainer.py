#!/usr/bin/env python3
"""
Memory Maintainer Service
메모리 시스템 유지보수 서비스 - TTL 정리, 백업 생성, Qdrant 동기화
"""

import os
import sys
import time
import json
import logging
import sqlite3
import schedule
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import requests
from concurrent.futures import ThreadPoolExecutor

# 환경변수
AI_MEMORY_DIR = os.getenv('AI_MEMORY_DIR', '/mnt/e/ai-data/memory')
QDRANT_URL = os.getenv('QDRANT_URL', 'http://qdrant:6333')
EMBEDDING_URL = os.getenv('EMBEDDING_URL', 'http://embedding:8003')
MEMORY_BACKUP_CRON = os.getenv('MEMORY_BACKUP_CRON', '03:00')  # 새벽 3시
MEMORY_SYNC_INTERVAL = int(os.getenv('MEMORY_SYNC_INTERVAL', '300'))  # 5분
TTL_CHECK_INTERVAL = int(os.getenv('TTL_CHECK_INTERVAL', '3600'))  # 1시간

# 로깅 설정
log_dir = Path(AI_MEMORY_DIR) / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'memory_maintainer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MemoryMaintainer:
    """메모리 시스템 유지보수 관리자"""

    def __init__(self):
        self.memory_dir = Path(AI_MEMORY_DIR)
        self.backup_dir = self.memory_dir / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Memory Maintainer 시작 - 메모리 디렉토리: {self.memory_dir}")

    def find_memory_databases(self) -> List[Path]:
        """모든 프로젝트의 memory.db 파일 찾기"""
        memory_dbs = []

        # projects 디렉토리 확인 및 생성
        projects_dir = self.memory_dir / 'projects'
        projects_dir.mkdir(parents=True, exist_ok=True)

        # 프로젝트별 메모리 DB 검색 (projects 디렉토리 하위에서)
        for project_dir in projects_dir.glob('*/'):
            if project_dir.is_dir():
                memory_db = project_dir / 'memory.db'
                if memory_db.exists():
                    memory_dbs.append(memory_db)

        logger.info(f"발견된 메모리 DB: {len(memory_dbs)}개 (경로: {projects_dir})")
        return memory_dbs

    def cleanup_expired_conversations(self, db_path: Path) -> int:
        """TTL 기반 만료된 대화 정리"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # TTL 기반 삭제
            cursor.execute("""
                DELETE FROM conversations
                WHERE expires_at IS NOT NULL
                AND expires_at < ?
            """, (datetime.now().isoformat(),))

            deleted_count = cursor.rowcount

            # 고아 임베딩 정리
            cursor.execute("""
                DELETE FROM conversation_embeddings
                WHERE conversation_id NOT IN (
                    SELECT id FROM conversations
                )
            """)

            conn.commit()
            conn.close()

            if deleted_count > 0:
                logger.info(f"TTL 정리 완료 - {db_path.parent.name}: {deleted_count}개 대화 삭제")

            return deleted_count

        except Exception as e:
            logger.error(f"TTL 정리 실패 - {db_path}: {e}")
            return 0

    def backup_memory_database(self, db_path: Path) -> Optional[Path]:
        """메모리 DB 백업 생성"""
        try:
            project_name = db_path.parent.name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # SQL 덤프 백업
            backup_sql = self.backup_dir / f"{project_name}_{timestamp}.sql"

            conn = sqlite3.connect(db_path)
            with open(backup_sql, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            conn.close()

            # JSON 백업 (검색 가능한 형태)
            backup_json = self.backup_dir / f"{project_name}_{timestamp}.json"
            self.export_memory_to_json(db_path, backup_json)

            logger.info(f"백업 완료 - {project_name}: {backup_sql.name}, {backup_json.name}")
            return backup_sql

        except Exception as e:
            logger.error(f"백업 실패 - {db_path}: {e}")
            return None

    def export_memory_to_json(self, db_path: Path, output_path: Path):
        """메모리 DB를 JSON으로 내보내기"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        export_data = {
            "export_time": datetime.now().isoformat(),
            "project": db_path.parent.name,
            "conversations": [],
            "embeddings": []
        }

        # 대화 데이터
        cursor.execute("SELECT * FROM conversations ORDER BY created_at DESC")
        for row in cursor.fetchall():
            export_data["conversations"].append(dict(row))

        # 임베딩 데이터
        cursor.execute("SELECT * FROM conversation_embeddings")
        for row in cursor.fetchall():
            export_data["embeddings"].append(dict(row))

        conn.close()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def sync_to_qdrant(self, db_path: Path) -> int:
        """Qdrant와 동기화 - 미동기화 임베딩 업로드"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 동기화 필요한 임베딩 조회
            cursor.execute("""
                SELECT ce.*, c.content, c.model_type, c.importance_score
                FROM conversation_embeddings ce
                JOIN conversations c ON ce.conversation_id = c.id
                WHERE ce.sync_status != 'synced'
                OR ce.sync_status IS NULL
                LIMIT 100
            """)

            pending_items = cursor.fetchall()
            synced_count = 0

            if not pending_items:
                return 0

            project_name = db_path.parent.name
            collection_name = f"memory_{project_name}"

            # Qdrant 컬렉션 확인/생성
            self.ensure_qdrant_collection(collection_name)

            for item in pending_items:
                try:
                    # Qdrant에 벡터 업로드
                    payload = {
                        "conversation_id": item[1],
                        "content": item[7],
                        "model_type": item[8],
                        "importance_score": item[9] or 0,
                        "created_at": item[3]
                    }

                    # 임베딩이 JSON 문자열인 경우 파싱
                    embedding_vector = json.loads(item[2]) if isinstance(item[2], str) else item[2]

                    point_data = {
                        "id": item[0],  # embedding_id
                        "vector": embedding_vector,
                        "payload": payload
                    }

                    response = requests.put(
                        f"{QDRANT_URL}/collections/{collection_name}/points",
                        json={"points": [point_data]},
                        timeout=30
                    )

                    if response.status_code == 200:
                        # 동기화 상태 업데이트
                        cursor.execute("""
                            UPDATE conversation_embeddings
                            SET sync_status = 'synced', synced_at = ?
                            WHERE id = ?
                        """, (datetime.now().isoformat(), item[0]))
                        synced_count += 1
                    else:
                        logger.warning(f"Qdrant 업로드 실패 - ID {item[0]}: {response.status_code}")

                except Exception as e:
                    logger.error(f"임베딩 동기화 실패 - ID {item[0]}: {e}")
                    cursor.execute("""
                        UPDATE conversation_embeddings
                        SET sync_status = 'failed'
                        WHERE id = ?
                    """, (item[0],))

            conn.commit()
            conn.close()

            if synced_count > 0:
                logger.info(f"Qdrant 동기화 완료 - {project_name}: {synced_count}개 벡터")

            return synced_count

        except Exception as e:
            logger.error(f"Qdrant 동기화 실패 - {db_path}: {e}")
            return 0

    def ensure_qdrant_collection(self, collection_name: str):
        """Qdrant 컬렉션 존재 확인 및 생성"""
        try:
            # 컬렉션 존재 확인
            response = requests.get(f"{QDRANT_URL}/collections/{collection_name}")

            if response.status_code == 404:
                # 컬렉션 생성
                create_data = {
                    "vectors": {
                        "size": 384,  # BAAI/bge-small-en-v1.5 차원
                        "distance": "Cosine"
                    }
                }

                response = requests.put(
                    f"{QDRANT_URL}/collections/{collection_name}",
                    json=create_data
                )

                if response.status_code == 200:
                    logger.info(f"Qdrant 컬렉션 생성 완료: {collection_name}")
                else:
                    logger.error(f"Qdrant 컬렉션 생성 실패: {collection_name}")

        except Exception as e:
            logger.error(f"Qdrant 컬렉션 확인/생성 실패: {e}")

    def cleanup_old_backups(self, days: int = 30):
        """오래된 백업 파일 정리"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0

            for backup_file in self.backup_dir.glob('*'):
                if backup_file.is_file():
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1

            if deleted_count > 0:
                logger.info(f"오래된 백업 정리 완료: {deleted_count}개 파일 삭제")

        except Exception as e:
            logger.error(f"백업 정리 실패: {e}")

    def run_ttl_cleanup(self):
        """TTL 정리 작업 실행"""
        logger.info("TTL 정리 작업 시작")

        memory_dbs = self.find_memory_databases()
        total_deleted = 0

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.cleanup_expired_conversations, db) for db in memory_dbs]
            for future in futures:
                total_deleted += future.result()

        logger.info(f"TTL 정리 작업 완료 - 총 {total_deleted}개 대화 삭제")

    def run_qdrant_sync(self):
        """Qdrant 동기화 작업 실행"""
        logger.info("Qdrant 동기화 작업 시작")

        memory_dbs = self.find_memory_databases()
        sync_stats = {"synced": 0, "failed": 0, "skipped": 0}

        for db_path in memory_dbs:
            try:
                # 프로젝트 ID 추출 (db 경로에서)
                project_id = db_path.parent.name

                # memory_system의 컬렉션 확인
                from memory_system import get_memory_system
                memory_system = get_memory_system()

                if not memory_system.ensure_memory_collection(project_id):
                    logger.warning(f"프로젝트 {project_id} Qdrant 컬렉션 생성 실패, 스킵")
                    sync_stats["skipped"] += 1
                    continue

                # 동기화 실행
                synced_count = self.sync_to_qdrant(db_path)
                sync_stats["synced"] += synced_count

            except Exception as e:
                logger.error(f"프로젝트 {db_path.parent.name} 동기화 실패: {e}")
                sync_stats["failed"] += 1

        logger.info(f"Qdrant 동기화 작업 완료 - 동기화: {sync_stats['synced']}, 실패: {sync_stats['failed']}, 스킵: {sync_stats['skipped']}")

        # 실패한 동기화가 있으면 15분 후 재시도 스케줄링
        if sync_stats["failed"] > 0:
            self.schedule_retry_sync()

    def schedule_retry_sync(self):
        """실패한 동기화 재시도 스케줄링"""
        import schedule

        def retry_sync():
            logger.info("실패한 동기화 재시도 시작")
            from memory_system import get_memory_system
            memory_system = get_memory_system()

            # 모든 프로젝트의 실패한 동기화 재시도
            memory_dbs = self.find_memory_databases()
            retry_stats = {"retried": 0, "succeeded": 0}

            for db_path in memory_dbs:
                try:
                    project_id = db_path.parent.name
                    stats = memory_system.retry_failed_syncs(project_id)
                    retry_stats["retried"] += stats.get("retried", 0)
                    retry_stats["succeeded"] += stats.get("succeeded", 0)
                except Exception as e:
                    logger.error(f"재시도 실패 {project_id}: {e}")

            logger.info(f"재시도 완료 - 시도: {retry_stats['retried']}, 성공: {retry_stats['succeeded']}")

        # 15분 후 한 번만 실행
        schedule.every(15).minutes.do(retry_sync).tag("retry_sync")
        logger.info("실패한 동기화 재시도가 15분 후 스케줄링됨")

    def run_backup(self):
        """백업 작업 실행"""
        logger.info("백업 작업 시작")

        memory_dbs = self.find_memory_databases()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.backup_memory_database, db) for db in memory_dbs]
            for future in futures:
                future.result()

        # 오래된 백업 정리
        self.cleanup_old_backups()

        logger.info("백업 작업 완료")

    def health_check(self) -> Dict:
        """헬스체크 정보 반환"""
        memory_dbs = self.find_memory_databases()

        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "memory_databases": len(memory_dbs),
            "services": {
                "qdrant": self.check_qdrant_health(),
                "embedding": self.check_embedding_health()
            }
        }

        return health_info

    def check_qdrant_health(self) -> bool:
        """Qdrant 서비스 상태 확인"""
        try:
            response = requests.get(f"{QDRANT_URL}/", timeout=5)
            return response.status_code == 200
        except:
            return False

    def check_embedding_health(self) -> bool:
        """임베딩 서비스 상태 확인"""
        try:
            response = requests.get(f"{EMBEDDING_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

def main():
    """메인 실행 함수"""
    maintainer = MemoryMaintainer()

    # 스케줄 설정
    schedule.every(TTL_CHECK_INTERVAL).seconds.do(maintainer.run_ttl_cleanup)
    schedule.every(MEMORY_SYNC_INTERVAL).seconds.do(maintainer.run_qdrant_sync)
    schedule.every().day.at(MEMORY_BACKUP_CRON).do(maintainer.run_backup)

    logger.info("Memory Maintainer 스케줄 시작")
    logger.info(f"TTL 정리: {TTL_CHECK_INTERVAL}초마다")
    logger.info(f"Qdrant 동기화: {MEMORY_SYNC_INTERVAL}초마다")
    logger.info(f"백업: 매일 {MEMORY_BACKUP_CRON}")

    # 초기 헬스체크
    health = maintainer.health_check()
    logger.info(f"초기 헬스체크: {health}")

    # 메인 루프
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 스케줄 확인

    except KeyboardInterrupt:
        logger.info("Memory Maintainer 종료")
    except Exception as e:
        logger.error(f"Memory Maintainer 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()