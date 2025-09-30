# AI Memory System 운영 가이드

## 개요

프로젝트별 장기 기억 시스템으로 SQLite 기반 로컬 저장과 Qdrant 벡터 검색을 결합한 하이브리드 메모리 아키텍처를 제공합니다.

## 시스템 구성

### 핵심 컴포넌트

1. **Memory System Core** (`scripts/memory_system.py`)
   - SQLite 데이터베이스 관리
   - FTS5 전문 검색
   - 프로젝트별 메모리 격리

2. **Memory Maintainer** (`scripts/memory_maintainer.py`)
   - TTL 기반 자동 정리 (기본: 14일)
   - 백업 생성 (매일 03:00)
   - Qdrant 동기화 (5분 간격)

3. **Memory API** (`services/api-gateway/memory_router.py`)
   - REST API 엔드포인트
   - OpenAPI 문서 자동 생성
   - 헬스체크 및 모니터링

4. **AI CLI 통합** (`scripts/ai.py`)
   - 자동 대화 저장
   - 메모리 검색 명령어
   - 로컬/API 폴백

## 디렉토리 구조

```
${DATA_DIR}/memory/
├── projects/
│   ├── {project-uuid}/
│   │   ├── memory.db              # SQLite 데이터베이스
│   │   └── project.json           # 프로젝트 메타데이터
│   └── docker-default/            # Docker 환경 기본 프로젝트
│       ├── memory.db
│       └── project.json
├── backups/
│   └── {project-uuid}/
│       └── memory_backup_{timestamp}.json
└── logs/
    ├── memory_maintainer.log
    └── sync_errors.log
```

## 환경 설정

### Docker 환경변수

```bash
# 메모리 시스템 설정
AI_MEMORY_DIR=/app/memory
DEFAULT_PROJECT_ID=my-project    # Docker 환경 프로젝트 ID

# 외부 서비스 연결
QDRANT_URL=http://qdrant:6333
EMBEDDING_URL=http://embedding:8003

# 유지보수 스케줄
MEMORY_BACKUP_CRON=03:00         # 백업 시간 (HH:MM)
MEMORY_SYNC_INTERVAL=300         # Qdrant 동기화 간격 (초)
TTL_CHECK_INTERVAL=3600          # TTL 확인 간격 (초)

# 스토리지 경로
DATA_DIR=/mnt/e/ai-data
```

### 로컬 환경

```bash
# 환경변수 설정
export AI_MEMORY_DIR="/mnt/e/ai-data/memory"
export QDRANT_URL="http://localhost:6333"
export EMBEDDING_URL="http://localhost:8003"
```

## 서비스 운영

### 서비스 시작

```bash
# 전체 시스템 시작
docker compose -f docker/compose.p3.yml up -d

# 메모리 관련 서비스만 시작
docker compose -f docker/compose.p3.yml up -d memory-api memory-maintainer qdrant
```

### 서비스 상태 확인

```bash
# 서비스 상태
docker compose -f docker/compose.p3.yml ps

# 메모리 API 헬스체크
curl http://localhost:8005/v1/memory/health

# 로그 확인
docker logs docker-memory-api-1
docker logs docker-memory-maintainer-1
```

### 포트 구성

| 서비스 | 포트 | 용도 |
|--------|------|------|
| memory-api | 8005 | REST API |
| qdrant | 6333 | 벡터 DB |
| embedding | 8003 | 임베딩 생성 |

## API 사용법

### 기본 엔드포인트

```bash
# 헬스체크
curl http://localhost:8005/v1/memory/health

# 대화 저장
curl -X POST http://localhost:8005/v1/memory/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "사용자 질문",
    "ai_response": "AI 응답",
    "model_used": "chat-7b",
    "session_id": "session-123",
    "token_count": 50,
    "response_time_ms": 1000
  }'

# 대화 검색
curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "검색어",
    "use_vector_search": false,
    "limit": 10
  }'

# 프로젝트 통계
curl http://localhost:8005/v1/memory/projects/{project_id}/stats
```

### 관리 작업

```bash
# Qdrant 동기화
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/sync \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "qdrant", "batch_size": 64}'

# 백업 생성
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/backup \
  -H "Content-Type: application/json" \
  -d '{"backup_type": "json"}'

# 만료된 대화 정리
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/cleanup

# 데이터베이스 최적화
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/optimize
```

## AI CLI 사용법

### 기본 명령어

