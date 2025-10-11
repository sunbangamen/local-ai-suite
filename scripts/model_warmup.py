#!/usr/bin/env python3
"""Model Warmup and Preoptimization System."""
import os
import requests
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ai_analytics import analytics

API_URL = "http://localhost:8000/v1/chat/completions"
RAG_URL = "http://localhost:8002"

CHAT_MODEL_NAME = os.getenv("API_GATEWAY_CHAT_MODEL", "chat-7b")
CODE_MODEL_NAME = os.getenv("API_GATEWAY_CODE_MODEL", "code-7b")
MODEL_NAME_BY_TYPE = {
    "chat": CHAT_MODEL_NAME,
    "code": CODE_MODEL_NAME,
}


class ModelWarmer:
    def __init__(self):
        self.warmup_queries = {
            "chat": ["안녕하세요!", "오늘 날씨가 어떤가요?", "간단한 질문입니다."],
            "code": ["def hello():", "파이썬 함수 예제", "코딩 도움이 필요해요"],
            "rag": ["문서 검색 테스트", "파일 처리 방법", "도움말을 찾습니다"],
        }

    def warmup_models(self, priority_models: List[str] = None):
        """Warmup models based on usage patterns or priority"""
        print("🔥 Starting model warmup...")

        if not priority_models:
            priority_models = self._get_priority_models()

        warmed_models = []
        for model_type in priority_models:
            if self._warmup_model(model_type):
                warmed_models.append(model_type)
                print(f"✅ {model_type} model warmed up")
            else:
                print(f"⚠️ Failed to warm up {model_type} model")

        return warmed_models

    def _get_priority_models(self) -> List[str]:
        """Get models to warm up based on usage patterns"""
        try:
            # Get current time context
            now = datetime.now()
            hour = now.hour

            # Get models likely to be used based on time patterns
            summary = analytics.get_analytics_summary(hours=168)  # Last week

            # Prioritize by usage patterns
            model_priority = {}
            for stat in summary["usage_stats"]:
                query_type = stat["query_type"]
                usage_count = stat["total_queries"]
                model_priority[query_type] = usage_count

            # Sort by usage and return top models
            sorted_models = sorted(
                model_priority.items(), key=lambda x: x[1], reverse=True
            )
            return [model[0] for model in sorted_models[:2]] or ["chat", "code"]

        except Exception:
            # Fallback to default priority
            if 9 <= hour <= 17:  # Work hours - prioritize code
                return ["code", "chat", "rag"]
            else:  # Off hours - prioritize chat
                return ["chat", "code", "rag"]

    def _warmup_model(self, model_type: str) -> bool:
        """Warmup a specific model type"""
        queries = self.warmup_queries.get(model_type, ["테스트"])

        for query in queries:
            try:
                if model_type == "rag":
                    # Warmup RAG system
                    response = requests.post(f"{RAG_URL}/prewarm", timeout=30)
                else:
                    # Warmup LLM
                    payload = {
                        "model": MODEL_NAME_BY_TYPE.get(model_type, CHAT_MODEL_NAME),
                        "messages": [{"role": "user", "content": query}],
                        "max_tokens": 10,
                        "temperature": 0.1,
                    }
                    response = requests.post(API_URL, json=payload, timeout=30)

                response.raise_for_status()
                time.sleep(1)  # Gentle warming
                return True

            except Exception as e:
                print(f"  ⚠️ Warmup failed for {model_type}: {e}")
                continue

        return False

    def get_optimization_recommendations(self) -> Dict:
        """Get performance optimization recommendations"""
        try:
            summary = analytics.get_analytics_summary(hours=24)
            recommendations = []

            # Analyze response times
            slow_threshold = 5000  # 5 seconds
            for stat in summary["usage_stats"]:
                avg_time = stat.get("avg_response_time", 0)
                if avg_time > slow_threshold:
                    recommendations.append(
                        {
                            "type": "performance",
                            "severity": "medium",
                            "message": f"{stat['query_type']} queries averaging {avg_time:.0f}ms - consider model optimization",
                            "action": f"Consider reducing context size or switching to faster model for {stat['query_type']}",
                        }
                    )

            # Analyze success rates
            for stat in summary["usage_stats"]:
                success_rate = stat.get("success_rate", 100)
                if success_rate < 95:
                    recommendations.append(
                        {
                            "type": "reliability",
                            "severity": "high",
                            "message": f"{stat['query_type']} success rate {success_rate:.1f}% - needs attention",
                            "action": f"Check error logs and model configuration for {stat['query_type']}",
                        }
                    )

            # Usage pattern recommendations
            peak_times = summary.get("peak_times", [])
            if peak_times:
                top_peak = peak_times[0]
                days = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                day_name = days[top_peak["day_of_week"]]
                recommendations.append(
                    {
                        "type": "scheduling",
                        "severity": "low",
                        "message": f"Peak usage: {day_name} {top_peak['hour_of_day']:02d}:00",
                        "action": f"Consider pre-warming models before {day_name} {top_peak['hour_of_day']:02d}:00",
                    }
                )

            return {
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "high_priority": len(
                    [r for r in recommendations if r["severity"] == "high"]
                ),
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"error": str(e), "recommendations": [], "total_count": 0}

    def auto_optimize(self) -> Dict:
        """Run automatic optimization based on patterns"""
        results = {
            "warmup_completed": False,
            "models_warmed": [],
            "recommendations": {},
            "optimization_time_ms": 0,
        }

        start_time = time.time()

        try:
            # Warmup high-priority models
            warmed_models = self.warmup_models()
            results["warmup_completed"] = True
            results["models_warmed"] = warmed_models

            # Get optimization recommendations
            results["recommendations"] = self.get_optimization_recommendations()

            # Database cleanup
            analytics.optimize_database()

            results["optimization_time_ms"] = int((time.time() - start_time) * 1000)

        except Exception as e:
            results["error"] = str(e)

        return results


