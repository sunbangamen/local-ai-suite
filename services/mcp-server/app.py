#!/usr/bin/env python3
"""
MCP Server for Local AI Suite
포트 8020에서 실행되는 로컬 AI용 Model Context Protocol 서버

핵심 기능:
- Resources: 로컬 파일 시스템 접근
- Tools: 코드 실행, Git 분석, RAG 검색
- Prompts: AI 작업 템플릿 제공
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
import base64
import tempfile
from io import BytesIO
from PIL import Image

# Playwright와 Notion 임포트 (지연 로딩)
playwright = None
notion_client = None

async def init_playwright():
    """Playwright 초기화"""
    global playwright
    if playwright is None:
        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
    return playwright

def init_notion():
    """Notion 클라이언트 초기화"""
    global notion_client
    if notion_client is None:
        from notion_client import Client
        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            notion_client = Client(auth=notion_token)
    return notion_client

# 환경 변수
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/workspace")
RAG_URL = os.getenv("RAG_URL", "http://rag-service:8002")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")

# MCP 서버 인스턴스
mcp = FastMCP("Local AI MCP Server")

# FastAPI 앱 (헬스체크용)
app = FastAPI(title="Local AI MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mcp-server"}

# =============================================================================
# Pydantic Models
# =============================================================================

class FileInfo(BaseModel):
    path: str
    content: str
    size: int
    type: str

class ExecutionResult(BaseModel):
    command: str
    stdout: str
    stderr: str
    returncode: int
    success: bool

class RAGResult(BaseModel):
    query: str
    response: str
    sources: List[str] = []

class AIResponse(BaseModel):
    model: str
    message: str
    response: str

class WebScreenshotResult(BaseModel):
    url: str
    screenshot_base64: str
    width: int
    height: int
    timestamp: str

class WebScrapeResult(BaseModel):
    url: str
    selector: str
    data: List[str]
    count: int

class WebUIAnalysis(BaseModel):
    url: str
    title: str
    css_styles: Dict[str, Any]
    layout_info: Dict[str, Any]
    color_scheme: List[str]
    fonts: List[str]

class NotionPageResult(BaseModel):
    page_id: str
    url: str
    title: str
    status: str

# =============================================================================
# MCP Resources - 파일 시스템 접근
# =============================================================================

@mcp.resource("file://{path}")
async def read_file_resource(path: str) -> str:
    """파일 내용을 리소스로 제공"""
    file_path = Path(PROJECT_ROOT) / path

    # 보안: 프로젝트 외부 접근 차단
    try:
        file_path.resolve().relative_to(Path(PROJECT_ROOT).resolve())
    except ValueError:
        raise ValueError(f"프로젝트 외부 파일 접근 금지: {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없음: {file_path}")

    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        return content

@mcp.resource("project://files")
async def list_project_files() -> str:
    """프로젝트 파일 목록 제공"""
    project_path = Path(PROJECT_ROOT)
    files = []

    # Python 파일들
    for file_path in project_path.rglob("*.py"):
        if not any(part.startswith('.') for part in file_path.parts):
            files.append({
                "path": str(file_path.relative_to(project_path)),
                "type": "python",
                "size": file_path.stat().st_size if file_path.exists() else 0
            })

    # 설정 파일들
    for pattern in ["*.yml", "*.yaml", "*.json", "*.md", "*.env*"]:
        for file_path in project_path.rglob(pattern):
            if not any(part.startswith('.') for part in file_path.parts):
                files.append({
                    "path": str(file_path.relative_to(project_path)),
                    "type": "config",
                    "size": file_path.stat().st_size if file_path.exists() else 0
                })

    return json.dumps(files[:50], indent=2)  # 최대 50개 제한

# =============================================================================
# MCP Tools - 코드 실행 및 시스템 도구
# =============================================================================

@mcp.tool()
async def execute_python(code: str, timeout: int = 30) -> ExecutionResult:
    """Python 코드 실행"""
    # 보안: 위험한 모듈 임포트 차단
    dangerous_imports = ["os", "sys", "subprocess", "shutil", "requests"]
    if any(f"import {module}" in code or f"from {module}" in code for module in dangerous_imports):
        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout="",
            stderr="보안상 위험한 모듈 사용이 감지되어 실행을 차단했습니다.",
            returncode=1,
            success=False
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout=stdout.decode() if stdout else "",
            stderr=stderr.decode() if stderr else "",
            returncode=proc.returncode or 0,
            success=proc.returncode == 0
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout="",
            stderr=f"타임아웃 ({timeout}초)",
            returncode=124,
            success=False
        )
    except Exception as e:
        return ExecutionResult(
            command=f"python -c '{code[:50]}...'",
            stdout="",
            stderr=f"실행 오류: {str(e)}",
            returncode=1,
            success=False
        )

@mcp.tool()
async def execute_bash(command: str, timeout: int = 30) -> ExecutionResult:
    """Bash 명령어 실행"""
    # 보안: 위험한 명령어 차단
    dangerous_commands = ["rm", "sudo", "chmod", "chown", "mv"]
    if any(cmd in command.split() for cmd in dangerous_commands):
        return ExecutionResult(
            command=command,
            stdout="",
            stderr="보안상 위험한 명령어가 감지되어 실행을 차단했습니다.",
            returncode=1,
            success=False
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        return ExecutionResult(
            command=command,
            stdout=stdout.decode() if stdout else "",
            stderr=stderr.decode() if stderr else "",
            returncode=proc.returncode or 0,
            success=proc.returncode == 0
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=f"타임아웃 ({timeout}초)",
            returncode=124,
            success=False
        )
    except Exception as e:
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=f"실행 오류: {str(e)}",
            returncode=1,
            success=False
        )

@mcp.tool()
async def read_file(path: str) -> FileInfo:
    """파일 내용 읽기"""
    file_path = Path(PROJECT_ROOT) / path

    # 보안: 프로젝트 외부 접근 차단
    try:
        file_path.resolve().relative_to(Path(PROJECT_ROOT).resolve())
    except ValueError:
        raise ValueError("프로젝트 외부 파일 접근이 금지되어 있습니다.")

    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        return FileInfo(
            path=str(file_path.relative_to(Path(PROJECT_ROOT))),
            content=content,
            size=len(content),
            type=file_path.suffix
        )
    except Exception as e:
        raise Exception(f"파일 읽기 오류: {str(e)}")

@mcp.tool()
async def write_file(path: str, content: str) -> FileInfo:
    """파일 내용 쓰기"""
    file_path = Path(PROJECT_ROOT) / path

    # 보안: 프로젝트 외부 접근 차단
    try:
        file_path.resolve().relative_to(Path(PROJECT_ROOT).resolve())
    except ValueError:
        raise ValueError("프로젝트 외부 파일 접근이 금지되어 있습니다.")

    try:
        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)

        return FileInfo(
            path=str(file_path.relative_to(Path(PROJECT_ROOT))),
            content=content,
            size=len(content),
            type=file_path.suffix
        )
    except Exception as e:
        raise Exception(f"파일 쓰기 오류: {str(e)}")

@mcp.tool()
async def rag_search(query: str, collection: str = "default") -> RAGResult:
    """RAG 시스템에서 문서 검색"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RAG_URL}/query",
                json={"query": query, "collection": collection},
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()
            return RAGResult(
                query=query,
                response=data.get('response', '응답 없음'),
                sources=data.get('sources', [])
            )
    except Exception as e:
        raise Exception(f"RAG 검색 오류: {str(e)}")

