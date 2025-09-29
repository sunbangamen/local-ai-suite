#!/usr/bin/env python3
"""
Phase 2 벡터 임베딩 파이프라인 실제 동작 예시

전제 조건:
1. 서비스 실행: make up-p2 (또는 make build-p2 && make up-p2)

호스트에서 직접 실행하는 경우:
2. 의존성 설치: pip install qdrant-client httpx

컨테이너 환경에서는 의존성이 이미 services/rag/Dockerfile에 포함되어 있습니다.
"""

import sys
import asyncio
from pathlib import Path

# 메모리 시스템 모듈 경로 추가
sys.path.append(str(Path(__file__).parent / "scripts"))

from memory_system import MemorySystem


async def demo_vector_pipeline():
    """실제 벡터 파이프라인 데모"""
    print("🚀 Phase 2 벡터 임베딩 파이프라인 데모")
    print("=" * 50)

    # 1. 메모리 시스템 초기화
    ms = MemorySystem()
    project_id = ms.get_project_id('/mnt/e/worktree/issue-5')

    print(f"📁 프로젝트 ID: {project_id}")
    print(f"🔗 임베딩 서비스: {ms.embedding_url}")
    print(f"🔗 Qdrant 서비스: {ms.qdrant_url}")
    print(f"📡 벡터 검색 활성화: {ms._vector_enabled}")

    # 2. 새 대화 저장 (자동으로 임베딩 큐에 추가)
    conv_id = ms.save_conversation(
        project_id=project_id,
        user_query="Python에서 비동기 프로그래밍을 어떻게 하나요?",
        ai_response="""Python에서 비동기 프로그래밍은 asyncio 모듈을 사용합니다:

1. async def로 코루틴 함수 정의
2. await 키워드로 비동기 작업 대기
3. asyncio.run()으로 실행

예시:
```python
import asyncio

async def main():
    print("Hello")
    await asyncio.sleep(1)
    print("World")

asyncio.run(main())
```""",
        model_used="chat-7b",
        session_id="vector-demo"
    )

    print(f"\n✅ 대화 저장 완료: ID {conv_id}")
    print("💾 임베딩 큐에 자동 추가됨 (sync_status='pending')")

    # 3. 대기 중인 임베딩 처리
    print(f"\n🔄 벡터 임베딩 처리 시작...")
    processed = await ms.process_pending_embeddings(project_id, batch_size=5)
    print(f"📊 처리된 대화 수: {processed}")

    # 4. 처리 결과 확인
    with ms.transaction(project_id) as conn:
        cursor = conn.execute("""
            SELECT conversation_id, sync_status, synced_at, created_at
            FROM conversation_embeddings
            WHERE conversation_id = ?
        """, (conv_id,))

        result = cursor.fetchone()
        if result:
            print(f"\n📋 임베딩 처리 결과:")
            print(f"   대화 ID: {result['conversation_id']}")
            print(f"   상태: {result['sync_status']}")
            print(f"   동기화 시각: {result['synced_at']}")
            print(f"   생성 시각: {result['created_at']}")

            if result['sync_status'] == 'synced':
                print("🎉 벡터 임베딩 파이프라인 성공!")
                print("   ✅ FastEmbed 서비스에서 384차원 벡터 생성")
                print("   ✅ Qdrant에 벡터 저장 완료")
                print("   ✅ SQLite 상태 추적 업데이트")
            else:
                print(f"⚠️ 처리 미완료: {result['sync_status']}")

    # 5. 벡터 검색 테스트 (의존성 있는 경우)
    if ms._vector_enabled:
        print(f"\n🔍 벡터 검색 테스트...")
        search_results = await ms.vector_search_conversations(
            project_id=project_id,
            query="asyncio 사용법",
            limit=3,
            score_threshold=0.5
        )

        print(f"검색 결과: {len(search_results)}개")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. 유사도: {result['similarity_score']:.3f}")
            print(f"     질문: {result['user_query'][:50]}...")

        # 6. 하이브리드 검색 테스트
        print(f"\n🔄 하이브리드 검색 테스트...")
        hybrid_results = await ms.hybrid_search_conversations(
            project_id=project_id,
            query="Python 비동기",
            limit=5
        )

        print(f"하이브리드 검색 결과: {len(hybrid_results)}개")
        for i, result in enumerate(hybrid_results, 1):
            method = result.get('search_method', 'unknown')
            score = result.get('search_score', 0)
            print(f"  {i}. [{method}] 점수: {score:.3f}")
            print(f"     질문: {result['user_query'][:50]}...")


def demo_sync_version():
    """동기 버전 간단 예시"""
    print("🔄 동기 버전 간단 데모")
    print("=" * 30)

    # 동기 작업만
    ms = MemorySystem()
    project_id = ms.get_project_id('/mnt/e/worktree/issue-5')

    # 대화 저장 (자동으로 큐에 추가됨)
    conv_id = ms.save_conversation(
        project_id=project_id,
        user_query="간단한 테스트 질문입니다.",
        ai_response="간단한 테스트 응답입니다.",
        model_used="test-model"
    )
    print(f"✅ 대화 저장: ID {conv_id}")

    # 비동기 처리는 별도로 실행
    print("💡 비동기 처리: asyncio.run(ms.process_pending_embeddings(project_id))")


if __name__ == "__main__":
    print("벡터 의존성 체크...")

    try:
        import qdrant_client
        import httpx
        print("✅ 벡터 의존성 설치됨 - 전체 데모 실행")

        # 전체 비동기 데모 실행
        asyncio.run(demo_vector_pipeline())

    except ImportError as e:
        print(f"⚠️ 벡터 의존성 누락: {e}")
        print("📝 설치 방법:")
        print("   pip install qdrant-client httpx")
        print("   또는")
        print("   pip install -r services/rag/requirements.txt")
        print()

        # 동기 버전만 데모
        demo_sync_version()