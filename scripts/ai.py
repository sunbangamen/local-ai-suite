#!/usr/bin/env python3
"""
Local AI CLI Tool - AI interface for local models
Supports automatic model selection and manual override
"""

import argparse
import json
import requests
import sys
import re
from typing import Optional

# Configuration
API_URL = "http://localhost:8000/v1/chat/completions"
AVAILABLE_MODELS = ["qwen2.5-14b-instruct", "gpt-3.5-turbo"]
DEFAULT_MODEL = "qwen2.5-14b-instruct"

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

def call_api(query: str, model_type: str = 'auto', max_tokens: int = 500) -> Optional[str]:
    """
    Call the API with the available model
    """
    # Determine query type for temperature adjustment
    if model_type == 'auto':
        model_type = detect_query_type(query)

    # Use the default model (both models point to the same local model for now)
    model_name = DEFAULT_MODEL

    # Prepare request with appropriate context
    if model_type == 'code':
        system_prompt = "You are a helpful coding assistant. Provide clear, well-commented code solutions."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        temperature = 0.2
    else:
        messages = [
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
        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        return data['choices'][0]['message']['content']

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to local AI server.")
        print("💡 Make sure the server is running: make up-p1")
        return None
    except requests.exceptions.Timeout:
        print("⏱️ Error: Request timed out.")
        return None
    except KeyError as e:
        print(f"❌ Error: Unexpected response format: {e}")
        print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="AI CLI for local AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ai "안녕하세요!"                     # Auto-detect (chat model)
  ai "Python 함수 만들어줘"            # Auto-detect (code model)
  ai --code "일반 질문이지만 코딩모델로"   # Force code model
  ai --chat "코딩 질문이지만 채팅모델로"   # Force chat model
  ai --tokens 200 "짧은 답변 원함"      # Limit response length
        """
    )

    parser.add_argument("query", nargs='?', help="Your question or prompt")
    parser.add_argument("--code", action="store_true", help="Force use of code model")
    parser.add_argument("--chat", action="store_true", help="Force use of chat model")
    parser.add_argument("--tokens", type=int, default=500, help="Maximum tokens in response (default: 500)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive mode")

    args = parser.parse_args()

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
                    continue

                # Parse inline commands
                if query.startswith(':code '):
                    query = query[6:]
                    model_type = 'code'
                elif query.startswith(':chat '):
                    query = query[6:]
                    model_type = 'chat'
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

    response = call_api(args.query, model_type, args.tokens)
    if response:
        print(response)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()