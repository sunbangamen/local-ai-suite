# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local AI Suite is a comprehensive local AI system designed to run entirely offline on external SSDs with GPU acceleration. It provides a phase-by-phase deployment approach for running local LLM models with OpenAI-compatible APIs, RAG (Retrieval-Augmented Generation), and MCP (Model Context Protocol) server capabilities.

**Key Goals:**
- Complete offline AI system for portability across different PCs
- RTX 4050 + WSL2 optimized GPU acceleration
- OpenAI API compatibility for VS Code/Cursor integration
- Korean language support with coding-specific model selection

## Architecture Overview

### Phase-Based Deployment

The system implements a progressive deployment strategy:

**Phase 1 (Basic AI Serving):**
- llama.cpp inference server (port 8001) - Direct model serving
- LiteLLM API gateway (port 8000) - OpenAI compatibility layer
- Automatic model selection between chat and code models

**Phase 2 (RAG System):**
- FastEmbed embedding service (port 8003) - PyTorch-free embedding generation
- Qdrant vector database (port 6333) - High-performance vector storage
- PostgreSQL database (port 5432) - Metadata and search logs
- RAG service (port 8002) - Document indexing and query processing
- Korean document support with contextual answers

**Phase 3 (MCP Integration):**
- MCP server (port 8020) - FastMCP framework with 14 tools
- Playwright web automation (4 tools) - Screenshots, scraping, UI analysis
- Notion API integration (3 tools) - Page creation, search, web-to-notion
- File system and Git integration for Claude Desktop

**Phase 4 (Desktop Application):**
- Electron-based Claude Desktop-style app
- Smart model selection (auto/manual modes)
- Markdown code block rendering with copy functionality
- Web/Electron environment compatibility

### Core Components

**Model Management:**
- GGUF format models in `models/` directory
- Automatic model selection based on query content analysis
- Supports both general chat and coding-specific models

**Service Architecture:**
- Docker Compose orchestration with health checks
- GPU passthrough for NVIDIA RTX 4050
- Service dependencies and startup ordering
- Environment-based configuration

**AI CLI Interface:**
- Intelligent model selection based on keywords and patterns
- Interactive and batch modes
- Token length control and timeout handling

## Common Development Commands

### Service Management
```bash
# Start Phase 1 (Basic AI)
make up-p1

# Start Phase 2 (Full RAG System)
make up-p2

# Start Phase 3 (Future MCP integration)
make up-p3

# Stop all services
make down

# View logs
make logs
```

### Testing and Validation
```bash
# Test inference server directly
curl http://localhost:8001/v1/models
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# Test API Gateway (OpenAI compatibility)
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-14b-instruct", "messages": [{"role": "user", "content": "Hello"}]}'

# Test RAG system
curl -X POST http://localhost:8002/index \
  -H "Content-Type: application/json" \
  -d '{"collection": "default"}'

curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python에서 파일을 읽는 방법", "collection": "default"}'

# Test AI CLI
python scripts/ai.py "Hello world"
python scripts/ai.py --code "Create a Python function"
python scripts/ai.py --interactive

# Test MCP Server (Phase 3)
curl http://localhost:8020/health

# Test Desktop App (Phase 4)
cd desktop-app && npm run dev  # Electron app
python3 -m http.server 3000 --directory desktop-app/src  # Web version
```

### Health Checks
```bash
# Check all services
curl http://localhost:8001/health  # Inference
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8003/health  # Embedding
curl http://localhost:8002/health  # RAG
curl http://localhost:6333/collections  # Qdrant
curl http://localhost:8020/health  # MCP Server
```

## Key Technical Details

### Model Configuration
- Models stored in `models/` directory as GGUF files
- Environment variables in `.env` specify model filenames
- **RTX 4050 6GB Optimized Settings (7B Models):**
  - GPU layers: 999 (auto-maximum)
  - Context size: 1024 tokens (speed optimized)
  - Parallel processing: 1
  - Batch size: 128
  - CPU threads: 4 (limited)
  - CPU limit: 4.0 cores (Docker)
