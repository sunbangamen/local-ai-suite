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
MCP_URL = "http://localhost:8020"
AVAILABLE_MODELS = {"chat": "chat-7b", "code": "code-7b"}
DEFAULT_MODEL = "chat-7b"

# Analytics integration
try:
    from ai_analytics import analytics

    ANALYTICS_ENABLED = True
except ImportError:
    ANALYTICS_ENABLED = False
    analytics = None

# Memory system integration
try:
    from memory_system import get_memory_system, set_memory_system, MemorySystem

    MEMORY_ENABLED = True
except ImportError:
    MEMORY_ENABLED = False
    print("⚠️ Memory system not available. Install memory_system.py for conversation memory.")

# Memory API integration
MEMORY_API_URL = "http://localhost:8005/v1/memory"

# Session ID for tracking related queries
SESSION_ID = str(uuid.uuid4())[:8]

# Keywords that suggest coding-related queries
CODE_KEYWORDS = [
    "코드",
    "함수",
    "변수",
    "클래스",
    "메서드",
    "알고리즘",
    "디버깅",
    "버그",
    "리팩토링",
    "최적화",
    "프로그래밍",
    "개발",
    "스크립트",
    "API",
    "데이터베이스",
    "code",
    "function",
    "variable",
    "class",
    "method",
    "algorithm",
    "debug",
    "bug",
    "refactor",
    "optimize",
    "programming",
    "development",
    "script",
    "api",
    "database",
    "python",
    "javascript",
    "java",
    "cpp",
    "html",
    "css",
    "sql",
    "git",
    "docker",
    "framework",
    "library",
    "import",
    "export",
    "def ",
    "class ",
    "function ",
    "var ",
    "let ",
    "const ",
    "if ",
    "for ",
    "while ",
    "return",
    "print(",
    "console.log",
    "import ",
    "from ",
    "#include",
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
            return "code"

    # Check for code patterns (basic heuristics)
    code_patterns = [
        r"def\s+\w+",  # Python function definition
        r"function\s+\w+",  # JavaScript function
        r"class\s+\w+",  # Class definition
        r"import\s+\w+",  # Import statements
        r"console\.log",  # console.log
        r"print\s*\(",  # print function
        r"if\s*\(",  # if statements
        r"for\s*\(",  # for loops
        r"{\s*.*\s*}",  # Code blocks
        r"#\s*TODO",  # TODO comments
    ]

    for pattern in code_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return "code"

    return "chat"


def call_mcp_tool(tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Call MCP server tool with current working directory support (UTF-8 enhanced)
    """
    headers = {"Content-Type": "application/json; charset=utf-8"}

    # Add current working directory to kwargs for path-based tools
    current_dir = os.getcwd()
    if "working_dir" not in kwargs and tool_name in [
        "read_file",
        "write_file",
        "list_files",
        "git_status",
        "git_diff",
        "git_add",
        "git_commit",
    ]:
        kwargs["working_dir"] = current_dir

    try:
        print(f"🔧 Calling MCP tool: {tool_name} (working_dir: {current_dir})...")

        # JSON 데이터를 UTF-8로 명시적 인코딩
        json_data = json.dumps(kwargs, ensure_ascii=False).encode("utf-8")

        response = requests.post(
            f"{MCP_URL}/tools/{tool_name}/call",
            data=json_data,
            headers=headers,
            timeout=60,
        )

        # Handle approval workflow (Issue #26)
        if response.status_code == 403:
            try:
                error_data = response.json()
                if error_data.get("approval_required"):
                    request_id = error_data.get("request_id")
                    return handle_approval_workflow(request_id, tool_name, kwargs)
            except Exception as e:
                print(f"⚠️ Error handling approval response: {e}")

        response.raise_for_status()

        data = response.json()
        return data

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to MCP server.")
        print("💡 Make sure MCP server is running: make up-p3")
        return None
    except requests.exceptions.Timeout:
        print("⏱️ Error: MCP request timed out.")
        return None
    except Exception as e:
        print(f"❌ MCP Error: {e}")
        return None


def handle_approval_workflow(request_id: str, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handle approval workflow for HIGH/CRITICAL tools (Issue #26, Phase 1)

    Shows progress bar while waiting for admin approval, then re-executes the tool
    """
    try:
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
        from rich.console import Console as RichConsole

        console = RichConsole()
    except ImportError:
        # Fallback if Rich is not installed
        return wait_for_approval_simple(request_id, tool_name, args)

    approval_timeout = int(os.getenv("APPROVAL_TIMEOUT", "300"))  # 5 minutes default
    polling_interval = int(os.getenv("APPROVAL_POLLING_INTERVAL", "1"))  # 1 second default

    console.print(
        f"⏳ [yellow]Approval Required[/yellow]\n"
        f"   Tool: [cyan]{tool_name}[/cyan]\n"
        f"   Request ID: [magenta]{request_id[:8]}[/magenta]\n"
        f"   Timeout: [red]{approval_timeout}s[/red]"
    )

    elapsed = 0
    with Progress(
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Waiting for approval...", total=approval_timeout)

        while elapsed < approval_timeout:
            # Poll approval status
            try:
                status_response = requests.get(
                    f"{MCP_URL}/api/approvals/{request_id}/status",
                    timeout=5,
                )
                status_data = status_response.json()
                status = status_data.get("status", "pending")

                if status == "approved":
                    console.print("✅ [green]Approval Granted![/green]")
                    # Re-execute the tool
                    return call_mcp_tool(tool_name, **args)

                elif status in ["rejected", "expired", "timeout"]:
                    console.print(f"❌ [red]Approval {status}[/red]")
                    if status_data.get("reason"):
                        console.print(f"   Reason: {status_data['reason']}")
                    return None

            except Exception as e:
                console.print(f"⚠️ Error polling approval status: {e}")

            # Update progress
            progress.update(task, advance=polling_interval)
            elapsed += polling_interval
            time.sleep(polling_interval)

        # Timeout
        console.print("❌ [red]Approval Timeout[/red]")
        return None


def wait_for_approval_simple(request_id: str, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Simple fallback approval handler (no Rich library)
    """
    approval_timeout = int(os.getenv("APPROVAL_TIMEOUT", "300"))
    polling_interval = int(os.getenv("APPROVAL_POLLING_INTERVAL", "1"))

    print(f"\n⏳ Approval Required for: {tool_name}")
    print(f"   Request ID: {request_id[:8]}...")
    print(f"   Timeout: {approval_timeout}s\n")

    elapsed = 0
    while elapsed < approval_timeout:
        try:
            status_response = requests.get(
                f"{MCP_URL}/api/approvals/{request_id}/status",
                timeout=5,
            )
            status_data = status_response.json()
            status = status_data.get("status", "pending")

            if status == "approved":
                print("✅ Approval Granted!")
                return call_mcp_tool(tool_name, **args)

            elif status in ["rejected", "expired", "timeout"]:
                print(f"❌ Approval {status}")
                return None

            # Show progress
            remaining = approval_timeout - elapsed
            print(f"   [{elapsed}s/{approval_timeout}s] Waiting for approval...", end="\r")

        except Exception as e:
            print(f"⚠️ Error: {e}")

        elapsed += polling_interval
        time.sleep(polling_interval)

    print("❌ Approval Timeout")
    return None


def analyze_query_for_mcp_tools(query: str) -> List[Dict[str, Any]]:
    """
    Analyze user query to determine if MCP tools should be used
    Returns list of suggested tools with arguments
    """
    suggestions = []
    query_lower = query.lower()

    # File operations
    if any(
        keyword in query_lower for keyword in ["파일", "읽어", "read file", "파일 내용", "텍스트"]
    ):
        if "읽" in query_lower or "read" in query_lower:
            suggestions.append(
                {
                    "tool": "read_file",
                    "reason": "File reading operation detected",
                    "confidence": 0.8,
                }
            )

    if any(keyword in query_lower for keyword in ["파일 생성", "파일 쓰기", "write file", "저장"]):
        suggestions.append(
            {
                "tool": "write_file",
                "reason": "File writing operation detected",
                "confidence": 0.8,
            }
        )

    # Web operations
    if any(
        keyword in query_lower
        for keyword in ["웹사이트", "스크린샷", "screenshot", "website", "url"]
    ):
        suggestions.append(
            {
                "tool": "web_screenshot",
                "reason": "Web screenshot request detected",
                "confidence": 0.9,
            }
        )

    if any(keyword in query_lower for keyword in ["크롤링", "scrape", "웹 데이터", "web data"]):
        suggestions.append(
            {
                "tool": "web_scrape",
                "reason": "Web scraping request detected",
                "confidence": 0.9,
            }
        )

    # Code execution
    if any(
        keyword in query_lower for keyword in ["파이썬 실행", "python run", "코드 실행", "execute"]
    ):
        suggestions.append(
            {
                "tool": "execute_python",
                "reason": "Python code execution detected",
                "confidence": 0.8,
            }
        )

    if any(keyword in query_lower for keyword in ["명령어", "command", "bash", "터미널"]):
        suggestions.append(
            {
                "tool": "execute_bash",
                "reason": "Bash command execution detected",
                "confidence": 0.8,
            }
        )

    # Git operations
    if any(keyword in query_lower for keyword in ["git", "깃", "저장소", "repository"]):
        suggestions.append(
            {
                "tool": "git_status",
                "reason": "Git repository operation detected",
                "confidence": 0.7,
            }
        )

    # RAG search
    if any(keyword in query_lower for keyword in ["검색", "search", "문서", "document", "찾기"]):
        suggestions.append(
            {
                "tool": "rag_search",
                "reason": "Document search request detected",
                "confidence": 0.8,
            }
        )

    # Notion operations
    if any(keyword in query_lower for keyword in ["notion", "노션", "노트"]):
        suggestions.append(
            {
                "tool": "notion_search",
                "reason": "Notion operation detected",
                "confidence": 0.7,
            }
        )

    return suggestions


def auto_execute_mcp_tools(query: str, max_tools: int = 2) -> str:
    """
    Automatically execute relevant MCP tools based on query analysis
    Returns enhanced response with tool results
    """
    suggestions = analyze_query_for_mcp_tools(query)

    # Filter high-confidence suggestions
    high_conf_suggestions = [s for s in suggestions if s["confidence"] >= 0.8]

    if not high_conf_suggestions:
        return ""

    # Sort by confidence and limit
    high_conf_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    selected_tools = high_conf_suggestions[:max_tools]

    tool_results = []
    for suggestion in selected_tools:
        tool_name = suggestion["tool"]
        print(
            f"🤖 Auto-executing MCP tool: {tool_name} (confidence: {suggestion['confidence']:.1%})"
        )

        try:
            # Extract parameters from query based on tool type
            args = extract_tool_args_from_query(query, tool_name)
            result = call_mcp_tool(tool_name, **args)

            if result and result.get("success"):
                tool_results.append(
                    {
                        "tool": tool_name,
                        "result": result.get("result", ""),
                        "success": True,
                    }
                )
            else:
                print(f"⚠️ MCP tool {tool_name} failed or returned no results")

        except Exception as e:
            print(f"❌ Error executing MCP tool {tool_name}: {e}")

    # Format results for inclusion in AI response
    if tool_results:
        formatted_results = "\n\n🔧 MCP 도구 실행 결과:\n"
        for i, result in enumerate(tool_results, 1):
            tool_name = result["tool"]
            formatted_results += f"{i}. {tool_name}: "

            # Format result based on tool type
            if tool_name == "web_screenshot":
                formatted_results += "스크린샷이 성공적으로 촬영되었습니다."
            elif tool_name == "read_file":
                formatted_results += "파일을 성공적으로 읽었습니다."
            elif tool_name == "rag_search":
                formatted_results += "문서 검색이 완료되었습니다."
            else:
                formatted_results += "실행 완료"
            formatted_results += "\n"

        return formatted_results

    return ""


def extract_tool_args_from_query(query: str, tool_name: str) -> Dict[str, Any]:
    """
    Extract tool arguments from user query
    """
    args = {}
    query.lower()

    if tool_name == "web_screenshot":
        # Try to extract URL from query
        import re

        url_pattern = (
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        urls = re.findall(url_pattern, query)
        if urls:
            args["url"] = urls[0]
        else:
            # Default URL if none found
            args["url"] = "https://www.google.com"

    elif tool_name == "read_file":
        # Try to extract file path from query
        words = query.split()
        for word in words:
            if "." in word and (
                "/" in word
                or "\\" in word
                or word.endswith(".txt")
                or word.endswith(".py")
                or word.endswith(".md")
            ):
                args["path"] = word
                break
        if "path" not in args:
            args["path"] = "README.md"  # Default file

    elif tool_name == "rag_search":
        # Use the query itself for RAG search
        args["query"] = query

    elif tool_name == "execute_python":
        # Extract Python code if present
        if "print(" in query or "def " in query or "import " in query:
            # Find code block
            code_start = query.find("```")
            if code_start != -1:
                code_end = query.find("```", code_start + 3)
                if code_end != -1:
                    args["code"] = query[code_start + 3 : code_end].strip()
            else:
                args["code"] = 'print("Hello from auto-generated code!")'
        else:
            args["code"] = f'print("Query: {query}")'

    return args


def get_mcp_tools() -> Optional[List[Dict[str, Any]]]:
    """
    Get available MCP tools list
    """
    try:
        response = requests.get(f"{MCP_URL}/tools", timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("tools", [])
    except Exception as e:
        print(f"❌ Error getting MCP tools: {e}")
        return None


def call_rag_api(
    query: str,
    collection: str = "default",
    include_context: bool = True,
    working_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Call RAG service for document-based queries with current directory support
    """
    payload = {
        "query": query,
        "collection": collection,
        "limit": 5,
        "score_threshold": 0.7,
        "include_context": include_context,
    }

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        print(f"🔍 Searching documents in '{collection}' collection...")
        response = requests.post(f"{RAG_URL}/query", json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        data = response.json()
        answer = data.get("answer", "No answer available")
        sources = data.get("sources", [])

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
    payload = {"collection": collection, "chunk_size": 1000, "chunk_overlap": 200}

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        print(f"📚 Indexing documents into '{collection}' collection...")
        if directory:
            print(f"📁 From directory: {directory}")

        response = requests.post(f"{RAG_URL}/index", json=payload, headers=headers, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"✅ {data['message']}")
        print(f"📄 Indexed {len(data['indexed_files'])} files, {data['total_chunks']} chunks")

        for file_info in data["indexed_files"]:
            print(f"   - {file_info['file']} ({file_info['chunks']} chunks)")

        return True

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to RAG service.")
        print("💡 Make sure RAG system is running: make up-p2")
        return False
    except Exception as e:
        print(f"❌ Indexing Error: {e}")
        return False


def call_api(
    query: str, model_type: str = "auto", max_tokens: int = 500, streaming: bool = True
) -> Optional[str]:
    """
    Call the API with the available model
    Enhanced with analytics and smart optimization
    Now supports streaming responses like ChatGPT/Claude Code
    """
    start_time = time.time()

    # Determine query type for temperature adjustment
    detected_type = None
    if model_type == "auto":
        detected_type = detect_query_type(query)
        model_type = detected_type

    # Get smart recommendation if analytics available
    if ANALYTICS_ENABLED and analytics:
        try:
            recommendation = analytics.get_model_recommendation(query, model_type)
            if recommendation.get("confidence", 0) > 0.7:
                suggested_model = recommendation["recommended_model"]
                if suggested_model in AVAILABLE_MODELS.values():
                    print(
                        f"💡 Smart recommendation: Using {suggested_model} (confidence: {recommendation['confidence']:.2f})"
                    )
        except Exception:
            pass  # Fallback to default logic

    # Use appropriate model based on query type
    model_name = AVAILABLE_MODELS.get(model_type, DEFAULT_MODEL)

    # Prepare request with appropriate context
    if model_type == "code":
        system_prompt = (
            "You are a helpful coding assistant. Provide clear, well-commented code solutions."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        temperature = 0.2
    else:
        system_prompt = "You are a helpful Korean AI assistant. You must respond ONLY in Korean language. Never use Chinese, English or any other language. 당신은 한국어 AI 어시스턴트입니다. 반드시 한국어로만 답변해주세요. 중국어나 영어를 절대 사용하지 마세요."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        temperature = 0.7

    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": streaming,
    }

    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        # Check if MCP tools should be auto-executed
        mcp_results = ""
        mcp_suggestions = analyze_query_for_mcp_tools(query)
        if mcp_suggestions:
            high_conf = [s for s in mcp_suggestions if s["confidence"] >= 0.8]
            if high_conf:
                print(f"🔍 Detected {len(high_conf)} high-confidence MCP tool(s) for this query")
                mcp_results = auto_execute_mcp_tools(query)

        print(f"🤖 Using {model_type} model ({model_name})...")

        # Enhance query with MCP results if available
        enhanced_query = query
        if mcp_results:
            enhanced_query = f"{query}{mcp_results}"
            # Update the user message in payload
            messages[-1]["content"] = enhanced_query
            payload["messages"] = messages

        response = requests.post(
            API_URL, json=payload, headers=headers, timeout=120, stream=streaming
        )
        response.raise_for_status()

        full_content = ""
        tokens_used = 0

        if streaming:
            print("\n🤖 AI: ", end="", flush=True)

            # Process streaming response
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                choice = data["choices"][0]
                                if "delta" in choice and "content" in choice["delta"]:
                                    content_chunk = choice["delta"]["content"]
                                    print(content_chunk, end="", flush=True)
                                    full_content += content_chunk
                                if "usage" in data:
                                    tokens_used = data["usage"].get("total_tokens", 0)
                        except json.JSONDecodeError:
                            continue

            print()  # New line after streaming completes
        else:
            # Non-streaming response
            data = response.json()
            full_content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

        # Log analytics
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    tokens_used=tokens_used,
                    success=True,
                    session_id=SESSION_ID,
                )
            except Exception:
                pass  # Don't fail on analytics errors

        # Save to memory system
        if MEMORY_ENABLED and full_content:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                save_conversation_to_memory(
                    user_query=query,
                    ai_response=full_content,
                    model_used=model_name,
                    session_id=SESSION_ID,
                    response_time_ms=response_time_ms,
                    token_count=tokens_used,
                )
            except Exception as e:
                # 메모리 저장 실패해도 응답은 반환
                print(f"⚠️ Memory save failed: {e}")

        return full_content

    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to local AI server"
        print(f"❌ Error: {error_msg}")
        print("💡 Make sure the server is running: make up-p1")
        if ANALYTICS_ENABLED and analytics:
            try:
                response_time_ms = int((time.time() - start_time) * 1000)
                analytics.log_usage(
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=error_msg,
                    session_id=SESSION_ID,
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
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=error_msg,
                    session_id=SESSION_ID,
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
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=error_msg,
                    session_id=SESSION_ID,
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
                    query=query,
                    query_type=model_type,
                    detected_type=detected_type or model_type,
                    model_used=model_name,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=error_msg,
                    session_id=SESSION_ID,
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
  ai "안녕하세요!"                        # Auto-detect (chat model, streaming)
  ai "Python 함수 만들어줘"               # Auto-detect (code model, streaming)
  ai --code "일반 질문이지만 코딩모델로"      # Force code model
  ai --chat "코딩 질문이지만 채팅모델로"      # Force chat model
  ai --no-stream "한번에 보여줘"           # Disable streaming (show all at once)
  ai --rag "파일 읽기 방법은?"              # Search documents with RAG
  ai --index                           # Index documents (default collection)
  ai --index myproject                 # Index documents into 'myproject' collection
  ai --rag --collection myproject "질문"   # Query specific collection
  ai --tokens 200 "짧은 답변 원함"         # Limit response length
        """,
    )

    parser.add_argument("query", nargs="?", help="Your question or prompt")
    parser.add_argument("--code", action="store_true", help="Force use of code model")
    parser.add_argument("--chat", action="store_true", help="Force use of chat model")
    parser.add_argument("--rag", action="store_true", help="Use RAG (document-based) search")
    parser.add_argument(
        "--index",
        metavar="COLLECTION",
        nargs="?",
        const="default",
        help="Index documents for RAG (default collection: 'default')",
    )
    parser.add_argument(
        "--collection",
        default="default",
        help="RAG collection name (default: 'default')",
    )
    parser.add_argument(
        "--tokens",
        type=int,
        default=500,
        help="Maximum tokens in response (default: 500)",
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive mode")
    parser.add_argument("--analytics", action="store_true", help="Show analytics dashboard")
    parser.add_argument("--optimize", action="store_true", help="Run database optimization")
    parser.add_argument("--mcp", metavar="TOOL", help="Call MCP tool directly")
    parser.add_argument("--mcp-args", metavar="ARGS", help="Arguments for MCP tool (JSON format)")
    parser.add_argument("--mcp-list", action="store_true", help="List available MCP tools")
    parser.add_argument(
        "--tools", action="store_true", help="Enable AI to use MCP tools automatically"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming responses (show all at once)",
    )

    # Memory system commands
    parser.add_argument("--memory", action="store_true", help="Show memory system status")
    parser.add_argument("--memory-init", action="store_true", help="Initialize project memory")
    parser.add_argument("--memory-search", metavar="QUERY", help="Search conversations in memory")
    parser.add_argument(
        "--memory-cleanup", action="store_true", help="Clean up expired conversations"
    )
    parser.add_argument(
        "--memory-backup",
        metavar="PATH",
        nargs="?",
        const=None,
        help="Export memory backup",
    )
    parser.add_argument(
        "--memory-stats", action="store_true", help="Show detailed memory statistics"
    )
    parser.add_argument("--memory-dir", metavar="DIR", help="Override memory storage directory")

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

    # Handle memory commands
    if (
        any(
            [
                args.memory,
                args.memory_init,
                args.memory_search,
                args.memory_cleanup,
                args.memory_backup is not None,
                args.memory_stats,
            ]
        )
        or args.memory_dir
    ):
        if not MEMORY_ENABLED:
            print("❌ Memory system not available. Install memory_system.py.")
            sys.exit(1)

        # CLI에서 메모리 디렉토리 지정된 경우 새 인스턴스 생성
        if args.memory_dir:
            from memory_system import MemorySystem, set_memory_system

            custom_instance = MemorySystem(data_dir=args.memory_dir)
            set_memory_system(custom_instance)
            print(f"💾 Using custom memory directory: {args.memory_dir}")

        handle_memory_commands(args)
        sys.exit(0)

    # Handle MCP tools list
    if args.mcp_list:
        show_mcp_tools()
        sys.exit(0)

    # Handle direct MCP tool call
    if args.mcp:
        handle_mcp_call(args.mcp, args.mcp_args)
        sys.exit(0)

    # Determine model type and streaming preference
    model_type = "auto"
    if args.code:
        model_type = "code"
    elif args.chat:
        model_type = "chat"

    use_streaming = not args.no_stream

    # Interactive mode
    if args.interactive:
        print("🤖 Local AI Interactive Mode")
        print("Type 'exit' or 'quit' to exit, 'help' for commands")
        stream_status = "ON" if use_streaming else "OFF"
        print(f"Streaming: {stream_status} (use :stream to toggle)")
        print("-" * 50)

        current_streaming = use_streaming
        while True:
            try:
                query = input("\n💬 You: ").strip()
                if not query:
                    continue
                if query.lower() in ["exit", "quit", "q"]:
                    print("👋 Goodbye!")
                    break
                if query.lower() == "help":
                    print("Commands:")
                    print("  exit/quit - Exit interactive mode")
                    print("  :code <query> - Force code model")
                    print("  :chat <query> - Force chat model")
                    print("  :rag <query> - Search documents with RAG")
                    print("  :index [collection] - Index documents")
                    print("  :analytics - Show usage analytics")
                    print("  :optimize - Run database optimization")
                    print("  :mcp-list - Show available MCP tools")
                    print("  :mcp <tool> [args] - Call MCP tool directly")
                    print("  :stream - Toggle streaming mode")
                    continue

                if query.startswith(":stream"):
                    current_streaming = not current_streaming
                    status = "ON" if current_streaming else "OFF"
                    print(f"🔄 Streaming mode: {status}")
                    continue

                # Parse inline commands
                if query.startswith(":code "):
                    query = query[6:]
                    model_type = "code"
                    response = call_api(query, model_type, args.tokens, current_streaming)
                elif query.startswith(":chat "):
                    query = query[6:]
                    model_type = "chat"
                    response = call_api(query, model_type, args.tokens, current_streaming)
                elif query.startswith(":rag "):
                    query = query[5:]
                    response = call_rag_api(query, args.collection)
                elif query.startswith(":index"):
                    parts = query.split(" ", 1)
                    collection = parts[1] if len(parts) > 1 else "default"
                    index_documents(collection)
                    continue
                elif query.startswith(":analytics"):
                    if ANALYTICS_ENABLED:
                        show_analytics_dashboard()
                    else:
                        print("❌ Analytics not available")
                    continue
                elif query.startswith(":optimize"):
                    if ANALYTICS_ENABLED:
                        run_optimization()
                    else:
                        print("❌ Analytics not available")
                    continue
                elif query.startswith(":mcp-list"):
                    show_mcp_tools()
                    continue
                elif query.startswith(":mcp "):
                    parts = query[5:].split(" ", 1)
                    tool_name = parts[0]
                    args_json = parts[1] if len(parts) > 1 else None
                    handle_mcp_call(tool_name, args_json)
                    continue
                else:
                    model_type = "auto"
                    response = call_api(query, model_type, args.tokens, current_streaming)

                # For non-streaming mode, show the response with AI prefix
                if response and not current_streaming:
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
        # Auto-index current directory if it contains documents
        current_dir = os.getcwd()
        doc_extensions = [
            ".md",
            ".txt",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".yaml",
            ".yml",
        ]
        has_docs = any(
            any(f.endswith(ext) for ext in doc_extensions)
            for f in os.listdir(current_dir)
            if os.path.isfile(os.path.join(current_dir, f))
        )

        if has_docs:
            print(f"📁 Auto-indexing current directory: {current_dir}")
            try:
                index_response = requests.post(
                    f"{RAG_URL}/index",
                    params={
                        "collection": args.collection or "current",
                        "path": current_dir,
                    },
                    timeout=60,
                )
                if index_response.status_code == 200:
                    print("✅ Directory indexed successfully")
                else:
                    print(f"⚠️ Indexing failed: {index_response.status_code}")
            except Exception as e:
                print(f"⚠️ Auto-indexing error: {e}")

        response = call_rag_api(args.query, args.collection or "current", working_dir=current_dir)
    else:
        response = call_api(args.query, model_type, args.tokens, use_streaming)

    # For non-streaming single query mode, show the response without prefix since it's already shown during streaming
    if response and not use_streaming:
        print(response)
    elif not response:
        sys.exit(1)


def show_analytics_dashboard():
    """Show comprehensive analytics dashboard"""
    try:
        print("📊 AI Usage Analytics Dashboard")
        print("=" * 50)

        # Get analytics summary
        summary = analytics.get_analytics_summary(hours=24)

        print("\n📈 Usage Statistics (Last 24h)")
        print("-" * 30)
        for stat in summary["usage_stats"]:
            print(f"  {stat['query_type'].upper()} ({stat['model_used']}):")
            print(f"    Queries: {stat['total_queries']}")
            print(f"    Avg Response: {stat['avg_response_time']:.0f}ms")
            print(f"    Success Rate: {stat['success_rate']:.1f}%")
            if stat["avg_tokens"]:
                print(f"    Avg Tokens: {stat['avg_tokens']:.0f}")
            print()

        print("\n⏰ Peak Usage Times")
        print("-" * 30)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for peak in summary["peak_times"]:
            day_name = days[peak["day_of_week"]]
            print(f"  {day_name} {peak['hour_of_day']:02d}:00 - {peak['total_usage']} queries")

        print("\n🏆 Model Performance Ranking")
        print("-" * 30)
        for perf in summary["model_performance"]:
            print(f"  {perf['model_name']} ({perf['query_type']})")
            print(f"    Speed: {perf['avg_response_time_ms']:.0f}ms")
            print(f"    Reliability: {perf['success_rate']:.1%}")
            print(f"    Usage: {perf['total_usage_count']} times")
            print()

        print("\n💡 Smart Recommendations")
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
        print("✅ Optimization complete!")
        print(f"  Cleaned records: {result['cleaned_records']}")
        print(f"  Database size: {result['database_size_mb']:.1f}MB")
    except Exception as e:
        print(f"❌ Error during optimization: {e}")


def show_mcp_tools():
    """Show available MCP tools"""
    print("🔧 Available MCP Tools")
    print("=" * 30)

    tools = get_mcp_tools()
    if not tools:
        print("❌ No MCP tools available or server unreachable")
        return

    for tool in tools:
        name = tool.get("name", "Unknown")
        desc = tool.get("description", "No description")
        print(f"\n🔨 {name}")
        print(f"   {desc}")

        # Show required arguments
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        if required:
            print(f"   Required: {', '.join(required)}")


def handle_mcp_call(tool_name: str, args_json: str = None):
    """Handle direct MCP tool call"""
    try:
        # Parse arguments if provided
        kwargs = {}
        if args_json:
            import json
            import ast

            # Handle potential encoding issues with Korean characters and shell escapes
            try:
                # First try direct parsing
                kwargs = json.loads(args_json)
            except json.JSONDecodeError:
                try:
                    # Try with literal_eval for safer parsing of shell-escaped strings
                    # Replace common shell escapes
                    cleaned_json = args_json.replace("\\!", "!")
                    kwargs = json.loads(cleaned_json)
                except (json.JSONDecodeError, ValueError):
                    # Final fallback - try to parse as Python literal
                    try:
                        kwargs = ast.literal_eval(args_json.replace("\\!", "!"))
                        if not isinstance(kwargs, dict):
                            kwargs = {"value": kwargs}
                    except (ValueError, SyntaxError):
                        print(f"⚠️ Cannot parse arguments: {args_json}")
                        print("💡 Try using double quotes and proper JSON format")
                        return

        # Call the tool
        result = call_mcp_tool(tool_name, **kwargs)
        if result:
            print("✅ MCP Tool Result:")
            if isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, str) and len(value) > 200:
                        print(f"  {key}: {value[:200]}...")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  {result}")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in --mcp-args: {e}")
    except Exception as e:
        print(f"❌ Error calling MCP tool: {e}")


def save_conversation_to_memory(
    user_query: str,
    ai_response: str,
    model_used: str,
    session_id: str,
    response_time_ms: int = None,
    token_count: int = None,
) -> bool:
    """AI 대화를 메모리에 저장"""
    if not MEMORY_ENABLED:
        return False

    try:
        # API 우선 시도
        try:
            data = {
                "user_query": user_query,
                "ai_response": ai_response,
                "model_used": model_used,
                "session_id": session_id,
                "response_time_ms": response_time_ms,
                "token_count": token_count,
                "project_path": os.getcwd(),
            }

            response = requests.post(f"{MEMORY_API_URL}/conversations", json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                print(f"💾 Conversation saved to memory (ID: {result.get('conversation_id')})")
                return True
            else:
                print(f"⚠️ Memory API failed: {response.status_code}")

        except requests.RequestException:
            print("⚠️ Memory API unavailable, using local storage")

        # 로컬 폴백
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()

        conversation_id = memory_system.save_conversation(
            project_id=project_id,
            user_query=user_query,
            ai_response=ai_response,
            model_used=model_used,
            session_id=session_id,
            response_time_ms=response_time_ms,
            token_count=token_count,
        )

        if conversation_id:
            print(f"💾 Conversation saved locally (ID: {conversation_id})")
            return True

    except Exception as e:
        print(f"⚠️ Failed to save conversation: {e}")

    return False


def handle_memory_commands(args):
    """메모리 시스템 명령어 처리"""

    if args.memory:
        # 메모리 상태 표시
        show_memory_status()

    elif args.memory_init:
        # 프로젝트 메모리 초기화
        init_project_memory()

    elif args.memory_search:
        # 메모리 검색
        handle_memory_search(args.memory_search)

    elif args.memory_cleanup:
        # 만료된 대화 정리
        try:
            deleted_count = handle_memory_cleanup()
            print(f"🧹 Cleanup completed: {deleted_count} conversations removed")
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")

    elif args.memory_backup is not None:
        # 메모리 백업
        try:
            backup_path = handle_memory_backup(args.memory_backup)
            print(f"💾 Memory backup saved to: {backup_path}")
        except Exception as e:
            print(f"❌ Backup failed: {e}")

    elif args.memory_stats:
        # 메모리 통계
        show_memory_stats()


def show_memory_status():
    """메모리 시스템 상태 표시"""
    try:
        # API 시도
        try:
            response = requests.get(f"{MEMORY_API_URL}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print("💾 Memory System Status (API)")
                print(f"   Status: {health.get('status', 'unknown')}")
                print(
                    f"   Storage: {'Available' if health.get('storage_available') else 'Unavailable'}"
                )
                print(
                    f"   Vector Search: {'Enabled' if health.get('vector_enabled') else 'Disabled'}"
                )
                return
        except requests.RequestException:
            pass

        # 로컬 폴백
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()
        stats = memory_system.get_conversation_stats(project_id)

        print("💾 Memory System Status (Local)")
        print(f"   Project ID: {project_id}")
        print(f"   Total Conversations: {stats.get('total_conversations', 0)}")
        print(f"   Average Importance: {stats.get('avg_importance', 0):.1f}")
        print(f"   Latest: {stats.get('latest_conversation', 'None')}")

    except Exception as e:
        print(f"❌ Error getting memory status: {e}")


def init_project_memory():
    """프로젝트 메모리 초기화"""
    try:
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()

        print(f"🎯 Initializing memory for project: {project_id}")
        print(f"📁 Memory directory: {memory_system.data_dir}")

        # 테스트 대화 저장
        test_id = memory_system.save_conversation(
            project_id=project_id,
            user_query="Memory system initialization test",
            ai_response="Memory system initialized successfully!",
            model_used="system",
            session_id="init",
        )

        if test_id:
            print(f"✅ Memory initialization successful (Test ID: {test_id})")
        else:
            print("❌ Memory initialization failed")

    except Exception as e:
        print(f"❌ Error initializing memory: {e}")


def handle_memory_search(query: str):
    """메모리 검색 처리"""
    try:
        # API 우선 시도
        try:
            data = {"query": query, "limit": 10, "use_vector_search": False}

            response = requests.post(
                f"{MEMORY_API_URL}/conversations/search", json=data, timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                results = result.get("results", [])
                print(f"🔍 Found {len(results)} conversations:")

                for i, conv in enumerate(results, 1):
                    importance = conv.get("importance_score", 5)
                    timestamp = conv.get("timestamp", "")[:16] if conv.get("timestamp") else ""
                    print(f"\n{i}. [{importance}] {timestamp}")
                    print(f"   Q: {conv.get('user_query', '')[:100]}...")
                    print(f"   A: {conv.get('ai_response', '')[:100]}...")

                return
        except requests.RequestException:
            print("⚠️ Memory API unavailable, using local search")

        # 로컬 폴백
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()

        results = memory_system.search_conversations(project_id=project_id, query=query, limit=10)

        print(f"🔍 Found {len(results)} conversations:")
        for i, conv in enumerate(results, 1):
            importance = conv.get("importance_score", 5)
            timestamp = conv.get("timestamp", "")[:16] if conv.get("timestamp") else ""
            print(f"\n{i}. [{importance}] {timestamp}")
            print(f"   Q: {conv.get('user_query', '')[:100]}...")
            print(f"   A: {conv.get('ai_response', '')[:100]}...")

    except Exception as e:
        print(f"❌ Error searching memory: {e}")


def handle_memory_cleanup() -> int:
    """메모리 정리 처리"""
    try:
        # API 우선 시도
        try:
            memory_system = get_memory_system()
            project_id = memory_system.get_project_id()

            response = requests.post(f"{MEMORY_API_URL}/projects/{project_id}/cleanup", timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get("deleted_conversations", 0)
        except requests.RequestException:
            print("⚠️ Memory API unavailable, using local cleanup")

        # 로컬 폴백
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()
        return memory_system.cleanup_expired_conversations(project_id)

    except Exception as e:
        print(f"❌ Error cleaning up memory: {e}")
        return 0


def handle_memory_backup(output_path: str = None) -> str:
    """메모리 백업 처리"""
    try:
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()

        # API 우선 시도
        try:
            data = {"project_id": project_id, "backup_type": "json"}
            response = requests.post(
                f"{MEMORY_API_URL}/projects/{project_id}/backup", json=data, timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("backup_path", "API backup completed")
        except requests.RequestException:
            print("⚠️ Memory API unavailable, using local backup")

        # 로컬 폴백
        backup_path = memory_system.export_memory_backup(
            project_id=project_id,
            output_path=Path(output_path) if output_path else None,
        )

        return str(backup_path) if backup_path else "Backup failed"

    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return "Backup failed"


def show_memory_stats():
    """메모리 통계 표시"""
    try:
        memory_system = get_memory_system()
        project_id = memory_system.get_project_id()

        # API 우선 시도
        try:
            response = requests.get(f"{MEMORY_API_URL}/projects/{project_id}/stats", timeout=10)

            if response.status_code == 200:
                result = response.json()
                stats = result.get("stats", {})
                print("📊 Memory Statistics (API)")
            else:
                raise requests.RequestException()
        except requests.RequestException:
            print("⚠️ Memory API unavailable, using local stats")
            stats = memory_system.get_conversation_stats(project_id)
            print("📊 Memory Statistics (Local)")

        print(f"   Project ID: {project_id}")
        print(f"   Total Conversations: {stats.get('total_conversations', 0)}")
        print(f"   Average Importance: {stats.get('avg_importance', 0):.2f}")
        print(f"   Oldest: {stats.get('oldest_conversation', 'None')}")
        print(f"   Latest: {stats.get('latest_conversation', 'None')}")

        # 중요도별 분포
        importance_dist = stats.get("importance_distribution", {})
        if importance_dist:
            print("\n   Importance Distribution:")
            for score, count in sorted(importance_dist.items()):
                print(f"     Level {score}: {count} conversations")

        # 모델별 사용량
        model_usage = stats.get("model_usage", {})
        if model_usage:
            print("\n   Model Usage:")
            for model, count in model_usage.items():
                print(f"     {model}: {count} conversations")

    except Exception as e:
        print(f"❌ Error getting memory stats: {e}")


if __name__ == "__main__":
    main()
