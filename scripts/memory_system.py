"""
AI Memory System - 프로젝트별 장기 기억 시스템
SQLite 기반 대화 저장, 검색, 자동 정리 기능 제공
"""

import sqlite3
import json
import hashlib
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
import threading
import re
import os

class MemorySystem:
    def __init__(self, data_dir: str = None):
        self.data_dir = self._get_data_directory(data_dir)
        self._local = threading.local()
        self._storage_available = True

        # 프로젝트별 메모리 디렉토리
        try:
            self.projects_dir = self.data_dir / "projects"
            self.projects_dir.mkdir(parents=True, exist_ok=True)

            # 글로벌 설정 디렉토리
            self.global_dir = self.data_dir / "global"
            self.global_dir.mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            print(f"⚠️ Warning: Cannot create memory directories: {e}")
            print(f"💡 Memory system will be disabled for this session.")
            self._storage_available = False

        # 중요도 레벨 정의
        self.IMPORTANCE_LEVELS = {
            1: {"name": "즉시삭제", "ttl_days": 0, "description": "인사, 테스트"},
            2: {"name": "단기보관", "ttl_days": 3, "description": "간단한 질문"},
            3: {"name": "1주보관", "ttl_days": 7, "description": "일반 대화"},
            4: {"name": "2주보관", "ttl_days": 14, "description": "정보성 질문"},
            5: {"name": "기본보관", "ttl_days": 30, "description": "기본값"},
            6: {"name": "1개월", "ttl_days": 30, "description": "코드 관련"},
            7: {"name": "3개월", "ttl_days": 90, "description": "프로젝트 설정"},
            8: {"name": "6개월", "ttl_days": 180, "description": "중요 결정사항"},
            9: {"name": "1년보관", "ttl_days": 365, "description": "핵심 문서화"},
            10: {"name": "영구보관", "ttl_days": -1, "description": "사용자 중요표시"}
        }

    def _get_data_directory(self, data_dir: str = None) -> Path:
        """
        메모리 데이터 저장 디렉토리 결정
        우선순위: 1. 명시된 경로 2. 환경변수 3. 기본 경로 4. 프로젝트 로컬 폴백
        """
        # 1. 명시적으로 지정된 경로
        if data_dir:
            path = Path(data_dir)
            if self._test_directory_access(path):
                return path

        # 2. 환경변수 AI_MEMORY_DIR
        env_dir = os.environ.get('AI_MEMORY_DIR')
        if env_dir:
            path = Path(env_dir)
            if self._test_directory_access(path):
                return path
            else:
                print(f"⚠️ Warning: AI_MEMORY_DIR '{env_dir}' is not accessible")

        # 3. 기본 경로 시도
        default_path = Path("/mnt/e/ai-data/memory")
        if self._test_directory_access(default_path):
            return default_path

        # 4. 프로젝트 로컬 폴백
        current_repo = self._find_git_root()
        if current_repo:
            fallback_path = current_repo / ".ai-memory-data"
            print(f"💡 Using local memory storage: {fallback_path}")
            if self._test_directory_access(fallback_path):
                return fallback_path

        # 5. 최종 폴백 - 현재 디렉토리
        final_fallback = Path.cwd() / ".ai-memory-data"
        print(f"⚠️ Using current directory fallback: {final_fallback}")
        return final_fallback

    def _test_directory_access(self, path: Path) -> bool:
        """디렉토리 접근 권한 테스트"""
        try:
            path.mkdir(parents=True, exist_ok=True)
            # 쓰기 권한 테스트
            test_file = path / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def _find_git_root(self) -> Optional[Path]:
        """현재 디렉토리에서 Git 루트 찾기"""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def get_project_id(self, project_path: str = None) -> str:
        """
        프로젝트 ID 획득 또는 생성
        .ai-memory/project.json에서 UUID 로드하거나 새로 생성
        """
        if project_path is None:
            project_path = os.getcwd()

        project_path = Path(project_path).resolve()
        memory_dir = project_path / ".ai-memory"
        project_file = memory_dir / "project.json"

        # 기존 프로젝트 파일 확인
        if project_file.exists():
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                    return project_data['project_id']
            except (json.JSONDecodeError, KeyError):
                pass

        # 새 프로젝트 ID 생성
        project_id = str(uuid.uuid4())
        memory_dir.mkdir(exist_ok=True)

        project_data = {
            "project_id": project_id,
            "project_name": project_path.name,
            "project_path": str(project_path),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        return project_id

    def get_project_db_path(self, project_id: str) -> Path:
        """프로젝트별 SQLite 데이터베이스 경로 반환"""
        project_dir = self.projects_dir / project_id
        project_dir.mkdir(exist_ok=True)
        return project_dir / "memory.db"

    def _get_connection(self, project_id: str):
        """Thread-safe 프로젝트별 데이터베이스 연결"""
        if not hasattr(self._local, 'connections'):
            self._local.connections = {}

        if project_id not in self._local.connections:
            db_path = self.get_project_db_path(project_id)
            conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                timeout=30.0
            )
            conn.row_factory = sqlite3.Row

            # SQLite 성능 최적화
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA foreign_keys=ON")

            self._local.connections[project_id] = conn

            # 스키마 초기화
            self._init_schema(conn)

        return self._local.connections[project_id]

    @contextmanager
    def transaction(self, project_id: str):
        """트랜잭션 컨텍스트 매니저"""
        conn = self._get_connection(project_id)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self, conn):
        """메모리 시스템 데이터베이스 스키마 초기화"""

        # 대화 기록 테이블
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_query TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                model_used VARCHAR(50),
                importance_score INTEGER DEFAULT 5,
                tags TEXT,  -- JSON 배열
                session_id VARCHAR(50),
                token_count INTEGER,
                response_time_ms INTEGER,
                project_context TEXT,  -- 프로젝트 관련 컨텍스트 정보
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME  -- TTL 기반 자동 삭제용
            )
        """)

        # 대화 요약 테이블
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_range TEXT,  -- "2024-09-01 to 2024-09-07"
                summary TEXT,     -- AI 생성 요약
                conversation_count INTEGER,
                importance_level INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 중요 사실 테이블
        conn.execute("""
            CREATE TABLE IF NOT EXISTS important_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                category VARCHAR(100),  -- code, config, decision, etc.
                source_conversation_id INTEGER,
                user_marked BOOLEAN DEFAULT FALSE,
                ai_suggested BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
            )
        """)

        # 사용자 선호도 테이블
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 벡터 임베딩 테이블 (Qdrant 동기화용)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_embeddings (
                conversation_id INTEGER PRIMARY KEY,
                embedding_vector BLOB,  -- 임베딩 벡터 (로컬 폴백용)
                qdrant_point_id TEXT,   -- Qdrant 포인트 ID
                sync_status INTEGER DEFAULT 0,  -- 0: 대기, 1: 동기화 완료, -1: 실패
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # FTS5 전문 검색 테이블
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                user_query,
                ai_response,
                content='conversations',
                content_rowid='id'
            )
        """)

        # 인덱스 생성
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_importance ON conversations(importance_score)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_expires_at ON conversations(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_model_used ON conversations(model_used)",
            "CREATE INDEX IF NOT EXISTS idx_important_facts_category ON important_facts(category)",
            "CREATE INDEX IF NOT EXISTS idx_conversation_embeddings_sync_status ON conversation_embeddings(sync_status)"
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        # FTS5 트리거 (자동 동기화)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_insert AFTER INSERT ON conversations
            BEGIN
                INSERT INTO conversations_fts(rowid, user_query, ai_response)
                VALUES (NEW.id, NEW.user_query, NEW.ai_response);
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_update AFTER UPDATE ON conversations
            BEGIN
                UPDATE conversations_fts SET
                    user_query = NEW.user_query,
                    ai_response = NEW.ai_response
                WHERE rowid = NEW.id;
            END
        """)

        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_ai_delete AFTER DELETE ON conversations
            BEGIN
                DELETE FROM conversations_fts WHERE rowid = OLD.id;
            END
        """)

    def calculate_importance_score(self, user_query: str, ai_response: str,
                                 model_used: str = None, context: Dict = None) -> int:
        """
        대화의 중요도 점수 자동 계산 (1-10)
        """
        score = 5  # 기본값
        context = context or {}

        query_lower = user_query.lower()
        response_lower = ai_response.lower()
        combined_text = f"{query_lower} {response_lower}"

        # 높은 중요도 키워드
        high_importance_keywords = [
            # 기술 설정
            "설정", "config", "configuration", "환경변수", "environment",
            "architecture", "design pattern", "아키텍처", "설계",

            # 문제 해결
            "버그", "에러", "오류", "문제", "해결", "fix", "bug", "error",
            "issue", "problem", "solution", "trouble",

            # 중요 개발
            "구현", "implementation", "알고리즘", "algorithm", "최적화",
            "optimization", "performance", "성능", "보안", "security",

            # 결정사항
            "결정", "decision", "정책", "policy", "방향", "direction",
            "전략", "strategy", "계획", "plan"
        ]

        # 낮은 중요도 키워드
        low_importance_keywords = [
            "안녕", "hello", "hi", "테스트", "test", "확인", "check",
            "감사", "thank", "좋아", "좋다", "괜찮", "ok", "okay"
        ]

        # 키워드 기반 점수 조정
        high_count = sum(1 for keyword in high_importance_keywords if keyword in combined_text)
        low_count = sum(1 for keyword in low_importance_keywords if keyword in combined_text)

        score += min(high_count, 3)  # 최대 +3
        score -= min(low_count, 2)   # 최대 -2

        # 응답 길이 고려 (긴 응답 = 더 상세한 정보)
        response_length = len(ai_response)
        if response_length > 2000:
            score += 2
        elif response_length > 1000:
            score += 1
        elif response_length < 100:
            score -= 1

        # 코드 포함 여부
        code_patterns = [
            r'```[\s\S]*?```',  # 코드 블록
            r'`[^`]+`',         # 인라인 코드
            r'def\s+\w+',       # Python 함수
            r'function\s+\w+',  # JavaScript 함수
            r'class\s+\w+',     # 클래스 정의
            r'import\s+\w+',    # Import 문
            r'SELECT\s+.*FROM', # SQL 쿼리
        ]

        for pattern in code_patterns:
            if re.search(pattern, ai_response, re.IGNORECASE):
                score += 1
                break

        # 모델 타입 고려
        if model_used == "code-7b":
            score += 1  # 코딩 모델 사용시 +1

        # 사용자 피드백 반영
        if context.get("user_saved", False):
            score = 10  # 사용자가 명시적으로 저장한 경우
        elif context.get("user_important", False):
            score = max(score, 8)

        # 질문 길이 고려 (상세한 질문일수록 중요)
        if len(user_query) > 200:
            score += 1

        return max(1, min(10, score))

    def save_conversation(self, project_id: str, user_query: str, ai_response: str,
                         model_used: str = None, session_id: str = None,
                         token_count: int = None, response_time_ms: int = None,
                         context: Dict = None, tags: List[str] = None) -> Optional[int]:
        """
        대화를 데이터베이스에 저장
        권한 오류 시 None 반환
        """
        if not self._storage_available:
            return None

        try:
            context = context or {}
            importance_score = self.calculate_importance_score(
                user_query, ai_response, model_used, context
            )

            # TTL 계산
            ttl_days = self.IMPORTANCE_LEVELS[importance_score]["ttl_days"]
            expires_at = None
            if ttl_days > 0:
                expires_at = datetime.now() + timedelta(days=ttl_days)

            with self.transaction(project_id) as conn:
                cursor = conn.execute("""
                    INSERT INTO conversations (
                        user_query, ai_response, model_used, importance_score,
                        tags, session_id, token_count, response_time_ms,
                        project_context, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_query, ai_response, model_used, importance_score,
                    json.dumps(tags or [], ensure_ascii=False), session_id,
                    token_count, response_time_ms, json.dumps(context, ensure_ascii=False),
                    expires_at
                ))

                conversation_id = cursor.lastrowid

                # 임베딩 큐에 추가 (나중에 비동기 처리)
                conn.execute("""
                    INSERT INTO conversation_embeddings (conversation_id, sync_status)
                    VALUES (?, 0)
                """, (conversation_id,))

                return conversation_id

        except (OSError, PermissionError) as e:
            print(f"⚠️ Cannot save conversation to memory: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Memory save error: {e}")
            return None

    def search_conversations(self, project_id: str, query: str = None,
                           importance_min: int = None, limit: int = 10,
                           offset: int = 0) -> List[Dict[str, Any]]:
        """
        대화 검색 (키워드 + 중요도 필터)
        """
        if not self._storage_available:
            return []

        try:
            with self.transaction(project_id) as conn:
                if query:
                    # FTS5 전문 검색
                    cursor = conn.execute("""
                        SELECT c.* FROM conversations c
                        JOIN conversations_fts fts ON c.id = fts.rowid
                        WHERE conversations_fts MATCH ?
                        AND (? IS NULL OR c.importance_score >= ?)
                        ORDER BY c.timestamp DESC
                        LIMIT ? OFFSET ?
                    """, (query, importance_min, importance_min, limit, offset))
                else:
                    # 일반 검색
                    cursor = conn.execute("""
                        SELECT * FROM conversations
                        WHERE (? IS NULL OR importance_score >= ?)
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    """, (importance_min, importance_min, limit, offset))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['tags'] = json.loads(result['tags'] or '[]')
                    result['project_context'] = json.loads(result['project_context'] or '{}')
                    results.append(result)

                return results

        except (OSError, PermissionError) as e:
            print(f"⚠️ Cannot search conversations: {e}")
            return []
        except Exception as e:
            print(f"⚠️ Search error: {e}")
            return []

    def get_conversation_stats(self, project_id: str) -> Dict[str, Any]:
        """프로젝트 메모리 통계"""
        if not self._storage_available:
            return {
                'total_conversations': 0,
                'avg_importance': 0,
                'oldest_conversation': None,
                'latest_conversation': None,
                'importance_distribution': {},
                'model_usage': {}
            }

        try:
            with self.transaction(project_id) as conn:
                # 기본 통계
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total_conversations,
                        AVG(importance_score) as avg_importance,
                        MIN(timestamp) as oldest_conversation,
                        MAX(timestamp) as latest_conversation
                    FROM conversations
                """)
                stats = dict(cursor.fetchone())

                # 중요도별 분포
                cursor = conn.execute("""
                    SELECT importance_score, COUNT(*) as count
                    FROM conversations
                    GROUP BY importance_score
                    ORDER BY importance_score
                """)
                stats['importance_distribution'] = {
                    row['importance_score']: row['count']
                    for row in cursor.fetchall()
                }

                # 모델별 사용량
                cursor = conn.execute("""
                    SELECT model_used, COUNT(*) as count
                    FROM conversations
                    WHERE model_used IS NOT NULL
                    GROUP BY model_used
                """)
                stats['model_usage'] = {
                    row['model_used']: row['count']
                    for row in cursor.fetchall()
                }

                return stats

        except (OSError, PermissionError) as e:
            print(f"⚠️ Cannot get conversation stats: {e}")
            return {
                'total_conversations': 0,
                'avg_importance': 0,
                'oldest_conversation': None,
                'latest_conversation': None,
                'importance_distribution': {},
                'model_usage': {}
            }
        except Exception as e:
            print(f"⚠️ Stats error: {e}")
            return {
                'total_conversations': 0,
                'avg_importance': 0,
                'oldest_conversation': None,
                'latest_conversation': None,
                'importance_distribution': {},
                'model_usage': {}
            }

# 글로벌 메모리 시스템 인스턴스
_current_instance = None

def get_memory_system() -> MemorySystem:
    """현재 활성화된 메모리 시스템 인스턴스 반환"""
    global _current_instance
    if _current_instance is None:
        _current_instance = MemorySystem()
    return _current_instance

def set_memory_system(instance: MemorySystem):
    """메모리 시스템 인스턴스 변경"""
    global _current_instance
    _current_instance = instance

# 기본 인스턴스 생성 (하위 호환성)
memory_system = get_memory_system()