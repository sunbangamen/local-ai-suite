#!/usr/bin/env python3
"""
Local AI CLI Tool - AI interface for local models
Supports automatic model selection and manual override
With integrated analytics and smart optimization
"""

import argparse
import json
import requests
import sys
import re
import os
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

# Configuration
API_URL = "http://localhost:8000/v1/chat/completions"
RAG_URL = "http://localhost:8002"
AVAILABLE_MODELS = {
    "chat": "local-7b",
    "code": "local-7b"
}
DEFAULT_MODEL = "local-7b"

# Analytics integration
try:
    from ai_analytics import analytics
    ANALYTICS_ENABLED = True
except ImportError:
    ANALYTICS_ENABLED = False
    analytics = None

# Session ID for tracking related queries
SESSION_ID = str(uuid.uuid4())[:8]

# Keywords that suggest coding-related queries
CODE_KEYWORDS = [
    "코드", "함수", "변수", "클래스", "메서드", "알고리즘", "디버깅", "버그",
    "리팩토링", "최적화", "프로그래밍", "개발", "스크립트", "API", "데이터베이스",
    "code", "function", "variable", "class", "method", "algorithm", "debug",
    "bug", "refactor", "optimize", "programming", "development", "script",
    "api", "database", "python", "javascript", "java", "cpp", "html", "css",
    "sql", "git", "docker", "framework", "library", "import", "export",
    "def ", "class ", "function ", "var ", "let ", "const ", "if ", "for ",
    "while ", "return", "print(", "console.log", "import ", "from ", "#include"
]

def detect_query_type(query: str) -> str:
    """
    Detect if the query is code-related or general chat
    Returns: 'code' or 'chat'
    """
    query_lower = query.lower()

    # Check for code keywords
    for keyword in CODE_KEYWORDS:
        if keyword in query_lower:
            return 'code'

    # Check for code patterns (basic heuristics)
    code_patterns = [
        r'def\s+\w+',  # Python function definition
        r'function\s+\w+',  # JavaScript function
        r'class\s+\w+',  # Class definition
        r'import\s+\w+',  # Import statements
        r'console\.log',  # console.log
        r'print\s*\(',  # print function
        r'if\s*\(',  # if statements
        r'for\s*\(',  # for loops
        r'{\s*.*\s*}',  # Code blocks
        r'#\s*TODO',  # TODO comments
    ]

    for pattern in code_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return 'code'

    return 'chat'

