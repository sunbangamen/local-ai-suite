"""
Memory System Utilities
프로젝트 식별, 메모리 관리 유틸리티 함수들
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional
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
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
                print(f"✅ 기존 프로젝트 메모리 발견: {project_data['project_id']}")
                print(f"📁 프로젝트: {project_data['project_name']}")
                print(f"📅 생성일: {project_data['created_at']}")
                return project_data['project_id']
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
            "project_name": project_path.name
        }

    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
            return {
                "has_memory": True,
                "project_id": project_data['project_id'],
                "project_name": project_data['project_name'],
                "project_path": project_data['project_path'],
                "created_at": project_data['created_at'],
                "updated_at": project_data.get('updated_at', project_data['created_at'])
            }
    except (json.JSONDecodeError, KeyError):
        return {
            "has_memory": False,
            "project_path": str(project_path),
            "project_name": project_path.name,
            "error": "손상된 프로젝트 메모리 파일"
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
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
                project_info = {
                    "has_memory": True,
                    "project_id": project_data['project_id'],
                    "project_name": project_data['project_name'],
                    "project_path": project_data['project_path'],
                    "created_at": project_data['created_at']
                }
        else:
            project_info = {
                "has_memory": False,
                "project_path": str(project_path),
                "project_name": project_path.name
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
            print(f"\n📊 메모리 통계:")
            print(f"  💬 총 대화: {stats['total_conversations']:,}개")
            if stats['total_conversations'] > 0:
                print(f"  ⭐ 평균 중요도: {stats['avg_importance']:.1f}/10")
                print(f"  📅 최초 대화: {stats['oldest_conversation']}")
                print(f"  📅 최근 대화: {stats['latest_conversation']}")

                # 중요도 분포
                if stats['importance_distribution']:
                    print(f"\n📈 중요도 분포:")
                    for importance, count in stats['importance_distribution'].items():
                        level_info = ms.IMPORTANCE_LEVELS[importance]
                        print(f"  {importance}/10 ({level_info['name']}): {count}개")

                # 모델 사용량
                if stats['model_usage']:
                    print(f"\n🤖 모델 사용량:")
                    for model, count in stats['model_usage'].items():
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
        cursor = conn.execute("""
            SELECT id, user_query, importance_score, expires_at
            FROM conversations
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """, (datetime.now(),))

        expired_conversations = cursor.fetchall()

        if dry_run:
            print(f"🧹 정리 예정 대화: {len(expired_conversations)}개")
            for conv in expired_conversations[:5]:  # 처음 5개만 미리보기
                print(f"  - [{conv['importance_score']}/10] {conv['user_query'][:50]}...")
            if len(expired_conversations) > 5:
                print(f"  ... 외 {len(expired_conversations) - 5}개")

            return {
                "total_expired": len(expired_conversations),
                "cleaned": 0,
                "dry_run": True
            }

        # 실제 삭제
        deleted_ids = [conv['id'] for conv in expired_conversations]
        if deleted_ids:
            placeholders = ','.join('?' * len(deleted_ids))
            conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", deleted_ids)

            # 관련 임베딩도 삭제
            conn.execute(f"DELETE FROM conversation_embeddings WHERE conversation_id IN ({placeholders})", deleted_ids)

            print(f"🗑️ {len(deleted_ids)}개 대화가 정리되었습니다.")

        return {
            "total_expired": len(expired_conversations),
            "cleaned": len(deleted_ids),
            "dry_run": False
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
        cursor = conn.execute("SELECT * FROM conversation_summaries ORDER BY created_at")
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
            "total_summaries": len(summaries)
        }
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"💾 메모리 백업 완료: {output_path}")
    print(f"📊 대화 {len(conversations)}개, 사실 {len(facts)}개, 요약 {len(summaries)}개")

    return output_path

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
        session_id="test_session"
    )
    print(f"✅ 테스트 대화 저장 완료: ID {conv_id}")

    # 상태 다시 확인
    print("\n📊 테스트 후 상태:")
    show_memory_status()