def main():
    """CLI interface for model warming and optimization"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Warmup and Optimization Tool")
    parser.add_argument(
        "--warmup", action="store_true", help="Warmup models based on usage patterns"
    )
    parser.add_argument(
        "--recommendations",
        action="store_true",
        help="Show optimization recommendations",
    )
    parser.add_argument(
        "--auto-optimize", action="store_true", help="Run full automatic optimization"
    )
    parser.add_argument(
        "--models", nargs="+", help="Specific models to warmup (chat, code, rag)"
    )

    args = parser.parse_args()

    warmer = ModelWarmer()

    if args.warmup:
        print("🔥 Manual Model Warmup")
        models = args.models or None
        warmed = warmer.warmup_models(models)
        print(f"✅ Warmed up {len(warmed)} models: {', '.join(warmed)}")

    elif args.recommendations:
        print("💡 Optimization Recommendations")
        rec = warmer.get_optimization_recommendations()

        if rec.get("error"):
            print(f"❌ Error: {rec['error']}")
            return

        if not rec["recommendations"]:
            print("✅ No optimization needed - system running well!")
            return

        print(f"Found {rec['total_count']} recommendations:")
        for i, r in enumerate(rec["recommendations"], 1):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            icon = severity_icon.get(r["severity"], "🔵")
            print(f"  {i}. {icon} {r['message']}")
            print(f"     Action: {r['action']}")

    elif args.auto_optimize:
        print("🚀 Running Auto-Optimization...")
        results = warmer.auto_optimize()

        if results.get("error"):
            print(f"❌ Error: {results['error']}")
            return

        print(f"✅ Optimization complete in {results['optimization_time_ms']}ms")
        print(f"🔥 Warmed models: {', '.join(results['models_warmed'])}")

        rec_count = results["recommendations"].get("total_count", 0)
        high_priority = results["recommendations"].get("high_priority", 0)

        if rec_count > 0:
            print(
                f"💡 {rec_count} recommendations generated ({high_priority} high priority)"
            )
        else:
            print("✅ System performance optimal!")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