def call_rag_api(query: str, collection: str = "default", include_context: bool = True) -> Optional[str]:
    """
    Call RAG service for document-based queries
    """
    payload = {
        "query": query,
        "collection": collection,
        "limit": 5,
        "score_threshold": 0.7,
        "include_context": include_context
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"🔍 Searching documents in '{collection}' collection...")
        response = requests.post(f"{RAG_URL}/query", json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        data = response.json()
        answer = data.get('answer', 'No answer available')
        sources = data.get('sources', [])

        # Add source information
        if sources:
            source_info = "\n\n📚 Sources:"
            for i, source in enumerate(sources[:3], 1):  # Show top 3 sources
                source_info += f"\n{i}. {source['file_path']} (score: {source['score']:.2f})"
            answer += source_info

        return answer

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to RAG service.")
        print("💡 Make sure RAG system is running: make up-p2")
        return None
    except requests.exceptions.Timeout:
        print("⏱️ Error: RAG request timed out.")
        return None
    except Exception as e:
        print(f"❌ RAG Error: {e}")
        return None

def index_documents(collection: str = "default", directory: str = None) -> bool:
    """
    Index documents for RAG
    """
    payload = {
        "collection": collection,
        "chunk_size": 1000,
        "chunk_overlap": 200
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"📚 Indexing documents into '{collection}' collection...")
        if directory:
            print(f"📁 From directory: {directory}")

        response = requests.post(f"{RAG_URL}/index", json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"✅ {data['message']}")
        print(f"📄 Indexed {len(data['indexed_files'])} files, {data['total_chunks']} chunks")

        for file_info in data['indexed_files']:
            print(f"   - {file_info['file']} ({file_info['chunks']} chunks)")

        return True

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to RAG service.")
        print("💡 Make sure RAG system is running: make up-p2")
        return False
    except Exception as e:
        print(f"❌ Indexing Error: {e}")
        return False

def call_api(query: str, model_type: str = 'auto', max_tokens: int = 500) -> Optional[str]:
    """
    Call the API with the available model
    Enhanced with analytics and smart optimization
    """
    start_time = time.time()

    # Determine query type for temperature adjustment
    original_model_type = model_type
    detected_type = None
    if model_type == 'auto':
        detected_type = detect_query_type(query)
        model_type = detected_type

    # Get smart recommendation if analytics available
    if ANALYTICS_ENABLED and analytics:
        try:
            recommendation = analytics.get_model_recommendation(query, model_type)
            if recommendation.get('confidence', 0) > 0.7:
                suggested_model = recommendation['recommended_model']
                if suggested_model in AVAILABLE_MODELS.values():
                    print(f"💡 Smart recommendation: Using {suggested_model} (confidence: {recommendation['confidence']:.2f})")
        except Exception:
            pass  # Fallback to default logic

    # Use appropriate model based on query type
    model_name = AVAILABLE_MODELS.get(model_type, DEFAULT_MODEL)

    # Prepare request with appropriate context
    if model_type == 'code':
        system_prompt = "You are a helpful coding assistant. Provide clear, well-commented code solutions."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        temperature = 0.2
    else:
        system_prompt = "You are a helpful Korean AI assistant. You must respond ONLY in Korean language. Never use Chinese, English or any other language. 당신은 한국어 AI 어시스턴트입니다. 반드시 한국어로만 답변해주세요. 중국어나 영어를 절대 사용하지 마세요."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        temperature = 0.7

    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"🤖 Using {model_type} model ({model_name})...")
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        data = response.json()
        content = data['choices'][0]['message']['content']

        # Log analytics
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                tokens_used = data.get('usage', {}).get('total_tokens', 0)
                analytics.log_usage(
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    tokens_used=tokens_used,
                    success=True,
                    session_id=SESSION_ID
                )
            except Exception:
                pass  # Don't fail on analytics errors

        return content

    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to local AI server"
        print(f"❌ Error: {error_msg}")
        print("💡 Make sure the server is running: make up-p1")
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query, query_type=model_type, detected_type=detected_type or model_type,
                    model_used=model_name, response_time_ms=response_time_ms,
                    success=False, error_message=error_msg, session_id=SESSION_ID
                )
            except Exception:
                pass
        return None
    except requests.exceptions.Timeout:
        error_msg = "Request timed out"
        print(f"⏱️ Error: {error_msg}")
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query, query_type=model_type, detected_type=detected_type or model_type,
                    model_used=model_name, response_time_ms=response_time_ms,
                    success=False, error_message=error_msg, session_id=SESSION_ID
                )
            except Exception:
                pass
        return None
    except KeyError as e:
        error_msg = f"Unexpected response format: {e}"
        print(f"❌ Error: {error_msg}")
        print(f"Response: {response.text}")
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query, query_type=model_type, detected_type=detected_type or model_type,
                    model_used=model_name, response_time_ms=response_time_ms,
                    success=False, error_message=error_msg, session_id=SESSION_ID
                )
            except Exception:
                pass
        return None
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query, query_type=model_type, detected_type=detected_type or model_type,
                    model_used=model_name, response_time_ms=response_time_ms,
                    success=False, error_message=error_msg, session_id=SESSION_ID
                )
            except Exception:
                pass
        return None

