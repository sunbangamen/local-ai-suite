"""
Memory System Utilities
프로젝트 식별, 메모리 관리 유틸리티 함수들
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def init_project_memory(project_path: str = None) -> str:
    """
    현재 디렉토리 또는 지정된 경로에 프로젝트 메모리 초기화
    .ai-memory/project.json 파일 생성
    """
    from memory_system import get_memory_system

    ms = get_memory_system()

    if project_path is None:
        project_path = os.getcwd()

    project_path = Path(project_path).resolve()
    memory_dir = project_path / ".ai-memory"
    project_file = memory_dir / "project.json"

    # 이미 존재하는 경우 기존 ID 반환
    if project_file.exists():
        try:
            with open(project_file, "r", encoding="utf-8") as f:
                project_data = json.load(f)
                print(f"✅ 기존 프로젝트 메모리 발견: {project_data['project_id']}")
                print(f"📁 프로젝트: {project_data['project_name']}")
                print(f"📅 생성일: {project_data['created_at']}")
                return project_data["project_id"]
        except (json.JSONDecodeError, KeyError):
            print("⚠️ 손상된 project.json 파일을 다시 생성합니다.")

    # 새 프로젝트 메모리 생성
    project_id = ms.get_project_id(str(project_path))

    print(f"🆕 새 프로젝트 메모리 생성: {project_id}")
    print(f"📁 프로젝트: {project_path.name}")
    print(f"📍 경로: {project_path}")
    print(f"💾 메모리 파일: {memory_dir}")

    return project_id


def get_current_project_info() -> Dict:
    """현재 디렉토리의 프로젝트 정보 반환"""
    project_path = Path(os.getcwd()).resolve()
    memory_dir = project_path / ".ai-memory"
    project_file = memory_dir / "project.json"

    if not project_file.exists():
        return {
            "has_memory": False,
            "project_path": str(project_path),
            "project_name": project_path.name,
        }

    try:
        with open(project_file, "r", encoding="utf-8") as f:
            project_data = json.load(f)
            return {
                "has_memory": True,
                "project_id": project_data["project_id"],
                "project_name": project_data["project_name"],
                "project_path": project_data["project_path"],
                "created_at": project_data["created_at"],
                "updated_at": project_data.get(
                    "updated_at", project_data["created_at"]
                ),
            }
    except (json.JSONDecodeError, KeyError):
        return {
            "has_memory": False,
            "project_path": str(project_path),
            "project_name": project_path.name,
            "error": "손상된 프로젝트 메모리 파일",
        }


def show_memory_status(project_path: str = None):
    """메모리 시스템 상태 출력"""
    from memory_system import get_memory_system

    ms = get_memory_system()

    if project_path is None:
        project_info = get_current_project_info()
    else:
        # 지정된 경로의 프로젝트 정보
        project_path = Path(project_path).resolve()
        memory_dir = project_path / ".ai-memory"
        project_file = memory_dir / "project.json"

        if project_file.exists():
            with open(project_file, "r", encoding="utf-8") as f:
                project_data = json.load(f)
                project_info = {
                    "has_memory": True,
                    "project_id": project_data["project_id"],
                    "project_name": project_data["project_name"],
                    "project_path": project_data["project_path"],
                    "created_at": project_data["created_at"],
                }
        else:
            project_info = {
                "has_memory": False,
                "project_path": str(project_path),
                "project_name": project_path.name,
            }

    print("🧠 AI Memory System Status")
    print("=" * 40)

    if project_info["has_memory"]:
        project_id = project_info["project_id"]

        print(f"📁 프로젝트: {project_info['project_name']}")
        print(f"🆔 메모리 ID: {project_id}")
        print(f"📍 경로: {project_info['project_path']}")
        print(f"📅 생성일: {project_info['created_at']}")

        # 통계 정보
        try:
            stats = ms.get_conversation_stats(project_id)
            print("\n📊 메모리 통계:")
            print(f"  💬 총 대화: {stats['total_conversations']:,}개")
            if stats["total_conversations"] > 0:
                print(f"  ⭐ 평균 중요도: {stats['avg_importance']:.1f}/10")
                print(f"  📅 최초 대화: {stats['oldest_conversation']}")
                print(f"  📅 최근 대화: {stats['latest_conversation']}")

                # 중요도 분포
                if stats["importance_distribution"]:
                    print("\n📈 중요도 분포:")
                    for importance, count in stats["importance_distribution"].items():
                        level_info = ms.IMPORTANCE_LEVELS[importance]
                        print(f"  {importance}/10 ({level_info['name']}): {count}개")

                # 모델 사용량
                if stats["model_usage"]:
                    print("\n🤖 모델 사용량:")
                    for model, count in stats["model_usage"].items():
                        print(f"  {model}: {count}개")

        except Exception as e:
            print(f"⚠️ 통계 조회 중 오류: {e}")

    else:
        print(f"📁 프로젝트: {project_info['project_name']}")
        print(f"📍 경로: {project_info['project_path']}")
        print("❌ 메모리 시스템이 초기화되지 않았습니다.")
        print("💡 'ai --memory --init' 명령으로 초기화하세요.")


def cleanup_expired_conversations(project_id: str = None, dry_run: bool = True) -> Dict:
    """
    만료된 대화 정리 (TTL 기반)
    """
    from memory_system import get_memory_system

    ms = get_memory_system()

    if project_id is None:
        project_info = get_current_project_info()
        if not project_info["has_memory"]:
            raise ValueError("프로젝트 메모리가 초기화되지 않았습니다.")
        project_id = project_info["project_id"]

    with ms.transaction(project_id) as conn:
        # 만료된 대화 조회
        cursor = conn.execute(
            """
            SELECT id, user_query, importance_score, expires_at
            FROM conversations
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """,
            (datetime.now(),),
        )

        expired_conversations = cursor.fetchall()

        if dry_run:
            print(f"🧹 정리 예정 대화: {len(expired_conversations)}개")
            for conv in expired_conversations[:5]:  # 처음 5개만 미리보기
                print(
                    f"  - [{conv['importance_score']}/10] {conv['user_query'][:50]}..."
                )
            if len(expired_conversations) > 5:
                print(f"  ... 외 {len(expired_conversations) - 5}개")

            return {
                "total_expired": len(expired_conversations),
                "cleaned": 0,
                "dry_run": True,
            }

        # 실제 삭제
        deleted_ids = [conv["id"] for conv in expired_conversations]
        if deleted_ids:
            placeholders = ",".join("?" * len(deleted_ids))
            conn.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})", deleted_ids
            )

            # 관련 임베딩도 삭제
            conn.execute(
                f"DELETE FROM conversation_embeddings WHERE conversation_id IN ({placeholders})",
                deleted_ids,
            )

            print(f"🗑️ {len(deleted_ids)}개 대화가 정리되었습니다.")

        return {
            "total_expired": len(expired_conversations),
            "cleaned": len(deleted_ids),
            "dry_run": False,
        }


def export_memory_backup(project_id: str = None, output_path: str = None) -> str:
    """메모리 데이터를 JSON으로 백업"""
    from memory_system import get_memory_system

    ms = get_memory_system()

    if project_id is None:
        project_info = get_current_project_info()
        if not project_info["has_memory"]:
            raise ValueError("프로젝트 메모리가 초기화되지 않았습니다.")
        project_id = project_info["project_id"]

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"memory_backup_{project_id[:8]}_{timestamp}.json"

    with ms.transaction(project_id) as conn:
        # 모든 대화 조회
        cursor = conn.execute("SELECT * FROM conversations ORDER BY timestamp")
        conversations = [dict(row) for row in cursor.fetchall()]

        # 중요 사실 조회
        cursor = conn.execute("SELECT * FROM important_facts ORDER BY created_at")
        facts = [dict(row) for row in cursor.fetchall()]

        # 요약 조회
        cursor = conn.execute(
            "SELECT * FROM conversation_summaries ORDER BY created_at"
        )
        summaries = [dict(row) for row in cursor.fetchall()]

    backup_data = {
        "project_id": project_id,
        "export_timestamp": datetime.now().isoformat(),
        "conversations": conversations,
        "important_facts": facts,
        "conversation_summaries": summaries,
        "metadata": {
            "total_conversations": len(conversations),
            "total_facts": len(facts),
            "total_summaries": len(summaries),
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"💾 메모리 백업 완료: {output_path}")
    print(
        f"📊 대화 {len(conversations)}개, 사실 {len(facts)}개, 요약 {len(summaries)}개"
    )

    return output_path


# ============ Qdrant 헬퍼 함수 (공통) ============


def get_collection_name(project_id: str) -> str:
    """
    프로젝트 ID로부터 Qdrant 컬렉션 이름 생성 (통일된 규칙)
    Args:
        project_id: 프로젝트 UUID
    Returns:
        collection_name: memory_{project_id[:8]}
    """
    return f"memory_{project_id[:8]}"


def ensure_qdrant_collection(
    project_id: str,
    qdrant_url: str = None,
    vector_size: int = 384,
    distance: str = "Cosine",
) -> bool:
    """
    Qdrant 컬렉션 존재 확인 및 생성 (memory_system과 maintainer 공통 사용)

    Args:
        project_id: 프로젝트 UUID
        qdrant_url: Qdrant 서버 URL (기본: http://localhost:6333)
        vector_size: 벡터 차원 (기본: 384 - BAAI/bge-small-en-v1.5)
        distance: 거리 메트릭 (기본: Cosine)

    Returns:
        bool: 컬렉션 준비 성공 여부
    """
    if qdrant_url is None:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    collection_name = get_collection_name(project_id)

    try:
        # 컬렉션 존재 확인
        response = requests.get(
            f"{qdrant_url}/collections/{collection_name}", timeout=10
        )

        if response.status_code == 404:
            # 컬렉션 생성
            create_data = {"vectors": {"size": vector_size, "distance": distance}}

            response = requests.put(
                f"{qdrant_url}/collections/{collection_name}",
                json=create_data,
                timeout=30,
            )

            if response.status_code == 200:
                print(f"✅ Qdrant 컬렉션 생성: {collection_name}")
                return True
            else:
                print(f"❌ Qdrant 컬렉션 생성 실패: {response.status_code}")
                return False

        elif response.status_code == 200:
            # 컬렉션 이미 존재
            return True

        else:
            print(f"⚠️ Qdrant 상태 확인 실패: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Qdrant 접근 실패: {e}")
        return False


def upsert_to_qdrant(
    project_id: str, points: List[Dict], qdrant_url: str = None
) -> bool:
    """
    Qdrant에 포인트 업로드 (배치)

    Args:
        project_id: 프로젝트 UUID
        points: 업로드할 포인트 리스트 [{"id": int, "vector": List[float], "payload": Dict}]
        qdrant_url: Qdrant 서버 URL

    Returns:
        bool: 업로드 성공 여부
    """
    if qdrant_url is None:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    collection_name = get_collection_name(project_id)

    try:
        response = requests.put(
            f"{qdrant_url}/collections/{collection_name}/points",
            json={"points": points},
            timeout=60,
        )

        if response.status_code == 200:
            return True
        else:
            print(f"❌ Qdrant 업로드 실패: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Qdrant 업로드 에러: {e}")
        return False


def build_qdrant_payload(
    conversation_id: int,
    user_query: str,
    ai_response: str,
    model_used: str = None,
    importance_score: int = 5,
    created_at: str = None,
) -> Dict:
    """
    Qdrant 페이로드 생성 (통일된 구조)

    Args:
        conversation_id: 대화 ID
        user_query: 사용자 질문
        ai_response: AI 응답
        model_used: 사용된 모델
        importance_score: 중요도 점수
        created_at: 생성 시각

    Returns:
        payload: Qdrant 페이로드 딕셔너리
    """
    return {
        "conversation_id": conversation_id,
        "user_query": user_query[:500],  # 최대 500자
        "ai_response": ai_response[:1000],  # 최대 1000자
        "model_used": model_used or "unknown",
        "importance_score": importance_score,
        "created_at": created_at or datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # 테스트 코드
    print("🧪 메모리 시스템 테스트")

    # 현재 프로젝트 정보 확인
    show_memory_status()

    # 프로젝트 메모리 초기화 (이미 있으면 기존 사용)
    project_id = init_project_memory()

    # 동적으로 메모리 시스템 가져오기
    from memory_system import get_memory_system

    ms = get_memory_system()

    # 테스트 대화 저장
    conv_id = ms.save_conversation(
        project_id=project_id,
        user_query="안녕하세요! 메모리 시스템 테스트입니다.",
        ai_response="안녕하세요! 메모리 시스템이 정상적으로 작동하고 있습니다. 이 대화는 자동으로 저장되고 중요도가 계산됩니다.",
        model_used="chat-7b",
        session_id="test_session",
    )
    print(f"✅ 테스트 대화 저장 완료: ID {conv_id}")

    # 상태 다시 확인
    print("\n📊 테스트 후 상태:")
    show_memory_status()