@mcp.tool()
async def ai_chat(message: str, model: str = "qwen2.5-14b-instruct") -> AIResponse:
    """로컬 AI 모델과 대화"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_GATEWAY_URL}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": 512,
                    "temperature": 0.3
                },
                timeout=60.0
            )
            response.raise_for_status()

            data = response.json()
            ai_response = data["choices"][0]["message"]["content"]
            return AIResponse(
                model=model,
                message=message,
                response=ai_response
            )
    except Exception as e:
        raise Exception(f"AI 채팅 오류: {str(e)}")

@mcp.tool()
async def git_status(path: str = ".") -> ExecutionResult:
    """Git 저장소 상태 확인"""
    repo_path = Path(PROJECT_ROOT) / path

    try:
        # git status 실행
        proc = await asyncio.create_subprocess_exec(
            "git", "status", "--porcelain",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(repo_path)
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return ExecutionResult(
                command="git status --porcelain",
                stdout="",
                stderr=stderr.decode() if stderr else "Git 명령 실행 실패",
                returncode=proc.returncode or 1,
                success=False
            )

        status_output = stdout.decode().strip()
        if not status_output:
            status_output = "변경사항 없음 (깨끗함)"

        return ExecutionResult(
            command="git status --porcelain",
            stdout=status_output,
            stderr="",
            returncode=0,
            success=True
        )
    except Exception as e:
        return ExecutionResult(
            command="git status --porcelain",
            stdout="",
            stderr=f"Git 상태 확인 오류: {str(e)}",
            returncode=1,
            success=False
        )

# =============================================================================
# Playwright 웹 자동화 도구
# =============================================================================

@mcp.tool()
async def web_screenshot(url: str, width: int = 1280, height: int = 720) -> WebScreenshotResult:
    """웹사이트 스크린샷 촬영"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})

        await page.goto(url, wait_until="networkidle")
        screenshot_bytes = await page.screenshot(full_page=True)

        # Base64 인코딩
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        await browser.close()

        from datetime import datetime
        return WebScreenshotResult(
            url=url,
            screenshot_base64=screenshot_b64,
            width=width,
            height=height,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise Exception(f"스크린샷 촬영 오류: {str(e)}")

@mcp.tool()
async def web_scrape(url: str, selector: str, attribute: str = "textContent") -> WebScrapeResult:
    """웹사이트에서 특정 요소 크롤링"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        # 요소들 찾기
        elements = await page.query_selector_all(selector)
        data = []

        for element in elements:
            if attribute == "textContent":
                content = await element.text_content()
            elif attribute == "innerHTML":
                content = await element.inner_html()
            elif attribute == "href":
                content = await element.get_attribute("href")
            elif attribute == "src":
                content = await element.get_attribute("src")
            else:
                content = await element.get_attribute(attribute)

            if content and content.strip():
                data.append(content.strip())

        await browser.close()

        return WebScrapeResult(
            url=url,
            selector=selector,
            data=data,
            count=len(data)
        )

    except Exception as e:
        raise Exception(f"웹 크롤링 오류: {str(e)}")

@mcp.tool()
async def web_analyze_ui(url: str) -> WebUIAnalysis:
    """웹사이트 UI/디자인 분석"""
    try:
        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        # 제목 가져오기
        title = await page.title()

        # CSS 스타일 분석
        css_analysis = await page.evaluate("""
            () => {
                const styles = {};
                const computedStyle = window.getComputedStyle(document.body);

                // 기본 스타일 정보
                styles.backgroundColor = computedStyle.backgroundColor;
                styles.color = computedStyle.color;
                styles.fontFamily = computedStyle.fontFamily;
                styles.fontSize = computedStyle.fontSize;

                // 레이아웃 정보
                const layout = {};
                layout.width = document.body.offsetWidth;
                layout.height = document.body.offsetHeight;
                layout.padding = computedStyle.padding;
                layout.margin = computedStyle.margin;

                // 색상 팔레트 추출
                const colors = new Set();
                const elements = document.querySelectorAll('*');
                for (let i = 0; i < Math.min(elements.length, 100); i++) {
                    const style = window.getComputedStyle(elements[i]);
                    if (style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        colors.add(style.backgroundColor);
                    }
                    if (style.color !== 'rgba(0, 0, 0, 0)') {
                        colors.add(style.color);
                    }
                }

                // 폰트 정보
                const fonts = new Set();
                for (let i = 0; i < Math.min(elements.length, 50); i++) {
                    const style = window.getComputedStyle(elements[i]);
                    fonts.add(style.fontFamily);
                }

                return {
                    styles,
                    layout,
                    colors: Array.from(colors).slice(0, 10),
                    fonts: Array.from(fonts).slice(0, 5)
                };
            }
        """)

        await browser.close()

        return WebUIAnalysis(
            url=url,
            title=title,
            css_styles=css_analysis["styles"],
            layout_info=css_analysis["layout"],
            color_scheme=css_analysis["colors"],
            fonts=css_analysis["fonts"]
        )

    except Exception as e:
        raise Exception(f"UI 분석 오류: {str(e)}")

@mcp.tool()
async def web_automate(url: str, actions: str) -> ExecutionResult:
    """웹 자동화 실행 (JSON 형태의 액션 리스트)"""
    try:
        import json
        action_list = json.loads(actions)

        pw = await init_playwright()
        browser = await pw.chromium.launch(headless=False)  # 디버깅을 위해 headless=False
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")

        results = []

        for action in action_list:
            action_type = action.get("type")
            selector = action.get("selector")
            value = action.get("value", "")

            if action_type == "click":
                await page.click(selector)
                results.append(f"클릭: {selector}")

            elif action_type == "fill":
                await page.fill(selector, value)
                results.append(f"입력: {selector} = {value}")

            elif action_type == "wait":
                await page.wait_for_timeout(int(value) * 1000)
                results.append(f"대기: {value}초")

            elif action_type == "screenshot":
                screenshot = await page.screenshot()
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(screenshot)
                    results.append(f"스크린샷: {f.name}")

        await browser.close()

        return ExecutionResult(
            command=f"web_automate({url})",
            stdout="\n".join(results),
            stderr="",
            returncode=0,
            success=True
        )

    except Exception as e:
        return ExecutionResult(
            command=f"web_automate({url})",
            stdout="",
            stderr=f"웹 자동화 오류: {str(e)}",
            returncode=1,
            success=False
        )

# =============================================================================
# Notion API 연동 도구
# =============================================================================

@mcp.tool()
async def notion_create_page(database_id: str, title: str, properties: str = "{}") -> NotionPageResult:
    """Notion 데이터베이스에 새 페이지 생성"""
    try:
        notion = init_notion()
        if not notion:
            raise Exception("Notion 토큰이 설정되지 않았습니다. NOTION_TOKEN 환경변수를 설정하세요.")

        import json
        props = json.loads(properties)

        # 기본 속성 설정
        page_properties = {
            "Name": {"title": [{"text": {"content": title}}]}
        }

        # 추가 속성 병합
        page_properties.update(props)

        response = notion.pages.create(
            parent={"database_id": database_id},
            properties=page_properties
        )

        return NotionPageResult(
            page_id=response["id"],
            url=response["url"],
            title=title,
            status="created"
        )

    except Exception as e:
        raise Exception(f"Notion 페이지 생성 오류: {str(e)}")

@mcp.tool()
async def notion_search(query: str, filter_type: str = "page") -> List[Dict]:
    """Notion에서 페이지 검색"""
    try:
        notion = init_notion()
        if not notion:
            raise Exception("Notion 토큰이 설정되지 않았습니다. NOTION_TOKEN 환경변수를 설정하세요.")

        response = notion.search(
            query=query,
            filter={
                "value": filter_type,
                "property": "object"
            }
        )

        results = []
        for item in response["results"][:10]:  # 최대 10개 결과
            results.append({
                "id": item["id"],
                "title": item.get("properties", {}).get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "제목 없음"),
                "url": item["url"],
                "last_edited": item["last_edited_time"]
            })

        return results

    except Exception as e:
        raise Exception(f"Notion 검색 오류: {str(e)}")

@mcp.tool()
async def web_to_notion(url: str, database_id: str, title_selector: str = "h1", content_selector: str = "p") -> NotionPageResult:
    """웹 크롤링 결과를 Notion에 저장"""
    try:
        # 웹 크롤링
        title_result = await web_scrape(url, title_selector)
        content_result = await web_scrape(url, content_selector)

        title = title_result.data[0] if title_result.data else f"웹페이지: {url}"
        content = "\n".join(content_result.data[:5])  # 최대 5개 문단

        # Notion 페이지 생성
        properties = json.dumps({
            "URL": {"url": url},
            "Content": {"rich_text": [{"text": {"content": content[:2000]}}]}  # 2000자 제한
        })

        result = await notion_create_page(database_id, title, properties)
        return result

    except Exception as e:
        raise Exception(f"웹→Notion 저장 오류: {str(e)}")

# =============================================================================
# 서버 실행
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    # 개발 모드: FastAPI + MCP 동시 실행
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        uvicorn.run(app, host="0.0.0.0", port=8020)
    else:
        # 프로덕션 모드: MCP 서버 실행
        # 현재는 HTTP 모드로 실행하여 헬스체크 지원
        uvicorn.run(app, host="0.0.0.0", port=8020)