def main():
    parser = argparse.ArgumentParser(
        description="AI CLI for local AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ai "안녕하세요!"                        # Auto-detect (chat model)
  ai "Python 함수 만들어줘"               # Auto-detect (code model)
  ai --code "일반 질문이지만 코딩모델로"      # Force code model
  ai --chat "코딩 질문이지만 채팅모델로"      # Force chat model
  ai --rag "파일 읽기 방법은?"              # Search documents with RAG
  ai --index                           # Index documents (default collection)
  ai --index myproject                 # Index documents into 'myproject' collection
  ai --rag --collection myproject "질문"   # Query specific collection
  ai --tokens 200 "짧은 답변 원함"         # Limit response length
        """
    )

    parser.add_argument("query", nargs='?', help="Your question or prompt")
    parser.add_argument("--code", action="store_true", help="Force use of code model")
    parser.add_argument("--chat", action="store_true", help="Force use of chat model")
    parser.add_argument("--rag", action="store_true", help="Use RAG (document-based) search")
    parser.add_argument("--index", metavar="COLLECTION", nargs='?', const="default", help="Index documents for RAG (default collection: 'default')")
    parser.add_argument("--collection", default="default", help="RAG collection name (default: 'default')")
    parser.add_argument("--tokens", type=int, default=500, help="Maximum tokens in response (default: 500)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive mode")
    parser.add_argument("--analytics", action="store_true", help="Show analytics dashboard")
    parser.add_argument("--optimize", action="store_true", help="Run database optimization")

    args = parser.parse_args()

    # Handle indexing command
    if args.index is not None:
        success = index_documents(args.index)
        sys.exit(0 if success else 1)

    # Handle analytics dashboard
    if args.analytics:
        if not ANALYTICS_ENABLED:
            print("❌ Analytics not available. ai_analytics.py not found.")
            sys.exit(1)
        show_analytics_dashboard()
        sys.exit(0)

    # Handle optimization command
    if args.optimize:
        if not ANALYTICS_ENABLED:
            print("❌ Analytics not available. ai_analytics.py not found.")
            sys.exit(1)
        run_optimization()
        sys.exit(0)

    # Determine model type
    model_type = 'auto'
    if args.code:
        model_type = 'code'
    elif args.chat:
        model_type = 'chat'

    # Interactive mode
    if args.interactive:
        print("🤖 Local AI Interactive Mode")
        print("Type 'exit' or 'quit' to exit, 'help' for commands")
        print("-" * 50)

        while True:
            try:
                query = input("\n💬 You: ").strip()
                if not query:
                    continue
                if query.lower() in ['exit', 'quit', 'q']:
                    print("👋 Goodbye!")
                    break
                if query.lower() == 'help':
                    print("Commands:")
                    print("  exit/quit - Exit interactive mode")
                    print("  :code <query> - Force code model")
                    print("  :chat <query> - Force chat model")
                    print("  :rag <query> - Search documents with RAG")
                    print("  :index [collection] - Index documents")
                    print("  :analytics - Show usage analytics")
                    print("  :optimize - Run database optimization")
                    continue

                # Parse inline commands
                if query.startswith(':code '):
                    query = query[6:]
                    model_type = 'code'
                    response = call_api(query, model_type, args.tokens)
                elif query.startswith(':chat '):
                    query = query[6:]
                    model_type = 'chat'
                    response = call_api(query, model_type, args.tokens)
                elif query.startswith(':rag '):
                    query = query[5:]
                    response = call_rag_api(query, args.collection)
                elif query.startswith(':index'):
                    parts = query.split(' ', 1)
                    collection = parts[1] if len(parts) > 1 else "default"
                    index_documents(collection)
                    continue
                elif query.startswith(':analytics'):
                    if ANALYTICS_ENABLED:
                        show_analytics_dashboard()
                    else:
                        print("❌ Analytics not available")
                    continue
                elif query.startswith(':optimize'):
                    if ANALYTICS_ENABLED:
                        run_optimization()
                    else:
                        print("❌ Analytics not available")
                    continue
                else:
                    model_type = 'auto'
                    response = call_api(query, model_type, args.tokens)

                if response:
                    print(f"\n🤖 AI: {response}")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
        return

    # Single query mode
    if not args.query:
        parser.print_help()
        sys.exit(1)

    # Handle RAG query
    if args.rag:
        response = call_rag_api(args.query, args.collection)
    else:
        response = call_api(args.query, model_type, args.tokens)

    if response:
        print(response)
    else:
        sys.exit(1)

def show_analytics_dashboard():
    """Show comprehensive analytics dashboard"""
    try:
        print("📊 AI Usage Analytics Dashboard")
        print("=" * 50)

        # Get analytics summary
        summary = analytics.get_analytics_summary(hours=24)

        print(f"\n📈 Usage Statistics (Last 24h)")
        print("-" * 30)
        for stat in summary['usage_stats']:
            print(f"  {stat['query_type'].upper()} ({stat['model_used']}):")
            print(f"    Queries: {stat['total_queries']}")
            print(f"    Avg Response: {stat['avg_response_time']:.0f}ms")
            print(f"    Success Rate: {stat['success_rate']:.1f}%")
            if stat['avg_tokens']:
                print(f"    Avg Tokens: {stat['avg_tokens']:.0f}")
            print()

        print(f"\n⏰ Peak Usage Times")
        print("-" * 30)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for peak in summary['peak_times']:
            day_name = days[peak['day_of_week']]
            print(f"  {day_name} {peak['hour_of_day']:02d}:00 - {peak['total_usage']} queries")

        print(f"\n🏆 Model Performance Ranking")
        print("-" * 30)
        for perf in summary['model_performance']:
            print(f"  {perf['model_name']} ({perf['query_type']})")
            print(f"    Speed: {perf['avg_response_time_ms']:.0f}ms")
            print(f"    Reliability: {perf['success_rate']:.1%}")
            print(f"    Usage: {perf['total_usage_count']} times")
            print()

        print(f"\n💡 Smart Recommendations")
        print("-" * 30)
        test_queries = [
            ("파이썬 함수 만들어줘", "code"),
            ("오늘 날씨가 어때?", "chat"),
        ]

        for query, qtype in test_queries:
            rec = analytics.get_model_recommendation(query, qtype)
            print(f"  Query type: {qtype}")
            print(f"  Recommended: {rec['recommended_model']}")
            print(f"  Confidence: {rec['confidence']:.1%}")
            print(f"  Reason: {rec['reason']}")
            print()

    except Exception as e:
        print(f"❌ Error showing analytics: {e}")

def run_optimization():
    """Run database optimization"""
    try:
        print("🔧 Running AI Analytics Optimization...")
        result = analytics.optimize_database()
        print(f"✅ Optimization complete!")
        print(f"  Cleaned records: {result['cleaned_records']}")
        print(f"  Database size: {result['database_size_mb']:.1f}MB")
    except Exception as e:
        print(f"❌ Error during optimization: {e}")

if __name__ == "__main__":
    main()