```bash
# 일반 대화 (자동 메모리 저장)
ai "안녕하세요"

# 메모리 검색
ai --memory-search "이전 대화 내용"

# 메모리 상태 확인
ai --memory-status

# 메모리 통계
ai --memory-stats

# 메모리 정리
ai --memory-cleanup
```

### 고급 검색

```bash
# 벡터 검색 (의미적 유사성)
ai --memory-search "Python 함수" --vector

# 중요도 필터링
ai --memory-search "에러" --importance 5

# 최신 대화 제한
ai --memory-search "설정" --limit 5
```

## 문제 해결

### 일반적인 문제

1. **메모리 저장 실패**
   ```bash
   # 권한 확인
   docker exec docker-memory-api-1 ls -la /app/memory

   # 디렉토리 생성
   docker exec docker-memory-api-1 mkdir -p /app/memory/projects
   ```

2. **Qdrant 연결 실패**
   ```bash
   # Qdrant 상태 확인
   curl http://localhost:6333/collections

   # 네트워크 연결 테스트
   docker exec docker-memory-api-1 curl http://qdrant:6333/collections
   ```

3. **검색 결과 없음**
   ```bash
   # FTS5 인덱스 재구축
   curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/fts/rebuild

   # 데이터베이스 최적화
   curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/optimize
   ```

### 로그 분석

```bash
# 메모리 API 로그
docker logs docker-memory-api-1 --tail 100

# 유지보수 서비스 로그
docker logs docker-memory-maintainer-1 --tail 100

# 상세 디버그 로그 (환경변수 추가)
docker compose -f docker/compose.p3.yml up memory-api -e LOG_LEVEL=DEBUG
```

## 성능 최적화

### 데이터베이스 최적화

```bash
# 정기 최적화 (권장: 주 1회)
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/optimize

# FTS5 인덱스 재구축 (검색 성능 저하 시)
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/fts/rebuild
```

### 메모리 관리

```bash
# TTL 정리 (만료된 대화 삭제)
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/cleanup

# 백업 후 오래된 데이터 정리
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/backup
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/cleanup
```

## 보안 고려사항

### 접근 제어

- 메모리 API는 localhost에서만 접근 가능
- Docker 내부 네트워크를 통한 서비스 간 통신
- 민감한 정보는 환경변수로 관리

### 데이터 보호

- SQLite 데이터베이스는 파일 시스템 권한으로 보호
- 백업 파일은 읽기 전용으로 생성
- 로그에는 민감한 정보 기록 금지

## 환경별 설정

### Docker 환경 (운영)

- 중앙집중식 메모리 저장: `/app/memory/projects/docker-default`
- 환경변수 `DEFAULT_PROJECT_ID`로 프로젝트 구분
- 전역 파일시스템 마운트: `/mnt/host:ro`

### 로컬 환경 (개발)

- 프로젝트별 분산 저장: `{project_path}/.ai-memory`
- Git 저장소 기반 자동 프로젝트 감지
- 직접 파일시스템 접근

## 마이그레이션

### 기존 데이터 이전

```bash
# 로컬에서 Docker로
cp -r ~/.ai-memory/* /mnt/e/ai-data/memory/projects/

# 프로젝트 통합
python scripts/memory_system.py --migrate --source old_project --target new_project
```

## Qdrant 장애 시나리오 수동 검증 체크리스트

### 장애 상황별 검증 절차

#### 1. Qdrant 연결 실패 시나리오

**1.1 서비스 중단 시뮬레이션**
```bash
# Qdrant 서비스 중단
docker compose -f docker/compose.p3.yml stop qdrant

# 메모리 API 헬스체크 확인
curl http://localhost:8005/v1/memory/health
```

**예상 결과:**
- ✅ 메모리 API가 정상 응답 (200 OK)
- ✅ `vector_enabled: false` 상태 표시
- ✅ `storage_available: true` 유지

**1.2 FTS 전용 모드 동작 확인**
```bash
# 대화 저장 테스트
curl -X POST http://localhost:8005/v1/memory/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Qdrant 장애 테스트 질문",
    "ai_response": "FTS 전용 모드 응답",
    "model_used": "chat-7b"
  }'

# FTS 검색 테스트
curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qdrant 장애",
    "use_vector_search": false,
    "limit": 5
  }'
```

**예상 결과:**
- ✅ 대화 저장 성공 (conversation_id 반환)
- ✅ FTS 검색 정상 동작
- ✅ 벡터 검색 비활성화 메시지