- **Available Models:**
  - 7B models (optimized): 4.4GB each
  - 14B models (high-performance): 8.4GB each

### Data Architecture (1TB External SSD)
**Unified Structure:**
```
/mnt/e/
├── ai-models/          # AI models (8GB+)
├── ai-data/           # All persistent data
│   ├── postgresql/    # Metadata DB
│   ├── vectors/       # Vector storage (Qdrant)
│   ├── documents/     # Original documents
│   ├── cache/         # Processing cache
│   └── logs/          # System logs
└── worktree/         # Temporary Git worktrees
```

**PostgreSQL Schema:**
- **RAG Tables**: collections, documents, chunks, search_logs
- **MCP Tables**: mcp_requests, notion_pages, web_scrapes
- **System Tables**: system_settings, user_preferences

**Data Separation Strategy:**
- Worktrees: Temporary code (deleted after merge)
- Shared Data: Models, DB, vectors, documents (permanent)
- Scalability: Independent component management

### RAG Implementation (ChatGPT Optimized)
- **FastEmbed**: PyTorch-free embedding using ONNX runtime
- **Model**: BAAI/bge-small-en-v1.5 (384 dimensions)
- **Korean Sentence Splitter**: Regex-based sentence boundary detection
- **Smart Chunking**: Sliding window with overlap (512 tokens/100 overlap)
- **Context Budget Management**: 1200 token limit for 7B models
- **Batch Processing**: 64-item embedding batches
- **Safety Limits**: Max 1024 texts, 8000 chars per item
- **Vector Search**: Cosine similarity in Qdrant
- **LLM Integration**: Environment-tunable timeouts and token limits
- **Prewarm Support**: Cold start prevention endpoints

### AI CLI Features
- **Automatic Detection**: Analyzes query content for model selection
- **Keywords**: Coding terms trigger code model, others use chat model
- **Manual Override**: `--code` and `--chat` flags for explicit control
- **Interactive Mode**: Persistent session with command prefixes
- **Token Control**: `--tokens` parameter for response length

### Docker Architecture
- **Health Checks**: wget-based for API Gateway, disabled for Qdrant
- **Dependencies**: Proper service startup ordering
- **GPU Access**: NVIDIA runtime with device passthrough
- **Networking**: Internal container communication with external ports
- **Volumes**: Model caching and document persistence

## Development Patterns

### Adding New Services
1. Create service directory under `services/`
2. Add Dockerfile and requirements.txt
3. Update appropriate `compose.p*.yml` file
4. Configure health checks and dependencies
5. Add environment variables to `.env`

### Modifying RAG Pipeline
- **Embedding Service**: `services/embedding/app.py` - FastAPI service
- **RAG Service**: `services/rag/app.py` - Document processing and querying
- **Vector DB**: Qdrant configuration in Docker Compose
- **Documents**: Place in `documents/` directory for indexing

### AI CLI Extensions
- **Model Detection**: Update `CODE_KEYWORDS` in `scripts/ai.py`
- **API Integration**: Modify `API_URL` and model selection logic
- **Interactive Commands**: Extend command parsing in interactive mode

### MCP Server Tools (Phase 3)
**File System Tools:**
- `list_files`: Directory file listing
- `read_file`: File content reading
- `write_file`: File writing
- `create_directory`: Directory creation
- `search_files`: File searching
- `run_command`: System command execution
- `get_system_info`: System information

**Playwright Web Tools:**
- `web_screenshot`: Web page screenshots
- `web_scrape`: Web content extraction
- `web_analyze_ui`: UI/design analysis
- `web_automate`: Web automation tasks

**Notion Integration Tools:**
- `notion_create_page`: Create Notion pages
- `notion_search`: Search Notion workspace
- `web_to_notion`: Save web content to Notion

### Desktop Application Features (Phase 4)
**Smart Model Selection:**
- Auto mode: Intelligent keyword detection for Chat/Code model selection
- Manual mode: User-controlled model selection
- Real-time model status display

