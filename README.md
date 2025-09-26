# Local AI Suite (Phase-by-Phase)

외장 SSD + RTX 4050에서 **클로드 데스크탑/코드/커서 느낌**을 로컬 모델 + RAG + MCP로 구현하는 스캐폴드.

## Quick Start

### 0) 사전 준비
- Docker Desktop + WSL 통합(Windows)
- 외장 SSD에 이 리포지토리 클론 후 `models/` 폴더 생성
- 7B GGUF 모델 파일을 `models/`에 배치(예: llama3.1-8b-instruct-q4_k_m.gguf, qwen2.5-coder-7b-q4_k_m.gguf)

### 1) Phase 1: 최소 동작 (모델 + OpenAI 호환 게이트웨이)
```bash
make up-p1
# 확인
curl http://localhost:8000/v1/models
```

* VS Code/Cursor에서 OpenAI 호환 엔드포인트를 `http://localhost:8000/v1` 로 설정

### 2) Phase 2: RAG + Qdrant + reranker 추가

```bash
make up-p2
# 문서 인덱싱
curl -X POST "http://localhost:8002/index?collection=myproj"
# 질의
curl -H "Content-Type: application/json" \
     -d '{"query":"테스트 실패 원인 정리","collection":"myproj"}' \
     http://localhost:8002/query
```

### 3) Phase 3: MCP 서버

```bash
make up-p3
# MCP(파일/깃/셸) 엔드포인트 확인
curl http://localhost:8020/health
```

### 보안 기능 세부사항

**차단되는 위험한 코드:**
```python
import subprocess  # ❌ 차단
import ctypes      # ❌ 차단
import socket      # ❌ 차단
importlib.import_module('subprocess')  # ❌ 우회 차단
```

**허용되는 안전한 코드:**
```python
import os          # ✅ 허용
import sys         # ✅ 허용
import pathlib     # ✅ 허용
import json        # ✅ 허용
```

**차단되는 위험한 경로:**
```bash
/etc/passwd                    # ❌ 차단
C:/Windows/System32/config/SAM  # ❌ 차단 (슬래시)
C:\Windows\System32            # ❌ 차단 (백슬래시)
../../../etc/shadow            # ❌ 경로 탈출 차단
```

## 폴더 요약

* `docker/compose.p1.yml` : 추론서버 + API 게이트웨이(litellm)
* `docker/compose.p2.yml` : + Qdrant + RAG(FastAPI) + reranker
* `docker/compose.p3.yml` : + MCP 서버(fs/git/shell)

## 보안

* 모든 서비스는 로컬호스트만 노출 권장.
* 외부 포트 개방 금지. 토큰/키 필요 없음(완전 로컬 전제).

### 보안 테스트 실행

MCP 서버의 보안 시스템을 검증하려면 자동화된 테스트를 실행할 수 있습니다:

```bash
# pytest 설치 (한 번만)
pip install pytest

# 보안 테스트 실행
pytest tests/security_tests.py -q

# 또는 직접 기본 보안 테스트 실행
python3 tests/security_tests.py
```

**테스트 항목:**
- ✅ AST 기반 코드 보안 검증
- ✅ 동적 import 우회 시도 차단 (`importlib.import_module` 등)
- ✅ 절대 경로 매핑 보안 (경로 탈출 방지)
- ✅ Windows/Linux 멀티플랫폼 경로 보안
- ✅ 슬래시/백슬래시 혼합 경로 차단
- ✅ 시스템 파일 및 민감 디렉터리 접근 방지

**기대 결과:** 모든 보안 테스트가 통과해야 하며, 실패 시 보안 취약점이 있음을 의미합니다.

## 트러블슈팅

* 모델 경로/파일명 오타 → `docker logs`에서 확인
* GPU 인식 안될 때 → Docker Desktop에서 WSL GPU 지원/드라이버 확인
* RAG 품질이 낮을 때 → bge-m3 임베딩, bge-reranker 설정 확인