**1.3 AI CLI 폴백 동작 확인**
```bash
# AI CLI로 대화 및 검색 테스트
ai "Qdrant 없이도 메모리가 작동하나요?"
ai --memory-search "Qdrant 장애"
ai --memory-status
```

**예상 결과:**
- ✅ 대화 자동 저장 성공
- ✅ 메모리 검색 정상 동작
- ✅ 벡터 기능 비활성화 상태 표시

#### 2. Qdrant 부분 장애 시나리오

**2.1 간헐적 연결 오류 시뮬레이션**
```bash
# iptables로 간헐적 연결 차단 (Linux)
sudo iptables -A OUTPUT -p tcp --dport 6333 -m statistic --mode random --probability 0.5 -j DROP

# 또는 Docker 네트워크 지연 추가
docker run --rm -d --name toxiproxy \
  -p 8474:8474 -p 6334:6334 \
  shopify/toxiproxy
```

**2.2 동기화 실패 복구 테스트**
```bash
# 실패한 동기화 재시도
curl -X POST http://localhost:8005/v1/memory/projects/{project_id}/sync/retry

# 동기화 대기열 확인
curl "http://localhost:8005/v1/memory/projects/{project_id}/sync/queue?include_failed=true"
```

**예상 결과:**
- ✅ 실패한 임베딩의 재시도 처리
- ✅ 실패 카운트 증가 기록
- ✅ 15분 후 자동 재시도 스케줄링

#### 3. Qdrant 복구 시나리오

**3.1 서비스 복구 후 자동 동기화**
```bash
# Qdrant 서비스 재시작
docker compose -f docker/compose.p3.yml start qdrant

# 복구 확인 (30초 대기 후)
sleep 30
curl http://localhost:8005/v1/memory/health
```

**예상 결과:**
- ✅ `vector_enabled: true` 복구
- ✅ 자동 컬렉션 재생성
- ✅ 대기 중인 임베딩 자동 동기화

**3.2 벡터 검색 복구 확인**
```bash
# 벡터 검색 테스트
curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python 함수 작성법",
    "use_vector_search": true,
    "limit": 5
  }'
```

**예상 결과:**
- ✅ 벡터 검색 정상 동작
- ✅ `search_type: "vector"` 응답
- ✅ 의미적 유사성 기반 결과

#### 4. 스트레스 테스트

**4.1 동시 요청 장애 처리**
```bash
# 다중 동시 요청 스크립트
#!/bin/bash
for i in {1..10}; do
  curl -X POST http://localhost:8005/v1/memory/conversations \
    -H "Content-Type: application/json" \
    -d "{\"user_query\": \"스트레스 테스트 $i\", \"ai_response\": \"응답 $i\"}" &
done
wait
```

**예상 결과:**
- ✅ 모든 요청 성공적 처리
- ✅ 데이터베이스 동시성 오류 없음
- ✅ 메모리 사용량 안정

**4.2 대량 데이터 장애 복구**
```bash
# 대량 데이터 준비
python3 << EOF
import requests
import json

for i in range(100):
    data = {
        "user_query": f"대량 테스트 질문 {i}",
        "ai_response": f"대량 테스트 응답 {i}",
        "model_used": "chat-7b"
    }
    requests.post("http://localhost:8005/v1/memory/conversations", json=data)
EOF

# Qdrant 중단 후 재시작
docker compose -f docker/compose.p3.yml stop qdrant
sleep 10
docker compose -f docker/compose.p3.yml start qdrant
```

**예상 결과:**
- ✅ 100개 대화 저장 성공
- ✅ 장애 중 FTS 검색 유지
- ✅ 복구 후 자동 벡터 동기화

### 자동화 테스트 실행

**테스트 스위트 실행**
```bash
# 전체 Qdrant 장애 테스트 실행
python tests/run_memory_tests.py

# 개별 테스트 실행
python tests/memory/test_qdrant_failure.py
```

**예상 테스트 결과:**
- ✅ `test_qdrant_connection_failure`: 연결 실패 폴백
- ✅ `test_qdrant_sync_failure_handling`: 동기화 실패 처리
- ✅ `test_maintainer_qdrant_failure_handling`: 유지보수 장애 처리
- ✅ `test_retry_mechanism`: 재시도 메커니즘
- ✅ `test_fts_fallback_search_quality`: FTS 폴백 검색 품질
- ✅ `test_database_corruption_recovery`: DB 손상 복구
- ✅ `test_concurrent_failure_handling`: 동시 장애 처리