**UI/UX Features:**
- Claude Desktop-style dark theme
- Markdown code block rendering with syntax highlighting
- Copy-to-clipboard functionality for code blocks
- Responsive chat interface

**Development Environment:**
- WSL2 development with web browser testing
- Electron app for Windows deployment
- Web/Electron environment compatibility

## Environment Configuration

### Required Environment Variables
```bash
# Service Ports
API_GATEWAY_PORT=8000
INFERENCE_PORT=8001
RAG_PORT=8002
EMBEDDING_PORT=8003
MCP_PORT=8020
POSTGRES_PORT=5432

# Model Files (optimized for 7B)
CHAT_MODEL=Qwen2.5-7B-Instruct-Q4_K_M.gguf
CODE_MODEL=qwen2.5-coder-7b-instruct-q4_k_m.gguf

# Data Paths (external SSD)
MODELS_DIR=/mnt/e/ai-models
DATA_DIR=/mnt/e/ai-data

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_DB=ai_suite
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=ai_secure_pass

# RAG Configuration
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
QDRANT_URL=http://qdrant:6333
EMBEDDING_URL=http://embedding:8003
```

### Model Requirements
- Place GGUF model files in `models/` directory
- Ensure adequate disk space (8GB+ per model)
- GPU memory: 8GB+ recommended for 14B parameter models
- CPU fallback available if GPU unavailable

## Troubleshooting

### Common Issues
- **Port Conflicts**: Check if ports 8000-8003, 6333 are available
- **GPU Access**: Verify NVIDIA Docker runtime and drivers
- **Model Loading**: Check model file paths and permissions
- **Health Checks**: Some containers use wget instead of curl
- **Service Dependencies**: Allow startup time for dependent services

### Health Check Problems
- **API Gateway**: Uses wget with GET requests (not HEAD)
- **Qdrant**: Health checks disabled due to missing HTTP clients
- **Service Status**: Check `docker-compose ps` for actual functionality vs health status

### Performance Optimization
- **GPU Layers**: Adjust `--n-gpu-layers` based on GPU memory
- **Context Size**: Modify `--ctx-size` for longer conversations
- **Parallel Processing**: Tune `--parallel` for throughput
- **Embedding Cache**: FastEmbed models cached in Docker volumes

## Integration Points

### VS Code/Cursor Setup
Configure OpenAI-compatible endpoint:
- **Base URL**: `http://localhost:8000/v1`
- **Model**: `qwen2.5-14b-instruct` or `gpt-3.5-turbo`
- **API Key**: Not required (local deployment)

### External Applications
- **OpenAI API Compatible**: Any application supporting OpenAI API format
- **RAG Endpoints**: Custom API for document-based queries
- **Local Network**: Services bind to localhost only for security

## Current Implementation Status (2025-09-30)

### ✅ Completed Features (100% Ready for Development Use)

**Phase 1-3: Core AI System**
- ✅ **Dual-Model System**: Intelligent chat-7b/code-7b model selection across all components
- ✅ **7B Model Optimization**: RTX 4050 6GB optimized with 99% CPU usage improvement
- ✅ **MCP Integration Complete**: 18 tools total (14 original + 4 new Git tools)
- ✅ **Global AI CLI**: `install.sh` script for system-wide `ai` command access
- ✅ **Git Worktree Support**: Complete Git workflow in containerized environment
- ✅ **RAG System**: Korean language support with optimized performance
- ✅ **API Compatibility**: Full OpenAI API compatibility for VS Code/Cursor
- ✅ **Global Filesystem Access**: Complete filesystem access from any directory
- ✅ **Configuration Issues Resolved**: All model naming conflicts and 400 errors fixed

**New MCP Git Tools:**
```bash
ai --mcp git_diff --mcp-args '{"file_path": "app.py"}'        # Show changes
ai --mcp git_log --mcp-args '{"max_count": 5}'               # Commit history
ai --mcp git_add --mcp-args '{"file_paths": "app.py"}'       # Stage files
ai --mcp git_commit --mcp-args '{"message": "fix: bug"}'     # Create commits
```

