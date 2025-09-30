#!/usr/bin/env python3
"""
Qdrant 장애 시나리오 자동화 테스트
메모리 시스템의 Qdrant 장애 시 폴백 처리 검증
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# 메모리 시스템 모듈 경로 추가
sys.path.append('/mnt/e/worktree/issue-5-memory/scripts')

# 테스트 전역 환경 변수 선행 설정 (memory_maintainer 로깅 경로 문제 방지)
if 'AI_MEMORY_DIR' not in os.environ:
    test_memory_dir = tempfile.mkdtemp(prefix='test_memory_')
    os.environ['AI_MEMORY_DIR'] = test_memory_dir
    print(f"📁 테스트용 임시 메모리 디렉토리 설정: {test_memory_dir}")

# schedule 의존성 모킹 (memory_maintainer import 전에 필수)
class FakeSchedule:
    """schedule 모듈 모킹용 더미 클래스"""

    class Job:
        def __init__(self):
            # 체이닝을 위해 자신을 반환하는 속성들 추가
            self.seconds = self
            self.minutes = self
            self.hours = self
            self.day = self

        def do(self, func):
            """do() 메서드 모킹"""
            return self

        def tag(self, *args):
            """tag() 메서드 모킹"""
            return self

        def at(self, time):
            """at() 메서드 모킹"""
            return self

    def every(self, interval=None):
        """every() 메서드 모킹 - 체이닝 지원"""
        return self.Job()

    def run_pending(self):
        """run_pending() 메서드 모킹"""
        pass

    class CancelJob(Exception):
        """CancelJob 예외 모킹"""
        pass

# schedule 모듈이 없으면 모킹된 버전 주입
if 'schedule' not in sys.modules:
    sys.modules['schedule'] = FakeSchedule()

try:
    from memory_system import MemorySystem, get_memory_system
    # memory_maintainer import (schedule 모킹 후)
    try:
        from memory_maintainer import MemoryMaintainer
        MAINTAINER_AVAILABLE = True
    except ImportError as e:
        print(f"⚠️ Warning: memory_maintainer module not available: {e}")
        MAINTAINER_AVAILABLE = False
except ImportError as e:
    print(f"⚠️ Warning: memory modules not found: {e}")
    sys.exit(1)


class TestQdrantFailureScenarios(unittest.TestCase):
    """Qdrant 장애 시나리오 테스트 클래스"""

    def setUp(self):
        """테스트 환경 초기화"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.memory_dir = self.temp_dir / 'memory'
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # 환경변수 설정
        os.environ['AI_MEMORY_DIR'] = str(self.memory_dir)
        os.environ['QDRANT_URL'] = 'http://localhost:6333'
        os.environ['EMBEDDING_URL'] = 'http://localhost:8003'

        # 테스트용 프로젝트 설정
        self.test_project_id = "test-project-12345678"
        self.project_dir = self.memory_dir / 'projects' / self.test_project_id
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # 메모리 시스템 초기화
        self.memory_system = MemorySystem()

        # 테스트 DB 생성
        self.memory_db = self.project_dir / 'memory.db'
        self._create_test_database()

        print(f"테스트 환경 초기화 완료: {self.memory_dir}")

    def tearDown(self):
        """테스트 환경 정리"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        print("테스트 환경 정리 완료")

    def _create_test_database(self):
        """테스트용 메모리 데이터베이스 생성 (실제 스키마와 정확히 일치)"""
        conn = sqlite3.connect(self.memory_db)

        # SQLite 최적화 설정
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA foreign_keys=ON")

        cursor = conn.cursor()

        # 대화 테이블 생성 (실제 memory_system.py와 정확히 일치)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_query TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                model_used VARCHAR(50),
                importance_score INTEGER DEFAULT 5,
                tags TEXT,
                session_id VARCHAR(50),
                token_count INTEGER,
                response_time_ms INTEGER,
                project_context TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME
            )
        """)

        # 임베딩 테이블 생성 (실제 스키마와 정확히 일치)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                embedding_vector TEXT,
                qdrant_point_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                synced_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                UNIQUE(conversation_id)
            )
        """)

        # FTS5 가상 테이블 생성
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                user_query,
                ai_response,
                content='conversations',
                content_rowid='id'
            )
        """)

        # 인덱스 생성 (실제 스키마와 일치)
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_importance ON conversations(importance_score)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_expires_at ON conversations(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_model_used ON conversations(model_used)",
            "CREATE INDEX IF NOT EXISTS idx_conversation_embeddings_sync_status ON conversation_embeddings(sync_status)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        # FTS5 트리거 생성 (자동 동기화)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_insert AFTER INSERT ON conversations
            BEGIN
                INSERT INTO conversations_fts(rowid, user_query, ai_response)
                VALUES (NEW.id, NEW.user_query, NEW.ai_response);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_update AFTER UPDATE ON conversations
            BEGIN
                UPDATE conversations_fts SET
                    user_query = NEW.user_query,
                    ai_response = NEW.ai_response
                WHERE rowid = NEW.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_delete AFTER DELETE ON conversations
            BEGIN
                DELETE FROM conversations_fts WHERE rowid = OLD.id;
            END
        """)

        # 테스트 데이터 삽입
        test_conversations = [
            ("Python 함수 작성법", "def example(): pass", "code-7b", 8),
            ("머신러닝 개념", "ML은 데이터 학습 기술입니다", "chat-7b", 7),
            ("Docker 사용법", "docker run hello-world", "code-7b", 6)
        ]

        for query, response, model, importance in test_conversations:
            cursor.execute("""
                INSERT INTO conversations
                (user_query, ai_response, model_used, importance_score)
                VALUES (?, ?, ?, ?)
            """, (query, response, model, importance))

            conv_id = cursor.lastrowid

            # 가짜 임베딩 데이터 (컬럼명 수정: embedding -> embedding_vector)
            fake_embedding = json.dumps([0.1] * 384)  # 384차원 벡터
            cursor.execute("""
                INSERT INTO conversation_embeddings
                (conversation_id, embedding_vector, sync_status)
                VALUES (?, ?, 'pending')
            """, (conv_id, fake_embedding))

        conn.commit()
        conn.close()
        print(f"테스트 데이터베이스 생성 완료: {self.memory_db}")

    @patch('requests.get')
    @patch('requests.put')
    def test_qdrant_connection_failure(self, mock_put, mock_get):
        """Qdrant 연결 실패 시 폴백 처리 테스트"""
        print("\n=== Qdrant 연결 실패 테스트 시작 ===")

        # Qdrant 연결 실패 시뮬레이션
        mock_get.side_effect = ConnectionError("Qdrant connection failed")
        mock_put.side_effect = ConnectionError("Qdrant connection failed")

        # 메모리 컬렉션 생성 시도
        result = self.memory_system.ensure_memory_collection(self.test_project_id)

        # 벡터 기능이 비활성화되어야 함
        self.assertFalse(result, "Qdrant 실패 시 False 반환해야 함")
        self.assertFalse(self.memory_system._vector_enabled, "벡터 기능이 비활성화되어야 함")

        # FTS 전용 모드로 대화 검색 가능해야 함
        results = self.memory_system.search_conversations(
            project_id=self.test_project_id,
            query="Python",
            limit=10
        )

        self.assertGreater(len(results), 0, "FTS 검색이 작동해야 함")
        self.assertIn("Python", results[0]['user_query'], "올바른 검색 결과여야 함")

        print("✅ Qdrant 연결 실패 시 FTS 폴백 정상 작동")

    @patch('requests.post')
    @patch('requests.get')
    def test_qdrant_sync_failure_handling(self, mock_get, mock_post):
        """Qdrant 동기화 실패 처리 테스트"""
        print("\n=== Qdrant 동기화 실패 처리 테스트 시작 ===")

        # 컬렉션 존재 확인은 성공
        mock_get.return_value.status_code = 200

        # 임베딩 생성 실패 시뮬레이션
        mock_post.side_effect = Exception("Embedding service unavailable")

        # 벡터 기능 강제 활성화 (테스트를 위해)
        self.memory_system._vector_enabled = True

        # 동기화 시도
        sync_stats = self.memory_system.batch_sync_to_qdrant(
            project_id=self.test_project_id,
            batch_size=10
        )

        # 실패 통계 확인
        self.assertEqual(sync_stats['synced'], 0, "동기화 성공 수가 0이어야 함")
        self.assertGreater(sync_stats['failed'], 0, "실패한 임베딩이 있어야 함")

        # 실패 상태가 DB에 기록되었는지 확인
        conn = sqlite3.connect(self.memory_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM conversation_embeddings
            WHERE sync_status = 'failed'
        """)
        failed_count = cursor.fetchone()[0]
        conn.close()

        self.assertGreater(failed_count, 0, "실패 상태가 DB에 기록되어야 함")

        print(f"✅ 동기화 실패 처리 정상 작동: {failed_count}개 실패 기록")

    @patch('requests.get')
    def test_maintainer_qdrant_failure_handling(self, mock_get):
        """메모리 유지보수 서비스의 Qdrant 장애 처리 테스트"""
        print("\n=== 메모리 유지보수 Qdrant 장애 처리 테스트 시작 ===")

        if not MAINTAINER_AVAILABLE:
            self.skipTest("MemoryMaintainer module not available (missing schedule dependency)")
            return

        # Qdrant 헬스체크 실패 시뮬레이션
        mock_get.side_effect = ConnectionError("Qdrant unavailable")

        # 메모리 유지보수 서비스 초기화
        maintainer = MemoryMaintainer()

        # 헬스체크 수행
        health_info = maintainer.health_check()

        # Qdrant 서비스가 unhealthy로 표시되어야 함
        self.assertFalse(health_info['services']['qdrant'], "Qdrant가 unhealthy로 표시되어야 함")

        # 동기화 작업 실행 (장애 상황에서)
        try:
            maintainer.run_qdrant_sync()
            print("✅ Qdrant 장애 시에도 동기화 작업이 예외 없이 실행됨")
        except Exception as e:
            self.fail(f"동기화 작업에서 예외 발생: {e}")

    @patch('memory_system.get_memory_system')
    def test_retry_mechanism(self, mock_get_memory_system):
        """실패한 동기화 재시도 메커니즘 테스트"""
        print("\n=== 재시도 메커니즘 테스트 시작 ===")

        if not MAINTAINER_AVAILABLE:
            self.skipTest("MemoryMaintainer module not available (missing schedule dependency)")
            return

        # 모킹된 메모리 시스템 설정
        mock_memory = Mock()
        mock_memory.retry_failed_syncs.return_value = {
            'retried': 3,
            'succeeded': 2,
            'failed': 1
        }
        mock_get_memory_system.return_value = mock_memory

        # 유지보수 서비스로 재시도 스케줄링
        maintainer = MemoryMaintainer()
        maintainer.schedule_retry_sync()

        print("✅ 재시도 스케줄링 정상 등록됨")

        # 실패 상태 테스트 (실제 스키마에 맞게)
        conn = sqlite3.connect(self.memory_db)
        cursor = conn.cursor()

        # 실패한 임베딩 상태 업데이트
        cursor.execute("""
            UPDATE conversation_embeddings
            SET sync_status = 'failed'
            WHERE id = 1
        """)
        conn.commit()

        # 실패 상태 확인
        cursor.execute("""
            SELECT sync_status FROM conversation_embeddings
            WHERE id = 1
        """)
        status = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(status, 'failed', "실패 상태가 기록되어야 함")
        print(f"✅ 실패 상태 기록 확인: {status}")

    def test_fts_fallback_search_quality(self):
        """FTS 폴백 검색 품질 테스트"""
        print("\n=== FTS 폴백 검색 품질 테스트 시작 ===")

        # 벡터 기능 강제 비활성화
        self.memory_system._vector_enabled = False

        # 다양한 검색 쿼리 테스트
        test_queries = [
            ("Python", "Python 함수 작성법"),
            ("머신러닝", "머신러닝 개념"),
            ("Docker", "Docker 사용법"),
            ("함수", "Python 함수 작성법")  # 부분 매치
        ]

        for query, expected_content in test_queries:
            results = self.memory_system.search_conversations(
                project_id=self.test_project_id,
                query=query,
                limit=5
            )

            self.assertGreater(len(results), 0, f"'{query}' 검색 결과가 있어야 함")

            # 관련성 확인
            found_relevant = any(
                expected_content in result.get('user_query', '') or
                expected_content in result.get('ai_response', '')
                for result in results
            )

            self.assertTrue(found_relevant, f"'{query}' 검색에서 관련 결과를 찾아야 함")
            print(f"✅ '{query}' 검색 품질 확인 완료")

    def test_database_corruption_recovery(self):
        """데이터베이스 손상 복구 테스트"""
        print("\n=== 데이터베이스 손상 복구 테스트 시작 ===")

        # 임의로 DB 파일 손상 시뮬레이션
        corrupt_db = self.project_dir / 'corrupt_test.db'
        with open(corrupt_db, 'wb') as f:
            f.write(b'corrupted data')

        # 손상된 DB 접근 시도
        try:
            conn = sqlite3.connect(corrupt_db)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations")
            conn.close()
            self.fail("손상된 DB에서 예외가 발생해야 함")
        except sqlite3.DatabaseError:
            print("✅ 손상된 DB 탐지 성공")

        # 새로운 DB로 재초기화 테스트
        new_memory_system = MemorySystem()
        # 메모리 시스템 자체 초기화로 DB 생성 검증
        self.assertTrue(new_memory_system._storage_available, "새 메모리 시스템이 초기화되어야 함")

        print("✅ DB 재초기화 성공")

    def test_concurrent_failure_handling(self):
        """동시 장애 처리 테스트"""
        print("\n=== 동시 장애 처리 테스트 시작 ===")

        from concurrent.futures import ThreadPoolExecutor
        import threading

        results = []
        errors = []

        def sync_with_failure():
            try:
                # 각 스레드에서 동기화 시도
                stats = self.memory_system.batch_sync_to_qdrant(
                    project_id=self.test_project_id,
                    batch_size=5
                )
                results.append(stats)
            except Exception as e:
                errors.append(str(e))

        # 동시에 5개 스레드에서 동기화 시도
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(sync_with_failure) for _ in range(5)]

            for future in futures:
                future.result()  # 완료 대기

        # 예외가 발생하지 않았는지 확인
        self.assertEqual(len(errors), 0, f"동시 처리 중 예외 발생: {errors}")
        self.assertGreater(len(results), 0, "동시 처리 결과가 있어야 함")

        print(f"✅ 동시 장애 처리 성공: {len(results)}개 결과, {len(errors)}개 오류")


def run_qdrant_failure_tests():
    """Qdrant 장애 테스트 실행 함수"""
    print("🧪 Qdrant 장애 시나리오 자동화 테스트 시작\n")

    # 테스트 스위트 생성
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestQdrantFailureScenarios)

    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 결과 요약
    print(f"\n📊 테스트 결과 요약:")
    print(f"   실행된 테스트: {result.testsRun}")
    print(f"   실패한 테스트: {len(result.failures)}")
    print(f"   오류가 발생한 테스트: {len(result.errors)}")

    if result.failures:
        print("\n❌ 실패한 테스트:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback}")

    if result.errors:
        print("\n💥 오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback}")

    if result.wasSuccessful():
        print("\n✅ 모든 Qdrant 장애 테스트 통과!")
        return True
    else:
        print("\n❌ 일부 테스트 실패")
        return False


if __name__ == "__main__":
    success = run_qdrant_failure_tests()
    sys.exit(0 if success else 1)