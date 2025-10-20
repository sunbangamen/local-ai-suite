"""
AI Analytics Database - Integrated Usage Tracking and Optimization
- AI CLI usage patterns and model selection tracking
- Performance analytics and smart recommendations
- Integration with RAG analytics for comprehensive insights
"""

import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path
import threading
from contextlib import contextmanager


DEFAULT_CHAT_MODEL = os.getenv("API_GATEWAY_CHAT_MODEL", "chat-7b")
ANALYTICS_ENABLED = True  # Global flag for analytics availability


class AIAnalytics:
    def __init__(self, db_path: str = None):
        self.db_path = self._get_database_path(db_path)
        self._local = threading.local()
        self._init_schema()

    def _get_database_path(self, custom_path: str = None) -> str:
        """유연한 데이터베이스 경로 결정 로직"""
        candidates = []

        # 1. CLI/환경변수 우선순위
        if custom_path:
            candidates.append(custom_path)

        # AI_ANALYTICS_DB 환경변수
        if os.getenv("AI_ANALYTICS_DB"):
            candidates.append(os.getenv("AI_ANALYTICS_DB"))

        # AI_ANALYTICS_DIR 환경변수 + 기본 파일명
        if os.getenv("AI_ANALYTICS_DIR"):
            analytics_dir = os.getenv("AI_ANALYTICS_DIR")
            candidates.append(os.path.join(analytics_dir, "analytics.db"))

        # 2. 기본 경로
        candidates.append("/mnt/e/ai-data/analytics/analytics.db")

        # 3. Git 루트 폴백
        try:
            import subprocess

            git_root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            candidates.append(
                os.path.join(git_root, ".ai-analytics-data", "analytics.db")
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 4. 워킹 디렉터리 폴백
        candidates.append(
            os.path.join(os.getcwd(), ".ai-analytics-data", "analytics.db")
        )

        # 5. 홈 디렉터리 폴백 (최종)
        candidates.append(os.path.expanduser("~/.local/share/ai-suite/ai_analytics.db"))

        # 각 후보 경로 검증
        for candidate in candidates:
            try:
                candidate_path = Path(candidate).resolve()

                # 디렉터리 생성 시도
                candidate_path.parent.mkdir(parents=True, exist_ok=True)

                # 임시 쓰기 테스트
                test_file = candidate_path.parent / ".analytics_write_test"
                try:
                    test_file.write_text("test")
                    test_file.unlink()

                    # 성공 - 이 경로 사용
                    if str(candidate_path) != candidates[0]:  # 첫 번째 후보가 아닌 경우
                        if candidate == candidates[-1]:  # 홈 디렉터리 폴백
                            print(f"💡 Using local analytics storage: {candidate_path}")
                        else:
                            print(
                                f"💡 Using fallback analytics storage: {candidate_path}"
                            )

                    return str(candidate_path)

                except (OSError, PermissionError):
                    continue

            except (OSError, PermissionError):
                continue

        # 모든 경로 실패 시 - analytics 비활성화
        print("⚠️ Cannot find writable location for analytics database.")
        print("💡 Analytics will be disabled for this session.")
        global ANALYTICS_ENABLED
        ANALYTICS_ENABLED = False
        return None

    def _get_connection(self):
        """Thread-safe connection handling"""
        if self.db_path is None:
            raise RuntimeError("Analytics database path not available")

        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            # Performance optimizations
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")
        return self._local.connection

    @contextmanager
    def transaction(self):
        """Transaction context manager"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self):
        """Initialize database schema for AI analytics"""
        if self.db_path is None:
            return  # Analytics disabled, skip schema initialization

        with self.transaction() as conn:
            # AI CLI usage tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    query_hash TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    query_type TEXT NOT NULL,  -- 'chat', 'code', 'rag'
                    detected_type TEXT,        -- auto-detected type
                    model_used TEXT NOT NULL,
                    response_time_ms INTEGER,
                    tokens_used INTEGER,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    user_satisfaction INTEGER, -- 1-5 rating (inferred from re-queries)
                    session_id TEXT
                )
            """
            )

            # Model performance tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    query_type TEXT NOT NULL,
                    avg_response_time_ms REAL,
                    success_rate REAL,
                    total_usage_count INTEGER,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(model_name, query_type)
                )
            """
            )

            # Model recommendations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_pattern TEXT NOT NULL,
                    recommended_model TEXT NOT NULL,
                    confidence_score REAL,
                    reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """
            )

            # Usage patterns
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour_of_day INTEGER,
                    day_of_week INTEGER,
                    query_type TEXT,
                    usage_count INTEGER,
                    avg_response_time_ms REAL,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(hour_of_day, day_of_week, query_type)
                )
            """
            )

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_timestamp ON ai_usage(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_query_type ON ai_usage(query_type)",
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_model ON ai_usage(model_used)",
                "CREATE INDEX IF NOT EXISTS idx_model_performance_model ON model_performance(model_name)",
                "CREATE INDEX IF NOT EXISTS idx_usage_patterns_time ON usage_patterns(hour_of_day, day_of_week)",
            ]
            for idx in indexes:
                conn.execute(idx)

    def log_usage(
        self,
        query: str,
        query_type: str,
        detected_type: str,
        model_used: str,
        response_time_ms: int,
        tokens_used: int = 0,
        success: bool = True,
        error_message: str = None,
        session_id: str = None,
    ):
        """Log AI CLI usage for analytics"""
        if self.db_path is None:
            return  # Analytics disabled, skip logging

        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO ai_usage
                (query_hash, query_text, query_type, detected_type, model_used,
                 response_time_ms, tokens_used, success, error_message, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    query_hash,
                    query[:500],
                    query_type,
                    detected_type,
                    model_used,
                    response_time_ms,
                    tokens_used,
                    success,
                    error_message,
                    session_id,
                ),
            )

            # Update model performance statistics
            self._update_model_performance(
                conn, model_used, query_type, response_time_ms, success
            )

            # Update usage patterns
            now = datetime.now()
            self._update_usage_patterns(
                conn, now.hour, now.weekday(), query_type, response_time_ms
            )

    def _update_model_performance(
        self, conn, model: str, query_type: str, response_time_ms: int, success: bool
    ):
        """Update model performance statistics"""
        # Get current stats
        cursor = conn.execute(
            """
            SELECT avg_response_time_ms, success_rate, total_usage_count
            FROM model_performance
            WHERE model_name = ? AND query_type = ?
        """,
            (model, query_type),
        )

        row = cursor.fetchone()
        if row:
            # Update existing stats
            old_avg_time = row["avg_response_time_ms"] or 0
            old_success_rate = row["success_rate"] or 0
            old_count = row["total_usage_count"] or 0

            new_count = old_count + 1
            new_avg_time = ((old_avg_time * old_count) + response_time_ms) / new_count
            new_success_rate = (
                (old_success_rate * old_count) + (1 if success else 0)
            ) / new_count

            conn.execute(
                """
                UPDATE model_performance
                SET avg_response_time_ms = ?, success_rate = ?,
                    total_usage_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE model_name = ? AND query_type = ?
            """,
                (new_avg_time, new_success_rate, new_count, model, query_type),
            )
        else:
            # Insert new stats
            conn.execute(
                """
                INSERT INTO model_performance
                (model_name, query_type, avg_response_time_ms, success_rate, total_usage_count)
                VALUES (?, ?, ?, ?, 1)
            """,
                (model, query_type, response_time_ms, 1.0 if success else 0.0),
            )

    def _update_usage_patterns(
        self, conn, hour: int, day_of_week: int, query_type: str, response_time_ms: int
    ):
        """Update usage patterns"""
        cursor = conn.execute(
            """
            SELECT usage_count, avg_response_time_ms
            FROM usage_patterns
            WHERE hour_of_day = ? AND day_of_week = ? AND query_type = ?
        """,
            (hour, day_of_week, query_type),
        )

        row = cursor.fetchone()
        if row:
            old_count = row["usage_count"]
            old_avg = row["avg_response_time_ms"] or 0
            new_count = old_count + 1
            new_avg = ((old_avg * old_count) + response_time_ms) / new_count

            conn.execute(
                """
                UPDATE usage_patterns
                SET usage_count = ?, avg_response_time_ms = ?, last_updated = CURRENT_TIMESTAMP
                WHERE hour_of_day = ? AND day_of_week = ? AND query_type = ?
            """,
                (new_count, new_avg, hour, day_of_week, query_type),
            )
        else:
            conn.execute(
                """
                INSERT INTO usage_patterns
                (hour_of_day, day_of_week, query_type, usage_count, avg_response_time_ms)
                VALUES (?, ?, ?, 1, ?)
            """,
                (hour, day_of_week, query_type, response_time_ms),
            )

    def get_model_recommendation(
        self, query: str, query_type: str = None
    ) -> Dict[str, Any]:
        """Get smart model recommendation based on usage patterns"""
        if self.db_path is None:
            # Fallback to default model when analytics disabled
            return {
                "recommended_model": DEFAULT_CHAT_MODEL,
                "confidence": 0.5,
                "reason": "Default model (analytics disabled)",
            }

        with self.transaction() as conn:
            # Get current time context
            now = datetime.now()
            hour = now.hour
            day_of_week = now.weekday()

            # Get best performing model for this query type and time
            cursor = conn.execute(
                """
                SELECT mp.model_name, mp.avg_response_time_ms, mp.success_rate,
                       up.avg_response_time_ms as pattern_response_time
                FROM model_performance mp
                LEFT JOIN usage_patterns up ON
                    up.query_type = mp.query_type AND
                    up.hour_of_day = ? AND
                    up.day_of_week = ?
                WHERE mp.query_type = ? AND mp.total_usage_count >= 3
                ORDER BY
                    (mp.success_rate * 0.4 +
                     (1000.0 / COALESCE(NULLIF(mp.avg_response_time_ms, 0), 1000)) * 0.4 +
                     (1000.0 / COALESCE(NULLIF(up.avg_response_time_ms, 0), 1000)) * 0.2) DESC
                LIMIT 1
            """,
                (hour, day_of_week, query_type or "chat"),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "recommended_model": result["model_name"],
                    "avg_response_time": result["avg_response_time_ms"],
                    "success_rate": result["success_rate"],
                    "confidence": min(result["success_rate"], 1.0),
                    "reason": f"Best performance for {query_type} queries at this time",
                }

            # Fallback to overall best model
            return {
                "recommended_model": DEFAULT_CHAT_MODEL,
                "confidence": 0.5,
                "reason": "Default model (insufficient data for optimization)",
            }

    def get_analytics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive analytics summary"""
        if self.db_path is None:
            return {
                "usage_stats": [],
                "peak_times": [],
                "model_performance": [],
                "analysis_period_hours": hours,
                "generated_at": datetime.now().isoformat(),
                "status": "Analytics disabled",
            }

        cutoff = datetime.now() - timedelta(hours=hours)

        with self.transaction() as conn:
            # Usage statistics
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_queries,
                    AVG(response_time_ms) as avg_response_time,
                    AVG(tokens_used) as avg_tokens,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                    query_type,
                    model_used
                FROM ai_usage
                WHERE timestamp >= ?
                GROUP BY query_type, model_used
                ORDER BY total_queries DESC
            """,
                (cutoff,),
            )

            usage_stats = [dict(row) for row in cursor.fetchall()]

            # Peak usage times
            cursor = conn.execute(
                """
                SELECT hour_of_day, day_of_week, SUM(usage_count) as total_usage
                FROM usage_patterns
                GROUP BY hour_of_day, day_of_week
                ORDER BY total_usage DESC
                LIMIT 5
            """
            )

            peak_times = [dict(row) for row in cursor.fetchall()]

            # Model performance comparison
            cursor = conn.execute(
                """
                SELECT model_name, query_type, avg_response_time_ms,
                       success_rate, total_usage_count
                FROM model_performance
                WHERE total_usage_count >= 3
                ORDER BY success_rate DESC, avg_response_time_ms ASC
            """
            )

            model_performance = [dict(row) for row in cursor.fetchall()]

            return {
                "usage_stats": usage_stats,
                "peak_times": peak_times,
                "model_performance": model_performance,
                "analysis_period_hours": hours,
                "generated_at": datetime.now().isoformat(),
            }

    def optimize_database(self):
        """Run database optimization"""
        if self.db_path is None:
            return {
                "cleaned_records": 0,
                "database_size_mb": 0,
                "status": "Analytics disabled",
            }

        with self.transaction() as conn:
            # Clean old data (keep last 30 days)
            cutoff = datetime.now() - timedelta(days=30)
            cursor = conn.execute("DELETE FROM ai_usage WHERE timestamp < ?", (cutoff,))
            deleted = cursor.rowcount

            # Update performance statistics
            conn.execute("ANALYZE")

            return {
                "cleaned_records": deleted,
                "database_size_mb": Path(self.db_path).stat().st_size / (1024 * 1024),
            }


# Global instance for easy import
try:
    analytics = AIAnalytics()
except Exception as e:
    print(f"⚠️ Analytics initialization failed: {e}")
    ANALYTICS_ENABLED = False
    analytics = None