**Global CLI Usage:**
```bash
# Install globally
./install.sh && export PATH="$HOME/.local/bin:$PATH"

# Use from anywhere on the filesystem
cd /any/directory
ai "Hello world"
ai --mcp git_status
ai --mcp read_file --mcp-args '{"file_path": "./local-file.txt"}'
ai --mcp write_file --mcp-args '{"file_path": "./output.txt", "content": "test"}'
ai --interactive
```

**Global Filesystem Access Features:**
- **Docker Volume Mapping**: Full host filesystem mounted as `/mnt/host` in containers
- **Dynamic Path Resolution**: `resolve_path()` function automatically maps working directories
- **MCP Tools**: All 18 tools work from any directory with `working_dir` parameter
- **Git Integration**: Git commands work correctly in any repository, not just project worktrees
- **RAG System**: Document indexing and querying from any filesystem location

### 🚨 Critical Issues Requiring Immediate Attention

#### **Security Vulnerabilities (HIGH PRIORITY) - 🔄 Issue #8 In Progress**
- ✅ **AST 기반 코드 검증**: 위험 모듈/함수 차단 완료 (security.py)
- ✅ **Docker 샌드박스**: 컨테이너 격리 실행 완료 (sandbox.py)
- ✅ **Rate Limiting**: 도구별 요청 제한 완료 (rate_limiter.py)
- ✅ **안전한 파일 API**: 경로 탐색 방지 완료 (safe_api.py)
- ❌ **RBAC 시스템**: 역할 기반 접근 제어 미구현 (진행 중)
- ❌ **감사 로깅 DB**: SQLite 기반 구조화 로깅 미구현 (진행 중)
- ❌ **승인 워크플로우**: HIGH/CRITICAL 도구 승인 메커니즘 미구현

#### **Service Reliability (HIGH PRIORITY)**
- **Single Point of Failure**: API Gateway failure affects entire system
- **Error Recovery**: No automatic recovery mechanisms for service failures
- **PostgreSQL Integration**: WSL permission issues causing restart loops
- **Timeout Inconsistency**: Different timeout settings across services

#### **Implementation Gaps (MEDIUM PRIORITY)**
- **Phase 4 Desktop App**: Basic UI only, smart model selection incomplete
- **Monitoring**: No centralized logging, metrics, or alerting
- **Testing**: Complete absence of unit/integration tests
- **Performance**: No caching, sequential MCP tool execution only

### 🎯 Improvement Roadmap

#### **Week 1-3: Security & Stability (Issue #8 - In Progress)**

**현재 상태 (2025-09-30):**
- 📋 **Issue #8 계획 수립 완료**: `docs/progress/v1/ri_4.md` 작성
- 📐 **아키텍처 설계**: SQLite RBAC + Docker Sandbox 강화 방식 선정
- 🎯 **목표**: 16일 + 4일 버퍼 = 약 3주 완료 예정

**구현 계획 (4 Phases):**

**Phase 0: 환경 및 설계 정리 (Day 0)**
- 환경 변수 정의 (`RBAC_ENABLED`, `SECURITY_DB_PATH`)
- 테스트 구조 확정 및 마커 추가
- ERD/시퀀스 다이어그램 작성
- SQLite vs PostgreSQL ADR 문서화

**Phase 1: SQLite RBAC 데이터베이스 구축 (Day 1-3)**
- SQLite 스키마 설계 (6개 테이블: users, roles, permissions, role_permissions, audit_logs, sessions)
- DB Manager 모듈 개발 (CRUD + 연결 풀링)
- WAL 모드 동시 접근 테스트 (10+ 연결)
- 백업 스크립트 및 초기 데이터 시딩

**Phase 2: RBAC 미들웨어 및 권한 검증 (Day 4-7)**
- RBAC Manager 모듈 (역할-권한 매핑)
- FastAPI 미들웨어 구현 (모든 `/tools/*` 자동 검증)
- 18개 도구 권한 정책 매핑
- HTTP 403 응답 표준화

