"""
AI Analytics Database - Integrated Usage Tracking and Optimization
- AI CLI usage patterns and model selection tracking
- Performance analytics and smart recommendations
- Integration with RAG analytics for comprehensive insights
"""
import sqlite3
import json
import time
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import threading
from contextlib import contextmanager

class AIAnalytics:
    def __init__(self, db_path: str = None):
        # Use environment variable or fallback to writable location
        if db_path is None:
            db_path = os.getenv(
                'AI_ANALYTICS_DB',
                os.path.expanduser('~/.local/share/ai-suite/ai_analytics.db')
            )

        self.db_path = db_path
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # If external path is read-only, fall back to home directory
            fallback_path = os.path.expanduser('~/.local/share/ai-suite/ai_analytics.db')
            print(f"Warning: Cannot write to {db_path} ({e}). Using fallback: {fallback_path}")
            self.db_path = fallback_path
            Path(fallback_path).parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_schema()

    def _get_connection(self):
        """Thread-safe connection handling"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
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
        with self.transaction() as conn:
            # AI CLI usage tracking
            conn.execute("""
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
            """)

            # Model performance tracking
            conn.execute("""
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
            """)

            # Model recommendations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_pattern TEXT NOT NULL,
                    recommended_model TEXT NOT NULL,
                    confidence_score REAL,
                    reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

            # Usage patterns
            conn.execute("""
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
            """)

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_timestamp ON ai_usage(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_query_type ON ai_usage(query_type)",
                "CREATE INDEX IF NOT EXISTS idx_ai_usage_model ON ai_usage(model_used)",
                "CREATE INDEX IF NOT EXISTS idx_model_performance_model ON model_performance(model_name)",
                "CREATE INDEX IF NOT EXISTS idx_usage_patterns_time ON usage_patterns(hour_of_day, day_of_week)"
            ]
            for idx in indexes:
                conn.execute(idx)

    def log_usage(self, query: str, query_type: str, detected_type: str,
                  model_used: str, response_time_ms: int, tokens_used: int = 0,
                  success: bool = True, error_message: str = None, session_id: str = None):
        """Log AI CLI usage for analytics"""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]

        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO ai_usage
                (query_hash, query_text, query_type, detected_type, model_used,
                 response_time_ms, tokens_used, success, error_message, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (query_hash, query[:500], query_type, detected_type, model_used,
                  response_time_ms, tokens_used, success, error_message, session_id))

            # Update model performance statistics
            self._update_model_performance(conn, model_used, query_type, response_time_ms, success)

            # Update usage patterns
            now = datetime.now()
            self._update_usage_patterns(conn, now.hour, now.weekday(), query_type, response_time_ms)

    def _update_model_performance(self, conn, model: str, query_type: str,
                                  response_time_ms: int, success: bool):
        """Update model performance statistics"""
        # Get current stats
        cursor = conn.execute("""
            SELECT avg_response_time_ms, success_rate, total_usage_count
            FROM model_performance
            WHERE model_name = ? AND query_type = ?
        """, (model, query_type))

        row = cursor.fetchone()
        if row:
            # Update existing stats
            old_avg_time = row['avg_response_time_ms'] or 0
            old_success_rate = row['success_rate'] or 0
            old_count = row['total_usage_count'] or 0

            new_count = old_count + 1
            new_avg_time = ((old_avg_time * old_count) + response_time_ms) / new_count
            new_success_rate = ((old_success_rate * old_count) + (1 if success else 0)) / new_count

            conn.execute("""
                UPDATE model_performance
                SET avg_response_time_ms = ?, success_rate = ?,
                    total_usage_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE model_name = ? AND query_type = ?
            """, (new_avg_time, new_success_rate, new_count, model, query_type))
        else:
            # Insert new stats
            conn.execute("""
                INSERT INTO model_performance
                (model_name, query_type, avg_response_time_ms, success_rate, total_usage_count)
                VALUES (?, ?, ?, ?, 1)
            """, (model, query_type, response_time_ms, 1.0 if success else 0.0))

    def _update_usage_patterns(self, conn, hour: int, day_of_week: int,
                              query_type: str, response_time_ms: int):
        """Update usage patterns"""
        cursor = conn.execute("""
            SELECT usage_count, avg_response_time_ms
            FROM usage_patterns
            WHERE hour_of_day = ? AND day_of_week = ? AND query_type = ?
        """, (hour, day_of_week, query_type))

        row = cursor.fetchone()
        if row:
            old_count = row['usage_count']
            old_avg = row['avg_response_time_ms'] or 0
            new_count = old_count + 1
            new_avg = ((old_avg * old_count) + response_time_ms) / new_count

            conn.execute("""
                UPDATE usage_patterns
                SET usage_count = ?, avg_response_time_ms = ?, last_updated = CURRENT_TIMESTAMP
                WHERE hour_of_day = ? AND day_of_week = ? AND query_type = ?
            """, (new_count, new_avg, hour, day_of_week, query_type))
        else:
            conn.execute("""
                INSERT INTO usage_patterns
                (hour_of_day, day_of_week, query_type, usage_count, avg_response_time_ms)
                VALUES (?, ?, ?, 1, ?)
            """, (hour, day_of_week, query_type, response_time_ms))

    def get_model_recommendation(self, query: str, query_type: str = None) -> Dict[str, Any]:
        """Get smart model recommendation based on usage patterns"""
        with self.transaction() as conn:
            # Get current time context
            now = datetime.now()
            hour = now.hour
            day_of_week = now.weekday()

            # Get best performing model for this query type and time
            cursor = conn.execute("""
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
            """, (hour, day_of_week, query_type or 'chat'))

            result = cursor.fetchone()
            if result:
                return {
                    'recommended_model': result['model_name'],
                    'avg_response_time': result['avg_response_time_ms'],
                    'success_rate': result['success_rate'],
                    'confidence': min(result['success_rate'], 1.0),
                    'reason': f"Best performance for {query_type} queries at this time"
                }

            # Fallback to overall best model
            return {
                'recommended_model': 'local-7b',
                'confidence': 0.5,
                'reason': 'Default model (insufficient data for optimization)'
            }

    def get_analytics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive analytics summary"""
        cutoff = datetime.now() - timedelta(hours=hours)

        with self.transaction() as conn:
            # Usage statistics
            cursor = conn.execute("""
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
            """, (cutoff,))

            usage_stats = [dict(row) for row in cursor.fetchall()]

            # Peak usage times
            cursor = conn.execute("""
                SELECT hour_of_day, day_of_week, SUM(usage_count) as total_usage
                FROM usage_patterns
                GROUP BY hour_of_day, day_of_week
                ORDER BY total_usage DESC
                LIMIT 5
            """)

            peak_times = [dict(row) for row in cursor.fetchall()]

            # Model performance comparison
            cursor = conn.execute("""
                SELECT model_name, query_type, avg_response_time_ms,
                       success_rate, total_usage_count
                FROM model_performance
                WHERE total_usage_count >= 3
                ORDER BY success_rate DESC, avg_response_time_ms ASC
            """)

            model_performance = [dict(row) for row in cursor.fetchall()]

            return {
                'usage_stats': usage_stats,
                'peak_times': peak_times,
                'model_performance': model_performance,
                'analysis_period_hours': hours,
                'generated_at': datetime.now().isoformat()
            }

    def optimize_database(self):
        """Run database optimization"""
        with self.transaction() as conn:
            # Clean old data (keep last 30 days)
            cutoff = datetime.now() - timedelta(days=30)
            cursor = conn.execute("DELETE FROM ai_usage WHERE timestamp < ?", (cutoff,))
            deleted = cursor.rowcount

            # Update performance statistics
            conn.execute("ANALYZE")

            return {
                'cleaned_records': deleted,
                'database_size_mb': Path(self.db_path).stat().st_size / (1024*1024)
            }

# Global instance for easy import
analytics = AIAnalytics()