### 장애 대응 체크리스트

#### 실시간 모니터링

**1. 헬스체크 모니터링**
```bash
# 5분마다 헬스체크 실행
watch -n 300 'curl -s http://localhost:8005/v1/memory/health | jq'
```

**2. 로그 모니터링**
```bash
# 실시간 에러 로그 감시
docker logs -f docker-memory-api-1 | grep -i "error\|fail"
docker logs -f docker-memory-maintainer-1 | grep -i "qdrant.*fail"
```

**3. 동기화 상태 모니터링**
```bash
# 동기화 대기열 크기 확인
curl -s "http://localhost:8005/v1/memory/projects/docker-default/sync/queue" | jq '.queue_size'
```

#### 알림 설정

**장애 감지 스크립트**
```bash
#!/bin/bash
# /opt/memory-monitor.sh

HEALTH_URL="http://localhost:8005/v1/memory/health"
ALERT_EMAIL="admin@example.com"

while true; do
    VECTOR_STATUS=$(curl -s $HEALTH_URL | jq -r '.vector_enabled')

    if [ "$VECTOR_STATUS" = "false" ]; then
        echo "$(date): Qdrant 장애 감지 - FTS 전용 모드 활성화" | \
          mail -s "메모리 시스템 장애 알림" $ALERT_EMAIL
        sleep 3600  # 1시간 대기
    else
        sleep 300   # 5분 대기
    fi
done
```

#### 복구 절차

**1. 장애 확인**
```bash
# Qdrant 상태 확인
curl http://localhost:6333/collections || echo "Qdrant 연결 실패"

# 메모리 시스템 상태 확인
curl http://localhost:8005/v1/memory/health | jq '.vector_enabled'
```

**2. 임시 조치**
```bash
# FTS 전용 모드 확인
curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "use_vector_search": false}'
```

**3. 복구 작업**
```bash
# Qdrant 재시작
docker compose -f docker/compose.p3.yml restart qdrant

# 복구 확인
sleep 30
curl http://localhost:8005/v1/memory/health | jq '.vector_enabled'

# 대기 중인 동기화 실행
curl -X POST http://localhost:8005/v1/memory/projects/docker-default/sync/retry
```

**4. 복구 검증**
```bash
# 벡터 검색 복구 확인
curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "use_vector_search": true}'

# 동기화 대기열 확인
curl "http://localhost:8005/v1/memory/projects/docker-default/sync/queue"
```

### 성능 영향 분석

#### FTS vs 벡터 검색 비교

**응답 시간 측정**
```bash
# FTS 검색 성능
time curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 함수", "use_vector_search": false}'

# 벡터 검색 성능 (복구 후)
time curl -X POST http://localhost:8005/v1/memory/conversations/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 함수", "use_vector_search": true}'
```

**예상 성능:**
- FTS 검색: 10-50ms (대화 1000개 기준)
- 벡터 검색: 50-200ms (대화 1000개 기준)
- 장애 시 성능 저하: 없음 (FTS 사용)

#### 리소스 사용량

**메모리 사용량**
```bash
# 컨테이너 리소스 모니터링
docker stats docker-memory-api-1 --no-stream
docker stats docker-qdrant-1 --no-stream  # 복구 후
```

**디스크 사용량**
```bash
# 데이터베이스 크기 확인
du -sh /mnt/e/ai-data/memory/projects/*/memory.db

# Qdrant 데이터 크기 확인 (복구 후)
du -sh /mnt/e/ai-data/vectors/qdrant/
```

이 체크리스트를 통해 Qdrant 장애 상황에서도 메모리 시스템이 안정적으로 FTS-only 모드로 동작하고, 장애 해제 시 자동 복구되는지 체계적으로 검증할 수 있습니다.

## 모니터링

### 메트릭 수집

- 대화 저장 성공/실패율
- 검색 응답 시간
- 데이터베이스 크기
- TTL 정리 통계
- Qdrant 동기화 성공/실패율
- 벡터 검색 vs FTS 검색 비율

### 알림 설정

- 백업 실패
- Qdrant 동기화 오류
- 디스크 용량 부족
- API 응답 시간 지연
- 벡터 기능 비활성화 감지
- 임베딩 동기화 실패 임계치 초과