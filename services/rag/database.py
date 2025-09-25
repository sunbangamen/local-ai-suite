"""
RAG Database Layer with SQLite
- Production-ready with performance monitoring
- Search analytics and caching
- Automatic optimization
"""
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import hashlib
import threading
from contextlib import contextmanager

class RAGDatabase:
    def __init__(self, db_path: str = "/mnt/e/ai-data/sqlite/rag_analytics.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
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
        """Initialize database schema"""
        with self.transaction() as conn:
            # Search logs for analytics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    collection TEXT NOT NULL,
                    query TEXT NOT NULL,
                    query_hash TEXT NOT NULL,
                    results_count INTEGER,
                    response_time_ms INTEGER,
                    llm_tokens_used INTEGER,
                    embedding_time_ms INTEGER,
                    vector_search_time_ms INTEGER,
                    llm_response_time_ms INTEGER,
                    user_feedback INTEGER,  -- -1: bad, 0: neutral, 1: good
                    context_length INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Document metadata for better management
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    chunk_count INTEGER,
                    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME,
                    access_count INTEGER DEFAULT 0,
                    embedding_model TEXT,
                    checksum TEXT
                )
            """)

            # Query cache for performance
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    collection TEXT NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    context_data TEXT,  -- JSON
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    accessed_count INTEGER DEFAULT 0,
                    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
            """)

            # Performance metrics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT NOT NULL,  -- 'search', 'embed', 'llm'
                    collection TEXT,
                    avg_response_time_ms REAL,
                    p95_response_time_ms REAL,
                    success_rate REAL,
                    error_count INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    date DATE DEFAULT CURRENT_DATE,
                    hour INTEGER DEFAULT (strftime('%H', 'now')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_timestamp ON search_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_query_hash ON search_logs(query_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_collection ON search_logs(collection)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_document_metadata_doc_id ON document_metadata(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_hash ON query_cache(query_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_date_hour ON performance_metrics(date, hour)")

    def _query_hash(self, query: str, collection: str) -> str:
        """Generate hash for query + collection"""
        content = f"{collection}::{query}".strip().lower()
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def log_search(self,
                   collection: str,
                   query: str,
                   results_count: int,
                   response_time_ms: int,
                   llm_tokens_used: int = 0,
                   embedding_time_ms: int = 0,
                   vector_search_time_ms: int = 0,
                   llm_response_time_ms: int = 0,
                   context_length: int = 0) -> int:
        """Log search query for analytics"""
        query_hash = self._query_hash(query, collection)

        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO search_logs
                (collection, query, query_hash, results_count, response_time_ms,
                 llm_tokens_used, embedding_time_ms, vector_search_time_ms,
                 llm_response_time_ms, context_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (collection, query, query_hash, results_count, response_time_ms,
                  llm_tokens_used, embedding_time_ms, vector_search_time_ms,
                  llm_response_time_ms, context_length))

            return cursor.lastrowid

    def get_cached_query(self, query: str, collection: str) -> Optional[Dict[str, Any]]:
        """Get cached query result if exists and not expired"""
        query_hash = self._query_hash(query, collection)

        with self.transaction() as conn:
            cursor = conn.execute("""
                SELECT response, context_data, created_at
                FROM query_cache
                WHERE query_hash = ? AND collection = ?
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (query_hash, collection))

            row = cursor.fetchone()
            if row:
                # Update access stats
                conn.execute("""
                    UPDATE query_cache
                    SET accessed_count = accessed_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE query_hash = ? AND collection = ?
                """, (query_hash, collection))

                return {
                    'response': row['response'],
                    'context_data': json.loads(row['context_data'] or '[]'),
                    'cached_at': row['created_at']
                }
        return None

    def cache_query(self,
                    query: str,
                    collection: str,
                    response: str,
                    context_data: List[Dict],
                    ttl_hours: int = 24):
        """Cache query result"""
        query_hash = self._query_hash(query, collection)
        expires_at = datetime.now() + timedelta(hours=ttl_hours)

        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO query_cache
                (query_hash, collection, query, response, context_data, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (query_hash, collection, query, response,
                  json.dumps(context_data), expires_at))

    def update_document_metadata(self,
                               doc_id: str,
                               filename: str,
                               file_size: int,
                               chunk_count: int,
                               embedding_model: str,
                               checksum: str):
        """Update document metadata"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO document_metadata
                (doc_id, filename, file_size, chunk_count, embedding_model, checksum)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, filename, file_size, chunk_count, embedding_model, checksum))

    def track_document_access(self, doc_id: str):
        """Track document access for analytics"""
        with self.transaction() as conn:
            conn.execute("""
                UPDATE document_metadata
                SET access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE doc_id = ?
            """, (doc_id,))

    def get_search_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get search analytics for the last N hours"""
        since = datetime.now() - timedelta(hours=hours)

        with self.transaction() as conn:
            # Basic stats
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_searches,
                    AVG(response_time_ms) as avg_response_time,
                    AVG(results_count) as avg_results_count,
                    SUM(llm_tokens_used) as total_tokens
                FROM search_logs
                WHERE timestamp > ?
            """, (since,))
            stats = dict(cursor.fetchone())

            # Top queries
            cursor = conn.execute("""
                SELECT query, COUNT(*) as count
                FROM search_logs
                WHERE timestamp > ?
                GROUP BY query_hash
                ORDER BY count DESC
                LIMIT 10
            """, (since,))
            stats['top_queries'] = [dict(row) for row in cursor.fetchall()]

            # Collection usage
            cursor = conn.execute("""
                SELECT collection, COUNT(*) as count
                FROM search_logs
                WHERE timestamp > ?
                GROUP BY collection
                ORDER BY count DESC
            """, (since,))
            stats['collection_usage'] = [dict(row) for row in cursor.fetchall()]

            return stats

    def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        with self.transaction() as conn:
            cursor = conn.execute("""
                DELETE FROM query_cache
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            return cursor.rowcount

    def optimize_database(self):
        """Run database maintenance tasks"""
        with self.transaction() as conn:
            # Clean up old logs (keep 30 days)
            cutoff = datetime.now() - timedelta(days=30)
            conn.execute("DELETE FROM search_logs WHERE timestamp < ?", (cutoff,))

            # Clean up expired cache
            deleted_cache = self.cleanup_expired_cache()

            # Vacuum database
            conn.execute("VACUUM")

            return {
                'cleaned_cache_entries': deleted_cache,
                'database_optimized': True
            }

# Global instance
db = RAGDatabase()