// MCP (Model Context Protocol) 클라이언트
class MCPClient {
    constructor(baseUrl = 'http://localhost:8020') {
        this.baseUrl = baseUrl;
        this.requestId = 1;
    }

    // MCP 요청 전송 (커스텀 HTTP API)
    async sendRequest(method, params = {}) {
        try {
            let endpoint;
            let requestMethod;
            let body = null;

            if (method === 'tools/list') {
                endpoint = '/tools';
                requestMethod = 'GET';
            } else if (method === 'tools/call') {
                endpoint = `/tools/${params.name}/call`;
                requestMethod = 'POST';
                body = JSON.stringify(params.arguments || {});
            } else {
                throw new Error(`지원하지 않는 메서드: ${method}`);
            }

            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: requestMethod,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: body
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // tools/call의 경우 result를 반환
            if (method === 'tools/call') {
                if (data.success) {
                    return data.result;
                } else {
                    throw new Error(data.error || '도구 실행 실패');
                }
            }

            return data;
        } catch (error) {
            throw new Error(`MCP 요청 실패: ${error.message}`);
        }
    }

    // 사용 가능한 도구 목록 조회
    async listTools() {
        return await this.sendRequest('tools/list');
    }

    // 도구 실행
    async callTool(name, toolArguments) {
        return await this.sendRequest('tools/call', {
            name: name,
            arguments: toolArguments
        });
    }

    // 웹페이지 스크린샷
    async webScreenshot(url, width = 1280, height = 720) {
        return await this.callTool('web_screenshot', {
            url: url,
            width: width,
            height: height
        });
    }

    // 웹 콘텐츠 스크래핑
    async webScrape(url, selector = null) {
        return await this.callTool('web_scrape', {
            url: url,
            selector: selector
        });
    }

    // UI 분석
    async webAnalyzeUI(url) {
        return await this.callTool('web_analyze_ui', {
            url: url
        });
    }

    // Notion 페이지 생성
    async notionCreatePage(title, content, parentId = null) {
        return await this.callTool('notion_create_page', {
            title: title,
            content: content,
            parent_id: parentId
        });
    }

    // Notion 검색
    async notionSearch(query, pageSize = 10) {
        return await this.callTool('notion_search', {
            query: query,
            page_size: pageSize
        });
    }

    // 웹 콘텐츠를 Notion에 저장
    async webToNotion(url, title = null) {
        return await this.callTool('web_to_notion', {
            url: url,
            title: title
        });
    }

    // 파일 읽기
    async readFile(path) {
        return await this.callTool('read_file', {
            path: path
        });
    }

    // 파일 쓰기
    async writeFile(path, content) {
        return await this.callTool('write_file', {
            path: path,
            content: content
        });
    }

    // 시스템 명령 실행
    async runCommand(command, workingDir = null) {
        return await this.callTool('run_command', {
            command: command,
            working_directory: workingDir
        });
    }
}

// 전역에서 사용할 수 있도록 내보내기
window.MCPClient = MCPClient;