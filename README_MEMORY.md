# 🧠 AI Memory System - Quick Start Guide

프로젝트별 무제한 대화 저장 및 스마트 검색 시스템

## 🚀 빠른 시작

### 1. 시스템 시작

```bash
# 전체 스택 시작 (메모리 시스템 포함)
docker compose -f docker/compose.p3.yml up -d

# 서비스 상태 확인
docker compose -f docker/compose.p3.yml ps

# 헬스체크
curl http://localhost:8005/health  # Memory API
curl http://localhost:6333/        # Qdrant
curl http://localhost:8003/health  # Embedding
```

### 2. AI CLI로 메모리 사용

```bash
# 일반 대화 (자동으로 메모리에 저장됨)
ai "Python에서 파일 읽는 방법 알려줘"
# 💾 Conversation saved (ID: 1, Importance: 6/10)

# 메모리 상태 확인
ai --memory
# 💾 Memory System Status (Local)
#    Project ID: abc123...
#    Total Conversations: 1
#    Average Importance: 6.0

# 메모리 검색
ai --memory-search "파일 읽기"
# 🔍 Found 1 conversations

# 메모리 통계
ai --memory-stats
# 📊 Total: 1, Avg Importance: 6.0/10

# 만료된 대화 정리
ai --memory-cleanup
# 🧹 Cleanup completed: 0 conversations removed
```

### 3. Desktop App에서 사용

1. Desktop App 시작:
   ```bash
   cd desktop-app
   npm install
   npm start
   ```

2. 메모리 기능:
   - **자동 저장**: 모든 대화가 자동으로 저장됨
   - **검색**: 상단 메뉴에서 "Memory Search" 클릭
   - **통계**: "Memory Stats" 탭에서 확인

### 4. Python에서 직접 사용

```python
from memory_system import get_memory_system

# 메모리 시스템 가져오기
memory = get_memory_system()
project_id = memory.get_project_id()

# 대화 저장
conv_id = memory.save_conversation(
    project_id=project_id,
    user_query="Python 함수 만들기",
    ai_response="def example(): pass",
    model_used="code-7b"
)
print(f"Saved: {conv_id}")

# 대화 검색
results = memory.search_conversations(
    project_id=project_id,
    query="Python 함수",
    limit=10
)
print(f"Found: {len(results)} conversations")
```

## 📊 주요 기능

### ✅ 구현 완료

| 기능 | 설명 | 상태 |
|------|------|------|
| 프로젝트별 저장 | UUID 기반 프로젝트 격리 | ✅ |
| 자동 중요도 판정 | 1-10단계 자동 점수 | ✅ |
| TTL 자동 정리 | 중요도별 차등 보관 | ✅ |
| FTS5 전문 검색 | 1초 내 빠른 검색 | ✅ |
| 벡터 유사도 검색 | Qdrant + FastEmbed | ✅ |
| 하이브리드 검색 | FTS5 + 벡터 결합 | ✅ |
| REST API | OpenAI 호환 API | ✅ |
| AI CLI 통합 | 명령어 6종 지원 | ✅ |
| Desktop App UI | 검색/통계 UI | ✅ |
| 자동 백업 | 일일 SQL/JSON 백업 | ✅ |

## 🎯 성능 지표

- **100만개 대화 처리**: SQLite WAL + 인덱스 최적화
- **1초 내 검색**: FTS5 BM25 알고리즘
- **벡터 검색**: 384차원 FastEmbed + Qdrant
- **자동 정리**: 1시간마다 TTL 기반
- **일일 백업**: 새벽 3시 자동 실행

## 📖 자세한 문서

- [전체 문서](./docs/MEMORY_SYSTEM.md)
- [구현 계획](./docs/progress/v1/ri_3.md)
- [통합 테스트](./tests/test_memory_integration.py)

## 🔧 환경 변수

```bash
# Memory API
AI_MEMORY_DIR=/mnt/e/ai-data/memory
MEMORY_SERVICE_PORT=8005

# Memory Maintainer
MEMORY_BACKUP_CRON=03:00
MEMORY_SYNC_INTERVAL=300
TTL_CHECK_INTERVAL=3600
```

## 🧪 테스트

```bash
# 통합 테스트 실행
python tests/test_memory_integration.py

# 수동 테스트
ai --memory-init           # 프로젝트 초기화
ai "테스트 메시지"         # 대화 저장
ai --memory-search "테스트" # 검색
ai --memory-stats          # 통계
ai --memory-cleanup        # 정리
```

## 🛠 트러블슈팅

### Memory API 연결 실패

```bash
# 서비스 로그 확인
docker compose -f docker/compose.p3.yml logs memory-api

# 수동 시작
docker compose -f docker/compose.p3.yml up -d memory-api

# 헬스체크
curl http://localhost:8005/health
```

### 벡터 검색 비활성화

```bash
# Qdrant 확인
docker compose -f docker/compose.p3.yml logs qdrant
curl http://localhost:6333/

# 수동 벡터 복구
python3 -c "from memory_system import get_memory_system; get_memory_system().try_vector_recovery()"
```

### 백업 복원

```bash
# SQL 백업에서 복원
sqlite3 /mnt/e/ai-data/memory/projects/{project-id}/memory.db < backup.sql
```

## 📝 중요도 점수 가이드

| 점수 | 보관 기간 | 예시 |
|------|----------|------|
| 10 | 영구 | 사용자가 명시적으로 중요 표시 |
| 9 | 1년 | 핵심 아키텍처 결정 |
| 8 | 6개월 | 중요 설계 패턴 |
| 7 | 3개월 | 프로젝트 설정 |
| 6 | 1개월 | 코드 구현 |
| 5 | 30일 | 일반 대화 (기본값) |
| 4 | 2주 | 정보성 질문 |
| 3 | 1주 | 단순 대화 |
| 2 | 3일 | 간단한 질문 |
| 1 | 즉시 | 인사, 테스트 |

## 🤝 기여

Issue #5 구현
- 날짜: 2025-09-30
- 개발: @sunbangamen

## 📄 라이선스

MIT License