**Phase 3: 감사 로깅 및 샌드박스 통합 (Day 8-12)**
- 비동기 감사 로깅 (<5ms 목표)
- 샌드박스 DB 로깅 통합
- 로그 조회 API (`/security/logs`)
- 실시간 알림 시스템 (선택)

**Phase 4: 테스트 및 문서화 (Day 13-16)**
- 샌드박스 탈출 테스트 (50+ 케이스)
- 권한 우회 테스트 (30+ 케이스)
- 성능 벤치마크 (<100ms 샌드박스, <10ms RBAC)
- SECURITY.md, RBAC_GUIDE.md 작성

**완료 기준 (DoD):**
- [ ] 80+ 보안 테스트 통과
- [ ] 성능 목표 달성 (p95 <500ms)
- [ ] Feature flag (`RBAC_ENABLED`) 동작 확인
- [ ] 보안 문서 작성 완료

**참고 문서:**
- 상세 계획: `docs/progress/v1/ri_4.md`
- GitHub Issue: #8

---

#### **Month 1: Feature Completion (Deferred)**
1. **PostgreSQL Migration (선택적)**
   - SQLite 동시성 제한 시 PostgreSQL 전환
   - 스키마 마이그레이션 스크립트

2. **Desktop Application**
   - Complete smart model selection implementation
   - Add advanced UI features (code highlighting, copy functionality)
   - Implement user preferences and settings persistence

3. **Performance Optimization**
   - Add caching layer for API responses and embeddings
   - Implement parallel MCP tool execution
   - Optimize model loading and memory management

4. **Testing Infrastructure**
   - Unit tests for core MCP tools
   - Integration tests for service communication
   - End-to-end tests for complete workflows

#### **Month 3: Production Readiness**
1. **Advanced Security**
   - Complete security audit and penetration testing
   - Implement comprehensive access controls
   - Add encryption for data at rest and in transit

2. **Scalability & Reliability**
   - Add load balancing and horizontal scaling support
   - Implement circuit breakers and retry mechanisms
   - Create backup/recovery procedures

3. **Operational Excellence**
   - Complete observability stack (metrics, logs, traces)
   - Automated deployment pipelines (CI/CD)
   - Comprehensive documentation and runbooks

### 💡 Project Assessment

**Strengths:**
- Complete offline AI ecosystem with GPU acceleration
- Excellent developer experience with worktree support
- High extensibility through MCP framework
- Strong Korean language and coding specialization
- Convenient global CLI access

**Critical Weaknesses:**
- **Security**: Major vulnerabilities for production use
- **Reliability**: Limited fault tolerance and error recovery
- **Observability**: Minimal monitoring and debugging capabilities
- **Testing**: No automated testing infrastructure

**Suitability by Environment:**
- **Personal Development**: ⭐⭐⭐⭐⭐ Excellent (100% ready)
- **Team Development**: ⭐⭐⭐⭐☆ Very Good (90% ready, needs monitoring)
- **Production Use**: ⭐⭐⭐☆☆ Improving (70% ready, RBAC/감사 로깅 구현 중)

**최근 업데이트 (2025-09-30):**
- Issue #8 보안 강화 작업 계획 수립 완료
- 기존 보안 기능 분석: AST 검증, Docker 샌드박스, Rate Limiting 구현 확인
- SQLite RBAC + 감사 로깅 아키텍처 설계 완료
- 3주 일정으로 RBAC 시스템 및 구조화된 감사 로깅 구축 예정

### 🔧 Quick Start Commands

```bash
# Global installation
./install.sh
export PATH="$HOME/.local/bin:$PATH"

# Start full system
docker compose -f docker/compose.p3.yml up -d

# Verify all services
curl http://localhost:8001/health  # Inference
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8002/health  # RAG
curl http://localhost:8020/health  # MCP Server

# Use global AI CLI
ai "Hello world"
ai --mcp git_status
ai --mcp-list  # Show all 18 available tools
```

This architecture enables completely offline AI capabilities while maintaining compatibility with existing AI-powered development tools, though security and reliability improvements are essential for production deployment.