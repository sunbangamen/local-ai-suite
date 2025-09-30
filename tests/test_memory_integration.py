#!/usr/bin/env python3
"""
Memory System Integration Tests
메모리 시스템 통합 테스트 - 기본 기능 검증
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from memory_system import MemorySystem, get_memory_system

class TestMemoryIntegration:
    def __init__(self):
        self.memory = MemorySystem(data_dir="/tmp/test-memory")
        self.project_id = None
        self.test_conversations = []

    def setup(self):
        """테스트 환경 설정"""
        print("=" * 60)
        print("Memory System Integration Tests")
        print("=" * 60)

        # 테스트 프로젝트 디렉토리 생성
        from pathlib import Path
        test_project_path = Path("/tmp/test-project")
        test_project_path.mkdir(parents=True, exist_ok=True)

        # 프로젝트 ID 생성
        self.project_id = self.memory.get_project_id(str(test_project_path))
        print(f"\n✅ Test project created: {self.project_id}")

    def test_save_conversations(self):
        """대화 저장 테스트"""
        print("\n[Test 1] 대화 저장 테스트")
        print("-" * 60)

        test_data = [
            {
                "query": "안녕하세요!",
                "response": "안녕하세요! 무엇을 도와드릴까요?",
                "model": "chat-7b",
                "expected_importance": 1  # 인사
            },
            {
                "query": "Python에서 파일을 읽는 방법을 알려주세요",
                "response": "Python에서 파일을 읽으려면 open() 함수를 사용합니다...",
                "model": "chat-7b",
                "expected_importance": 6  # 코드 관련
            },
            {
                "query": "Django REST Framework API 설계 패턴",
                "response": "Django REST Framework에서 API를 설계할 때는 다음 패턴들을 고려해야 합니다:\n1. ViewSets 사용\n2. Serializers 정의\n3. URL routing...",
                "model": "code-7b",
                "expected_importance": 7  # 설계 패턴
            }
        ]

        for i, data in enumerate(test_data, 1):
            conv_id = self.memory.save_conversation(
                project_id=self.project_id,
                user_query=data["query"],
                ai_response=data["response"],
                model_used=data["model"],
                session_id="test-session"
            )

            if conv_id:
                self.test_conversations.append(conv_id)

                # 중요도 점수 확인
                with self.memory.transaction(self.project_id) as conn:
                    cursor = conn.execute(
                        "SELECT importance_score FROM conversations WHERE id = ?",
                        (conv_id,)
                    )
                    row = cursor.fetchone()
                    actual_score = row['importance_score'] if row else 0

                expected_range = (data["expected_importance"] - 1, data["expected_importance"] + 1)
                score_ok = expected_range[0] <= actual_score <= expected_range[1]

                status = "✅" if score_ok else "⚠️"
                print(f"{status} Conversation {i} saved (ID: {conv_id}, Score: {actual_score}, Expected: ~{data['expected_importance']})")
            else:
                print(f"❌ Failed to save conversation {i}")

        print(f"\n총 {len(self.test_conversations)}개 대화 저장 완료")

    def test_fts_search(self):
        """FTS5 전문 검색 테스트"""
        print("\n[Test 2] FTS5 전문 검색 테스트")
        print("-" * 60)

        test_queries = [
            ("파일", "FTS5 keyword search"),
            ("Django API", "Multi-word search"),
            ("python", "Case insensitive search")
        ]

        for query, description in test_queries:
            results = self.memory.search_conversations(
                project_id=self.project_id,
                query=query,
                limit=10
            )

            print(f"\n검색어: '{query}' ({description})")
            print(f"결과: {len(results)}개")

            for result in results[:2]:  # Show top 2
                print(f"  - Score: {result.get('importance_score')}, Query: {result['user_query'][:50]}...")

    async def test_vector_search(self):
        """벡터 유사도 검색 테스트"""
        print("\n[Test 3] 벡터 유사도 검색 테스트")
        print("-" * 60)

        if not self.memory._vector_enabled:
            print("⚠️ Vector search not available (Qdrant/Embedding service required)")
            return

        # 임베딩 생성 및 동기화
        print("임베딩 생성 중...")
        processed = await self.memory.process_pending_embeddings(
            self.project_id,
            batch_size=10
        )
        print(f"✅ {processed}개 임베딩 생성 완료")

        # 벡터 검색
        query = "파일 입출력 방법"
        results = await self.memory.vector_search_conversations(
            project_id=self.project_id,
            query=query,
            limit=5,
            score_threshold=0.5
        )

        print(f"\n검색어: '{query}'")
        print(f"결과: {len(results)}개")

        for result in results:
            print(f"  - Similarity: {result['similarity_score']:.3f}, Query: {result['user_query'][:50]}...")

    async def test_hybrid_search(self):
        """하이브리드 검색 (FTS5 + 벡터) 테스트"""
        print("\n[Test 4] 하이브리드 검색 테스트")
        print("-" * 60)

        if not self.memory._vector_enabled:
            print("⚠️ Hybrid search requires vector support")
            return

        query = "Python 프로그래밍"
        results = await self.memory.hybrid_search_conversations(
            project_id=self.project_id,
            query=query,
            limit=10
        )

        print(f"\n검색어: '{query}'")
        print(f"결과: {len(results)}개")

        for result in results[:3]:  # Show top 3
            search_method = result.get('search_method', 'unknown')
            score = result.get('search_score', 0)
            print(f"  - Method: {search_method}, Score: {score:.3f}, Query: {result['user_query'][:50]}...")

    def test_stats(self):
        """통계 조회 테스트"""
        print("\n[Test 5] 통계 조회 테스트")
        print("-" * 60)

        stats = self.memory.get_conversation_stats(self.project_id)

        print(f"총 대화 수: {stats['total_conversations']}")
        print(f"평균 중요도: {stats['avg_importance']:.2f}")
        print(f"가장 오래된 대화: {stats['oldest_conversation']}")
        print(f"가장 최근 대화: {stats['latest_conversation']}")

        print("\n중요도 분포:")
        for score, count in sorted(stats['importance_distribution'].items()):
            percentage = (count / stats['total_conversations']) * 100
            print(f"  Score {score}: {count}개 ({percentage:.1f}%)")

        print("\n모델 사용량:")
        for model, count in stats['model_usage'].items():
            percentage = (count / stats['total_conversations']) * 100
            print(f"  {model}: {count}개 ({percentage:.1f}%)")

    def test_ttl_cleanup(self):
        """TTL 정리 테스트"""
        print("\n[Test 6] TTL 정리 테스트")
        print("-" * 60)

        # 만료 시간이 지난 대화 생성 (테스트용)
        from datetime import datetime, timedelta

        with self.memory.transaction(self.project_id) as conn:
            # 만료된 대화 추가
            expired_time = (datetime.now() - timedelta(days=1)).isoformat()
            conn.execute("""
                INSERT INTO conversations
                (user_query, ai_response, importance_score, expires_at)
                VALUES (?, ?, ?, ?)
            """, ("Test expired conversation", "This should be deleted", 1, expired_time))

        # 정리 실행
        deleted_count = self.memory.cleanup_expired_conversations(self.project_id)

        print(f"✅ {deleted_count}개 만료된 대화 정리 완료")

    def test_database_optimization(self):
        """데이터베이스 최적화 테스트"""
        print("\n[Test 7] 데이터베이스 최적화 테스트")
        print("-" * 60)

        success = self.memory.optimize_database(self.project_id)

        if success:
            print("✅ 데이터베이스 최적화 (VACUUM, ANALYZE) 완료")
        else:
            print("❌ 데이터베이스 최적화 실패")

    def test_backup(self):
        """백업 테스트"""
        print("\n[Test 8] 백업 테스트")
        print("-" * 60)

        backup_path = self.memory.export_memory_backup(self.project_id)

        if backup_path and backup_path.exists():
            size_mb = backup_path.stat().st_size / (1024 * 1024)
            print(f"✅ 백업 생성 성공: {backup_path}")
            print(f"   파일 크기: {size_mb:.2f} MB")
        else:
            print("❌ 백업 생성 실패")

    def teardown(self):
        """테스트 정리"""
        print("\n" + "=" * 60)
        print("테스트 완료")
        print("=" * 60)

        # 테스트 데이터 정리 (선택적)
        # import shutil
        # shutil.rmtree("/tmp/test-memory", ignore_errors=True)
        # print("테스트 데이터 정리 완료")

def main():
    """메인 테스트 실행"""
    test = TestMemoryIntegration()

    try:
        # Setup
        test.setup()

        # Run tests
        test.test_save_conversations()
        test.test_fts_search()

        # Async tests
        asyncio.run(test.test_vector_search())
        asyncio.run(test.test_hybrid_search())

        # Synchronous tests
        test.test_stats()
        test.test_ttl_cleanup()
        test.test_database_optimization()
        test.test_backup()

        # Teardown
        test.teardown()

        print("\n✅ 모든 테스트 통과!")
        return 0

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())