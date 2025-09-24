#!/usr/bin/env python3
"""
Model Performance Optimizer
- Smart model selection based on usage patterns
- Memory management and model prewarming
- Performance monitoring and caching
"""
import os
import json
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class ModelOptimizer:
    def __init__(self, db_path: str = "/mnt/e/ai-data/sqlite/model_usage.db"):
        self.db_path = db_path
        self.api_url = "http://localhost:8000/v1/chat/completions"
        self.models = {
            "chat": "qwen2.5-14b-instruct",
            "code": "qwen2.5-coder-14b-instruct"
        }

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize model usage tracking database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query_text TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                detected_type TEXT NOT NULL,  -- 'chat' or 'code'
                selected_model TEXT NOT NULL,
                manual_override BOOLEAN DEFAULT 0,
                response_time_ms INTEGER,
                tokens_used INTEGER,
                user_feedback INTEGER,  -- -1: wrong model, 0: ok, 1: perfect
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                avg_response_time_ms REAL,
                total_requests INTEGER DEFAULT 0,
                success_rate REAL,
                last_used DATETIME,
                prewarmed BOOLEAN DEFAULT 0,
                date DATE DEFAULT CURRENT_DATE
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON model_usage(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_model ON model_usage(selected_model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_model ON model_performance(model_name)")

        conn.commit()
        conn.close()

    def log_model_usage(self,
                       query: str,
                       detected_type: str,
                       selected_model: str,
                       manual_override: bool = False,
                       response_time_ms: int = 0,
                       tokens_used: int = 0) -> int:
        """Log model usage for pattern learning"""
        query_hash = hash(query.strip().lower()) % (2**31)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            INSERT INTO model_usage
            (query_text, query_hash, detected_type, selected_model,
             manual_override, response_time_ms, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (query, str(query_hash), detected_type, selected_model,
              manual_override, response_time_ms, tokens_used))

        usage_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return usage_id

    def get_smart_model_recommendation(self, query: str) -> Tuple[str, float]:
        """
        Get smart model recommendation based on usage patterns
        Returns: (model_type, confidence_score)
        """
        query_lower = query.lower()

        # Basic keyword detection (fallback)
        basic_type = self._detect_basic_type(query)

        # Learn from past similar queries
        conn = sqlite3.connect(self.db_path)

        # Find similar queries with good user feedback
        cursor = conn.execute("""
            SELECT detected_type, selected_model, user_feedback, COUNT(*) as count
            FROM model_usage
            WHERE LENGTH(query_text) BETWEEN ? AND ?
            AND user_feedback >= 0
            AND timestamp > datetime('now', '-30 days')
            GROUP BY detected_type, selected_model
            ORDER BY
                CASE WHEN user_feedback = 1 THEN 3
                     WHEN user_feedback = 0 THEN 1
                     ELSE 0 END * count DESC
        """, (len(query) - 20, len(query) + 20))

        patterns = cursor.fetchall()
        conn.close()

        if patterns:
            # Use historical patterns with good feedback
            best_type = patterns[0][0]  # detected_type from best pattern
            confidence = min(0.9, 0.6 + (patterns[0][3] * 0.1))  # count-based confidence
            return best_type, confidence
        else:
            # Fall back to basic detection
            return basic_type, 0.5

    def _detect_basic_type(self, query: str) -> str:
        """Basic keyword-based detection (imported from ai.py logic)"""
        code_keywords = [
            "코드", "함수", "변수", "클래스", "메서드", "알고리즘", "디버깅", "버그",
            "code", "function", "variable", "class", "method", "algorithm", "debug",
            "python", "javascript", "java", "cpp", "html", "css", "sql", "git",
            "def ", "function ", "import ", "print(", "console.log"
        ]

        query_lower = query.lower()
        for keyword in code_keywords:
            if keyword in query_lower:
                return 'code'
        return 'chat'

    def prewarm_models(self) -> Dict[str, bool]:
        """Prewarm frequently used models"""
        results = {}

        # Check which models are used frequently
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT selected_model, COUNT(*) as usage_count
            FROM model_usage
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY selected_model
            ORDER BY usage_count DESC
        """)

        model_usage = dict(cursor.fetchall())
        conn.close()

        # Prewarm models with significant usage
        for model_type, model_name in self.models.items():
            if model_usage.get(model_name, 0) > 5:  # Used more than 5 times this week
                success = self._prewarm_model(model_name)
                results[model_name] = success

                # Update performance tracking
                self._update_model_performance(model_name, prewarmed=success)

        return results

    def _prewarm_model(self, model_name: str) -> bool:
        """Send a small warming request to the model"""
        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "temperature": 0.1
            }

            response = requests.post(
                self.api_url,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )

            return response.status_code == 200

        except Exception:
            return False

    def _update_model_performance(self, model_name: str, prewarmed: bool = False,
                                response_time: Optional[float] = None):
        """Update model performance metrics"""
        conn = sqlite3.connect(self.db_path)

        # Get current stats
        cursor = conn.execute("""
            SELECT avg_response_time_ms, total_requests
            FROM model_performance
            WHERE model_name = ? AND date = CURRENT_DATE
        """, (model_name,))

        row = cursor.fetchone()

        if row:
            # Update existing record
            current_avg, current_count = row
            if response_time:
                new_avg = ((current_avg * current_count) + response_time) / (current_count + 1)
                new_count = current_count + 1
            else:
                new_avg, new_count = current_avg, current_count

            conn.execute("""
                UPDATE model_performance
                SET avg_response_time_ms = ?, total_requests = ?,
                    last_used = CURRENT_TIMESTAMP, prewarmed = ?
                WHERE model_name = ? AND date = CURRENT_DATE
            """, (new_avg, new_count, prewarmed, model_name))
        else:
            # Create new record
            conn.execute("""
                INSERT INTO model_performance
                (model_name, avg_response_time_ms, total_requests, prewarmed)
                VALUES (?, ?, ?, ?)
            """, (model_name, response_time or 0, 1 if response_time else 0, prewarmed))

        conn.commit()
        conn.close()

    def get_performance_stats(self) -> Dict:
        """Get model performance statistics"""
        conn = sqlite3.connect(self.db_path)

        # Usage stats
        cursor = conn.execute("""
            SELECT
                selected_model,
                COUNT(*) as total_uses,
                AVG(response_time_ms) as avg_response_time,
                COUNT(CASE WHEN manual_override = 1 THEN 1 END) as manual_overrides,
                AVG(CASE WHEN user_feedback IS NOT NULL THEN user_feedback END) as avg_feedback
            FROM model_usage
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY selected_model
        """)

        usage_stats = [dict(zip([col[0] for col in cursor.description], row))
                      for row in cursor.fetchall()]

        # Recent performance
        cursor = conn.execute("""
            SELECT model_name, avg_response_time_ms, total_requests, prewarmed, last_used
            FROM model_performance
            WHERE date >= date('now', '-7 days')
            ORDER BY total_requests DESC
        """)

        performance_stats = [dict(zip([col[0] for col in cursor.description], row))
                           for row in cursor.fetchall()]

        # Model switching patterns
        cursor = conn.execute("""
            SELECT
                detected_type,
                selected_model,
                COUNT(*) as count,
                AVG(CASE WHEN user_feedback >= 0 THEN 1.0 ELSE 0.0 END) as accuracy
            FROM model_usage
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY detected_type, selected_model
            ORDER BY count DESC
        """)

        switching_patterns = [dict(zip([col[0] for col in cursor.description], row))
                            for row in cursor.fetchall()]

        conn.close()

        return {
            "usage_stats": usage_stats,
            "performance_stats": performance_stats,
            "switching_patterns": switching_patterns,
            "total_queries_week": sum(stat['total_uses'] for stat in usage_stats)
        }

    def provide_feedback(self, usage_id: int, feedback: int):
        """Provide feedback on model selection quality"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE model_usage
            SET user_feedback = ?
            WHERE id = ?
        """, (feedback, usage_id))
        conn.commit()
        conn.close()

# Global optimizer instance
optimizer = ModelOptimizer()

def main():
    """CLI interface for model optimizer"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python model_optimizer.py [prewarm|stats|feedback]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "prewarm":
        print("🔥 Prewarming models...")
        results = optimizer.prewarm_models()
        for model, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {model}")

    elif command == "stats":
        stats = optimizer.get_performance_stats()
        print(json.dumps(stats, indent=2, default=str))

    elif command == "feedback":
        if len(sys.argv) < 4:
            print("Usage: python model_optimizer.py feedback <usage_id> <score>")
            print("Score: -1 (wrong model), 0 (ok), 1 (perfect)")
            sys.exit(1)
        usage_id = int(sys.argv[2])
        feedback = int(sys.argv[3])
        optimizer.provide_feedback(usage_id, feedback)
        print(f"✅ Feedback recorded for usage ID {usage_id}")

    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()