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
# Vector search dependencies (optional)
try:
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    VECTOR_DEPS_AVAILABLE = True
except ImportError:
    VECTOR_DEPS_AVAILABLE = False
    # Mock classes for type hints when dependencies are not available
    class QdrantClient:
        pass
    class qmodels:
        class VectorParams:
            pass
        class Distance:
            COSINE = None
        class PointStruct:
            pass

class MemorySystem:
    def __init__(self, data_dir: str = None):
        self.data_dir = self._get_data_directory(data_dir)
        self._local = threading.local()
        self._storage_available = True

        # 임베딩 및 벡터 검색 설정
        self.embedding_url = os.getenv("EMBEDDING_URL", "http://localhost:8003")
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self._qdrant_client = None
        self._embedding_dim = None
        self._vector_enabled = VECTOR_DEPS_AVAILABLE

        if not VECTOR_DEPS_AVAILABLE:
            print("💡 Vector search dependencies not available. Text search only.")

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
        Docker 환경에서는 중앙집중식 메모리 디렉토리 사용
        """
        # Docker 환경에서는 환경변수 우선
        default_project_id = os.getenv('DEFAULT_PROJECT_ID')
        if default_project_id:
            return default_project_id

        if project_path is None:
            project_path = os.getcwd()

        project_path = Path(project_path).resolve()

        # Docker 환경 감지 (/.dockerenv 파일 존재 여부)
        if Path("/.dockerenv").exists():
            # Docker 환경에서는 중앙집중식 저장소 사용
            # 실제 경로: /app/memory/projects/docker-default
            memory_dir = self.projects_dir / "docker-default"
            project_file = memory_dir / "project.json"
        else:
            # 로컬 환경에서는 프로젝트별 .ai-memory 디렉토리 사용
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                embedding_vector TEXT,  -- JSON 형태 임베딩 벡터 (로컬 폴백용)
                qdrant_point_id TEXT,   -- Qdrant 포인트 ID
                sync_status TEXT DEFAULT 'pending',  -- 'pending', 'synced', 'failed'
                synced_at DATETIME,     -- 동기화 완료 시각
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                UNIQUE(conversation_id)  -- 한 대화당 하나의 임베딩
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
                    VALUES (?, 'pending')
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
                           offset: int = 0, use_advanced_ranking: bool = True) -> List[Dict[str, Any]]:
        """
        대화 검색 (키워드 + 중요도 필터 + 고급 랭킹)
        """
        if not self._storage_available:
            return []

        try:
            with self.transaction(project_id) as conn:
                if query:
                    if use_advanced_ranking:
                        # 고급 FTS5 검색 (BM25 + 중요도 가중치)
                        cursor = conn.execute("""
                            SELECT c.*,
                                   bm25(conversations_fts) as relevance_score,
                                   (bm25(conversations_fts) + (c.importance_score * 0.1)) as combined_score
                            FROM conversations c
                            JOIN conversations_fts fts ON c.id = fts.rowid
                            WHERE conversations_fts MATCH ?
                            AND (? IS NULL OR c.importance_score >= ?)
                            ORDER BY combined_score DESC, c.timestamp DESC
                            LIMIT ? OFFSET ?
                        """, (query, importance_min, importance_min, limit, offset))
                    else:
                        # 기본 FTS5 검색
                        cursor = conn.execute("""
                            SELECT c.* FROM conversations c
                            JOIN conversations_fts fts ON c.id = fts.rowid
                            WHERE conversations_fts MATCH ?
                            AND (? IS NULL OR c.importance_score >= ?)
                            ORDER BY c.timestamp DESC
                            LIMIT ? OFFSET ?
                        """, (query, importance_min, importance_min, limit, offset))
                else:
                    # 일반 검색 (중요도 기반)
                    cursor = conn.execute("""
                        SELECT * FROM conversations
                        WHERE (? IS NULL OR importance_score >= ?)
                        ORDER BY importance_score DESC, timestamp DESC
                        LIMIT ? OFFSET ?
                    """, (importance_min, importance_min, limit, offset))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['tags'] = json.loads(result['tags'] or '[]')
                    result['project_context'] = json.loads(result['project_context'] or '{}')
                    # 검색 점수 정보 포함
                    if 'relevance_score' in result:
                        result['search_metadata'] = {
                            'relevance_score': result.get('relevance_score', 0),
                            'combined_score': result.get('combined_score', 0),
                            'search_type': 'fts5_advanced'
                        }
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

    # ============ 벡터 임베딩 및 검색 메서드 ============

    def _get_qdrant_client(self) -> Optional[QdrantClient]:
        """Qdrant 클라이언트 초기화 및 반환"""
        if not self._vector_enabled:
            return None

        if self._qdrant_client is None:
            try:
                self._qdrant_client = QdrantClient(url=self.qdrant_url, timeout=30.0)
                # 연결 테스트
                _ = self._qdrant_client.get_collections()
            except Exception as e:
                print(f"⚠️ Qdrant connection failed: {e}")
                print("💡 Vector search will be disabled for this session.")
                self._vector_enabled = False
                return None

        return self._qdrant_client

    async def _get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """FastEmbed 서비스를 통해 텍스트 임베딩 생성"""
        if not self._vector_enabled or not texts:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embedding_url}/embed",
                    json={"texts": texts}
                )
                response.raise_for_status()
                data = response.json()

                # 차원 정보 저장
                if self._embedding_dim is None:
                    self._embedding_dim = data.get('dim', 384)

                return data['embeddings']

        except Exception as e:
            print(f"⚠️ Embedding generation failed: {e}")
            return None


    async def _store_conversation_vectors(self, project_id: str, conversation_id: int,
                                        user_query: str, ai_response: str):
        """대화 벡터를 Qdrant에 저장"""
        if not self._vector_enabled:
            return

        try:
            # 대화 텍스트 결합 (검색용)
            combined_text = f"Q: {user_query}\nA: {ai_response}"

            # 임베딩 생성
            embeddings = await self._get_embeddings([combined_text])
            if not embeddings:
                return

            # Qdrant에 저장
            qdrant = self._get_qdrant_client()
            if not qdrant:
                return

            collection_name = f"memory_{project_id[:8]}"
            if not self.ensure_memory_collection(project_id):
                return

            # 포인트 생성
            point = qmodels.PointStruct(
                id=conversation_id,
                vector=embeddings[0],
                payload={
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "user_query": user_query[:500],  # 페이로드 크기 제한
                    "ai_response": ai_response[:1000],
                    "timestamp": datetime.now().isoformat(),
                    "combined_text": combined_text[:1500]
                }
            )

            qdrant.upsert(collection_name=collection_name, points=[point])

            # SQLite에 동기화 상태 업데이트
            with self.transaction(project_id) as conn:
                conn.execute("""
                    UPDATE conversation_embeddings
                    SET sync_status = 'synced', synced_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = ?
                """, (conversation_id,))

        except Exception as e:
            print(f"⚠️ Vector storage failed: {e}")
            # 실패 시 상태 업데이트
            try:
                with self.transaction(project_id) as conn:
                    conn.execute("""
                        UPDATE conversation_embeddings
                        SET sync_status = 'failed'
                        WHERE conversation_id = ?
                    """, (conversation_id,))
            except:
                pass  # 메타데이터 업데이트 실패해도 원본 오류가 중요

    async def vector_search_conversations(self, project_id: str, query: str,
                                        limit: int = 5, score_threshold: float = 0.7) -> List[Dict]:
        """벡터 유사도 기반 대화 검색"""
        if not self._vector_enabled:
            return []

        try:
            # 쿼리 임베딩 생성
            embeddings = await self._get_embeddings([query])
            if not embeddings:
                return []

            # Qdrant에서 검색
            qdrant = self._get_qdrant_client()
            if not qdrant:
                return []

            collection_name = f"memory_{project_id[:8]}"

            # 컬렉션 존재 확인
            if not self.ensure_memory_collection(project_id):
                return []

            search_result = qdrant.search(
                collection_name=collection_name,
                query_vector=embeddings[0],
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )

            # 결과 변환
            results = []
            for hit in search_result:
                results.append({
                    'conversation_id': hit.payload['conversation_id'],
                    'user_query': hit.payload['user_query'],
                    'ai_response': hit.payload['ai_response'],
                    'similarity_score': hit.score,
                    'timestamp': hit.payload['timestamp']
                })

            return results

        except Exception as e:
            print(f"⚠️ Vector search failed: {e}")
            return []

    async def process_pending_embeddings(self, project_id: str, batch_size: int = 10):
        """대기 중인 대화들의 임베딩을 배치 처리"""
        if not self._vector_enabled:
            return 0

        try:
            with self.transaction(project_id) as conn:
                # 대기 중인 대화들 조회
                cursor = conn.execute("""
                    SELECT ce.conversation_id, c.user_query, c.ai_response
                    FROM conversation_embeddings ce
                    JOIN conversations c ON ce.conversation_id = c.id
                    WHERE ce.sync_status = 'pending'
                    ORDER BY c.timestamp
                    LIMIT ?
                """, (batch_size,))

                pending_conversations = cursor.fetchall()

            if not pending_conversations:
                return 0

            # 배치로 처리 (개별 실패 처리)
            processed = 0
            for conv in pending_conversations:
                try:
                    await self._store_conversation_vectors(
                        project_id=project_id,
                        conversation_id=conv['conversation_id'],
                        user_query=conv['user_query'],
                        ai_response=conv['ai_response']
                    )
                    processed += 1
                except Exception as e:
                    print(f"⚠️ Failed to process conversation {conv['conversation_id']}: {e}")
                    # 개별 실패 시 해당 대화만 failed 상태로 마킹
                    try:
                        with self.transaction(project_id) as conn:
                            conn.execute("""
                                UPDATE conversation_embeddings
                                SET sync_status = 'failed'
                                WHERE conversation_id = ?
                            """, (conv['conversation_id'],))
                    except:
                        pass  # 상태 업데이트 실패해도 다음 대화 계속 처리

            return processed

        except Exception as e:
            print(f"⚠️ Embedding batch processing failed: {e}")
            return 0

    async def hybrid_search_conversations(self, project_id: str, query: str,
                                        limit: int = 10, combine_results: bool = True) -> List[Dict]:
        """하이브리드 검색 (FTS5 + 벡터 유사도)"""
        # FTS5 검색 결과
        fts_results = self.search_conversations(project_id, query, limit=limit)

        # 벡터 검색 결과
        vector_results = await self.vector_search_conversations(
            project_id, query, limit=limit, score_threshold=0.6
        )

        if not combine_results:
            return {
                'fts_results': fts_results,
                'vector_results': vector_results
            }

        # 결과 결합 및 중복 제거
        combined_results = {}

        # FTS5 결과 추가 (높은 가중치)
        for result in fts_results:
            conv_id = result['id']
            combined_results[conv_id] = {
                **result,
                'search_score': 1.0,  # FTS5는 기본 점수 1.0
                'search_method': 'fts5'
            }

        # 벡터 결과 추가 또는 점수 보강
        for result in vector_results:
            conv_id = result['conversation_id']
            if conv_id in combined_results:
                # 이미 있는 경우 점수 보강
                combined_results[conv_id]['search_score'] = max(
                    combined_results[conv_id]['search_score'],
                    result['similarity_score']
                )
                combined_results[conv_id]['search_method'] = 'hybrid'
                combined_results[conv_id]['similarity_score'] = result['similarity_score']
            else:
                # 새로 추가
                combined_results[conv_id] = {
                    'id': conv_id,
                    'user_query': result['user_query'],
                    'ai_response': result['ai_response'],
                    'timestamp': result['timestamp'],
                    'search_score': result['similarity_score'],
                    'similarity_score': result['similarity_score'],
                    'search_method': 'vector'
                }

        # 점수순 정렬 후 제한
        final_results = sorted(
            combined_results.values(),
            key=lambda x: x['search_score'],
            reverse=True
        )[:limit]

        return final_results

    # ============ 추가 유틸리티 메서드 ============

    def rebuild_fts_index(self, project_id: str) -> bool:
        """FTS5 인덱스 재구축"""
        try:
            with self.transaction(project_id) as conn:
                # FTS5 테이블 데이터 정리 및 재구축
                conn.execute("DELETE FROM conversations_fts")
                conn.execute("""
                    INSERT INTO conversations_fts(rowid, user_query, ai_response)
                    SELECT id, user_query, ai_response FROM conversations
                """)
                return True
        except Exception as e:
            print(f"⚠️ FTS index rebuild failed: {e}")
            return False

    def ensure_memory_collection(self, project_id: str) -> bool:
        """Qdrant 메모리 컬렉션 존재 확인 및 생성"""
        try:
            collection_name = f"memory_{project_id[:8]}"

            # HTTP API로 컬렉션 확인
            import requests
            response = requests.get(f"{self.qdrant_url}/collections/{collection_name}")

            if response.status_code == 404:
                # 컬렉션 생성
                create_data = {
                    "vectors": {
                        "size": 384,  # BAAI/bge-small-en-v1.5 차원
                        "distance": "Cosine"
                    }
                }

                response = requests.put(
                    f"{self.qdrant_url}/collections/{collection_name}",
                    json=create_data,
                    timeout=30
                )

                if response.status_code == 200:
                    print(f"✅ Qdrant 컬렉션 생성됨: {collection_name}")
                    # 컬렉션 생성 성공 시 벡터 기능 자동 활성화
                    if not self._vector_enabled:
                        self._vector_enabled = True
                        print(f"🔄 벡터 검색 기능 자동 복구됨")
                    return True
                else:
                    print(f"⚠️ Qdrant 컬렉션 생성 실패: {response.status_code}")
                    return False
            elif response.status_code == 200:
                # 컬렉션 존재 확인 성공 시 벡터 기능 자동 활성화
                if not self._vector_enabled:
                    self._vector_enabled = True
                    print(f"🔄 벡터 검색 기능 자동 복구됨")
                return True
            else:
                print(f"⚠️ Qdrant 컬렉션 확인 실패: {response.status_code}")
                return False

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Qdrant 컬렉션 처리 실패, 벡터 기능 비활성화: {e}")
            self._vector_enabled = False
            print(f"⚠️ Qdrant 컬렉션 처리 실패, FTS 전용 모드로 전환: {e}")
            return False

    def try_vector_recovery(self, project_id: str = None) -> bool:
        """벡터 기능 복구 시도"""
        if self._vector_enabled:
            return True  # 이미 활성화됨

        if not VECTOR_DEPS_AVAILABLE:
            return False  # 의존성 없음

        try:
            # 기본 프로젝트 ID 사용
            if not project_id:
                project_id = os.getenv('DEFAULT_PROJECT_ID', 'default-project')

            # Qdrant 연결 테스트
            result = self.ensure_memory_collection(project_id)
            if result:
                print(f"✅ 벡터 기능 복구 성공")
                return True
            else:
                return False

        except Exception as e:
            print(f"⚠️ 벡터 기능 복구 실패: {e}")
            return False

    def export_memory_backup(self, project_id: str, output_path: Path = None) -> Optional[Path]:
        """메모리 DB를 JSON으로 백업"""
        if not self._storage_available:
            return None

        try:
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = self.data_dir / "backups" / f"memory_{project_id}_{timestamp}.json"
                output_path.parent.mkdir(parents=True, exist_ok=True)

            with self.transaction(project_id) as conn:
                conn.row_factory = sqlite3.Row

                export_data = {
                    "export_time": datetime.now().isoformat(),
                    "project_id": project_id,
                    "conversations": [],
                    "embeddings": [],
                    "summaries": [],
                    "important_facts": [],
                    "user_preferences": []
                }

                # 모든 테이블 데이터 내보내기
                tables = [
                    ("conversations", "conversations"),
                    ("conversation_embeddings", "embeddings"),
                    ("conversation_summaries", "summaries"),
                    ("important_facts", "important_facts"),
                    ("user_preferences", "user_preferences")
                ]

                for table_name, export_key in tables:
                    cursor = conn.execute(f"SELECT * FROM {table_name}")
                    for row in cursor.fetchall():
                        export_data[export_key].append(dict(row))

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            return output_path

        except Exception as e:
            print(f"⚠️ 백업 실패: {e}")
            return None

    def import_memory_backup(self, project_id: str, backup_path: Path) -> bool:
        """JSON 백업에서 메모리 복원"""
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            with self.transaction(project_id) as conn:
                # 기존 데이터 정리 (선택적)
                confirmation = input("기존 데이터를 삭제하고 복원하시겠습니까? (y/N): ")
                if confirmation.lower() == 'y':
                    conn.execute("DELETE FROM conversation_embeddings")
                    conn.execute("DELETE FROM conversations")
                    conn.execute("DELETE FROM conversation_summaries")
                    conn.execute("DELETE FROM important_facts")
                    conn.execute("DELETE FROM user_preferences")

                # 데이터 복원
                for conversation in backup_data.get("conversations", []):
                    conn.execute("""
                        INSERT OR REPLACE INTO conversations (
                            id, timestamp, user_query, ai_response, model_used,
                            importance_score, tags, session_id, token_count,
                            response_time_ms, project_context, created_at,
                            updated_at, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        conversation.get('id'), conversation.get('timestamp'),
                        conversation.get('user_query'), conversation.get('ai_response'),
                        conversation.get('model_used'), conversation.get('importance_score'),
                        conversation.get('tags'), conversation.get('session_id'),
                        conversation.get('token_count'), conversation.get('response_time_ms'),
                        conversation.get('project_context'), conversation.get('created_at'),
                        conversation.get('updated_at'), conversation.get('expires_at')
                    ))

                # 다른 테이블들도 복원...
                # (간단하게 하기 위해 conversations만 예시)

                # FTS5 인덱스 재구축
                self.rebuild_fts_index(project_id)

            print(f"✅ 백업 복원 완료: {backup_path}")
            return True

        except Exception as e:
            print(f"⚠️ 백업 복원 실패: {e}")
            return False

    def cleanup_expired_conversations(self, project_id: str) -> int:
        """TTL 만료된 대화 정리"""
        try:
            with self.transaction(project_id) as conn:
                cursor = conn.execute("""
                    DELETE FROM conversations
                    WHERE expires_at IS NOT NULL
                    AND expires_at < ?
                """, (datetime.now().isoformat(),))

                deleted_count = cursor.rowcount

                # 고아 임베딩 정리
                conn.execute("""
                    DELETE FROM conversation_embeddings
                    WHERE conversation_id NOT IN (
                        SELECT id FROM conversations
                    )
                """)

                if deleted_count > 0:
                    print(f"✅ TTL 정리 완료: {deleted_count}개 대화 삭제")

                return deleted_count

        except Exception as e:
            print(f"⚠️ TTL 정리 실패: {e}")
            return 0

    def optimize_database(self, project_id: str) -> bool:
        """데이터베이스 최적화 (VACUUM, ANALYZE)"""
        try:
            with self.transaction(project_id) as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                print(f"✅ 데이터베이스 최적화 완료: {project_id}")
                return True
        except Exception as e:
            print(f"⚠️ 데이터베이스 최적화 실패: {e}")
            return False

    def get_qdrant_sync_queue(self, project_id: str, limit: int = 100,
                            include_failed: bool = False) -> List[Dict]:
        """Qdrant 동기화 대기열 조회"""
        try:
            with self.transaction(project_id) as conn:
                if include_failed:
                    # 실패한 것도 포함 (재시도용)
                    cursor = conn.execute("""
                        SELECT ce.*, c.user_query, c.ai_response, c.model_used, c.importance_score
                        FROM conversation_embeddings ce
                        JOIN conversations c ON ce.conversation_id = c.id
                        WHERE ce.sync_status IN ('pending', 'failed')
                        ORDER BY
                            CASE WHEN ce.sync_status = 'pending' THEN 0 ELSE 1 END,
                            c.importance_score DESC,
                            c.created_at
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor = conn.execute("""
                        SELECT ce.*, c.user_query, c.ai_response, c.model_used, c.importance_score
                        FROM conversation_embeddings ce
                        JOIN conversations c ON ce.conversation_id = c.id
                        WHERE ce.sync_status = 'pending'
                        ORDER BY c.importance_score DESC, c.created_at
                        LIMIT ?
                    """, (limit,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"⚠️ 동기화 큐 조회 실패: {e}")
            return []

    def batch_sync_to_qdrant(self, project_id: str, batch_size: int = 64) -> Dict[str, int]:
        """Qdrant 배치 동기화 (개선된 처리)"""
        sync_stats = {"synced": 0, "failed": 0, "skipped": 0}

        # 벡터 기능이 비활성화된 경우 즉시 반환
        if not self._vector_enabled:
            return sync_stats

        try:
            # 컬렉션 먼저 확인/생성
            if not self.ensure_memory_collection(project_id):
                return sync_stats

            # 대기열 조회
            sync_queue = self.get_qdrant_sync_queue(project_id, batch_size, include_failed=True)
            if not sync_queue:
                return sync_stats

            # 임베딩 생성이 필요한 항목들
            texts_to_embed = []
            items_map = {}

            for item in sync_queue:
                conv_id = item['conversation_id']
                combined_text = f"Q: {item['user_query']}\nA: {item['ai_response']}"
                texts_to_embed.append(combined_text)
                items_map[len(texts_to_embed) - 1] = item

            # 배치 임베딩 생성
            import requests
            try:
                response = requests.post(
                    f"{self.embedding_url}/embed",
                    json={"texts": texts_to_embed},
                    timeout=60
                )
                response.raise_for_status()
                embeddings_data = response.json()
                embeddings = embeddings_data['embeddings']
            except Exception as e:
                print(f"⚠️ 배치 임베딩 생성 실패: {e}")
                # 모든 항목을 failed로 마킹
                self._mark_embeddings_failed(project_id, [item['conversation_id'] for item in sync_queue])
                sync_stats["failed"] = len(sync_queue)
                return sync_stats

            # Qdrant에 배치 업로드
            collection_name = f"memory_{project_id[:8]}"
            points_data = []

            for idx, embedding in enumerate(embeddings):
                item = items_map[idx]  # items_map은 배치 인덱스 → 대화 정보 구조

                point = {
                    "id": item['conversation_id'],
                    "vector": embedding,
                    "payload": {
                        "conversation_id": item['conversation_id'],
                        "project_id": project_id,
                        "user_query": item['user_query'][:500],
                        "ai_response": item['ai_response'][:1000],
                        "model_used": item.get('model_used', ''),
                        "importance_score": item.get('importance_score', 5),
                        "created_at": item['created_at']
                    }
                }
                points_data.append(point)

            # Qdrant 배치 업로드
            try:
                response = requests.put(
                    f"{self.qdrant_url}/collections/{collection_name}/points",
                    json={"points": points_data},
                    timeout=60
                )
                response.raise_for_status()

                # 성공한 항목들 상태 업데이트
                with self.transaction(project_id) as conn:
                    for idx, item in enumerate(sync_queue):
                        conn.execute("""
                            UPDATE conversation_embeddings
                            SET sync_status = 'synced',
                                synced_at = ?,
                                embedding_vector = ?
                            WHERE conversation_id = ?
                        """, (
                            datetime.now().isoformat(),
                            json.dumps(embeddings[idx]),  # 배치 인덱스 사용
                            item['conversation_id']
                        ))

                sync_stats["synced"] = len(sync_queue)

            except Exception as e:
                print(f"⚠️ Qdrant 배치 업로드 실패: {e}")
                self._mark_embeddings_failed(project_id, [item['conversation_id'] for item in sync_queue])
                sync_stats["failed"] = len(sync_queue)

            return sync_stats

        except Exception as e:
            print(f"⚠️ 배치 동기화 실패: {e}")
            return sync_stats

    def _mark_embeddings_failed(self, project_id: str, conversation_ids: List[int]):
        """임베딩 동기화 실패 상태로 마킹"""
        try:
            with self.transaction(project_id) as conn:
                placeholders = ','.join(['?' for _ in conversation_ids])
                conn.execute(f"""
                    UPDATE conversation_embeddings
                    SET sync_status = 'failed'
                    WHERE conversation_id IN ({placeholders})
                """, conversation_ids)
        except Exception as e:
            print(f"⚠️ 실패 상태 마킹 실패: {e}")

    def retry_failed_syncs(self, project_id: str, max_retries: int = 3) -> Dict[str, int]:
        """실패한 동기화 재시도"""
        stats = {"retried": 0, "succeeded": 0, "still_failed": 0}

        try:
            # 실패한 항목들 중 재시도 횟수가 적은 것들 조회
            with self.transaction(project_id) as conn:
                cursor = conn.execute("""
                    SELECT ce.conversation_id, c.user_query, c.ai_response
                    FROM conversation_embeddings ce
                    JOIN conversations c ON ce.conversation_id = c.id
                    WHERE ce.sync_status = 'failed'
                    LIMIT 50
                """)

                failed_items = cursor.fetchall()

            if not failed_items:
                return stats

            # 개별 재시도 (배치보다 안전)
            for item in failed_items:
                try:
                    # 재시도
                    combined_text = f"Q: {item['user_query']}\nA: {item['ai_response']}"

                    # 임베딩 생성
                    response = requests.post(
                        f"{self.embedding_url}/embed",
                        json={"texts": [combined_text]},
                        timeout=30
                    )
                    response.raise_for_status()
                    embedding = response.json()['embeddings'][0]

                    # Qdrant 업로드
                    collection_name = f"memory_{project_id[:8]}"
                    point_data = {
                        "points": [{
                            "id": item['conversation_id'],
                            "vector": embedding,
                            "payload": {
                                "conversation_id": item['conversation_id'],
                                "project_id": project_id,
                                "user_query": item['user_query'][:500],
                                "ai_response": item['ai_response'][:1000],
                                "retry_attempt": True
                            }
                        }]
                    }

                    response = requests.put(
                        f"{self.qdrant_url}/collections/{collection_name}/points",
                        json=point_data,
                        timeout=30
                    )
                    response.raise_for_status()

                    # 성공 시 상태 업데이트
                    with self.transaction(project_id) as conn:
                        conn.execute("""
                            UPDATE conversation_embeddings
                            SET sync_status = 'synced',
                                synced_at = ?,
                                embedding_vector = ?
                            WHERE conversation_id = ?
                        """, (
                            datetime.now().isoformat(),
                            json.dumps(embedding),
                            item['conversation_id']
                        ))

                    stats["succeeded"] += 1

                except Exception as e:
                    print(f"⚠️ 재시도 실패 - 대화 {item['conversation_id']}: {e}")
                    stats["still_failed"] += 1

                stats["retried"] += 1

            return stats

        except Exception as e:
            print(f"⚠️ 재시도 처리 실패: {e}")
            return stats

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