# Service Reliability Operations Guide

**작성일**: 2025-10-09
**대상**: Phase 2 운영자
**목적**: Issue #14 Service Reliability 개선 사항 운영 가이드

---

## 📋 개요

이 문서는 Phase 2 이중화 구조의 운영 절차, 장애 대응, 모니터링 방법을 설명합니다.

### 주요 개선 사항

- ✅ **LLM 서버 이중화**: inference-chat (3B) + inference-code (7B)
- ✅ **자동 페일오버**: LiteLLM priority 기반 재시도
- ✅ **헬스체크 강화**: 모든 서비스에 `/health` 엔드포인트 추가
- ✅ **의존성 관리**: `depends_on: service_healthy` 조건 적용
- ✅ **재시도 메커니즘**: Qdrant 호출에 exponential backoff 재시도

---

## 🚀 서비스 시작 및 중지

### Phase 2 시작

```bash
# 전체 서비스 시작
docker compose -f docker/compose.p2.yml up -d

# 서비스 상태 확인
docker compose -f docker/compose.p2.yml ps

# 로그 확인
docker compose -f docker/compose.p2.yml logs -f
```

### 개별 서비스 재시작

```bash
# Chat 모델 서버만 재시작
docker compose -f docker/compose.p2.yml restart inference-chat

# Code 모델 서버만 재시작
docker compose -f docker/compose.p2.yml restart inference-code

# API Gateway 재시작
docker compose -f docker/compose.p2.yml restart api-gateway

# RAG 서비스 재시작
docker compose -f docker/compose.p2.yml restart rag
```

### 서비스 중지

```bash
# 전체 중지
docker compose -f docker/compose.p2.yml down

# 특정 서비스만 중지
docker compose -f docker/compose.p2.yml stop inference-chat
```

---

## 🔍 모니터링 및 헬스체크

### 헬스체크 엔드포인트

| 서비스 | URL | 정상 응답 |
|--------|-----|----------|
| **inference-chat** | http://localhost:8001/health | 200 OK |
| **inference-code** | http://localhost:8004/health | 200 OK |
| **api-gateway** | http://localhost:8000/health | 200 OK |
| **rag** | http://localhost:8002/health | 200 OK (의존성 healthy) |
| **embedding** | http://localhost:8003/health | 200 OK |
| **qdrant** | http://localhost:6333/collections | 200 OK |

### 헬스체크 스크립트

```bash
#!/bin/bash
# health_check.sh

echo "=== Phase 2 Health Check ==="

services=(
  "inference-chat:8001"
  "inference-code:8004"
  "api-gateway:8000"
  "rag:8002"
  "embedding:8003"
)

for service in "${services[@]}"; do
  name="${service%%:*}"
  port="${service##*:}"

  if curl -fsS "http://localhost:$port/health" > /dev/null 2>&1; then
    echo "✅ $name: healthy"
  else
    echo "❌ $name: unhealthy"
  fi
done

# Qdrant 특별 체크
if curl -fsS "http://localhost:6333/collections" > /dev/null 2>&1; then
  echo "✅ qdrant: healthy"
else
  echo "❌ qdrant: unhealthy"
fi
```

### Docker 헬스 상태 확인

```bash
# 전체 서비스 상태
docker compose -f docker/compose.p2.yml ps

# 헬스체크 세부 정보
docker inspect <container_id> | jq '.[0].State.Health'

# Unhealthy 컨테이너 찾기
docker ps --filter "health=unhealthy"
```

### GPU 메모리 모니터링

```bash
# 실시간 모니터링
watch -n 1 nvidia-smi

# VRAM 사용량만 확인
nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 1

# 컨테이너별 GPU 사용량 (프로세스 ID로 추적)
nvidia-smi pmon -s um
```

---

## 🚨 장애 대응 가이드

### Scenario 1: inference-chat 장애

**증상**:
- `docker ps`에서 inference-chat이 unhealthy 또는 exited 상태
- Chat 요청이 자동으로 inference-code로 failover됨

**확인**:
```bash
# 컨테이너 상태
docker ps -a | grep inference-chat

# 로그 확인
docker logs inference-chat --tail 100

# GPU 메모리 확인
nvidia-smi
```

**대응**:
1. **자동 재시작 대기** (Docker가 자동 재시작 시도)
2. **수동 재시작**:
   ```bash
   docker compose -f docker/compose.p2.yml restart inference-chat
   ```
3. **GPU OOM 시** GPU 레이어 조정:
   ```bash
   # .env 파일 수정
   CHAT_N_GPU_LAYERS=999  # → 500으로 감소

   docker compose -f docker/compose.p2.yml up -d inference-chat
   ```

**복구 확인**:
```bash
# 헬스체크
curl http://localhost:8001/health

# 모델 로딩 확인
curl http://localhost:8001/v1/models

# 간단한 추론 테스트
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "안녕"}]}'
```

---

### Scenario 2: Qdrant 연결 실패

**증상**:
- RAG `/health` 엔드포인트가 503 반환
- RAG 로그에 Qdrant 연결 에러

**확인**:
```bash
# Qdrant 상태
docker ps | grep qdrant

# Qdrant 로그
docker logs qdrant --tail 100

# Qdrant API 테스트
curl http://localhost:6333/collections
```

**대응**:
1. **Qdrant 재시작**:
   ```bash
   docker compose -f docker/compose.p2.yml restart qdrant
   ```

2. **재시도 메커니즘 확인**:
   - RAG 서비스는 자동으로 3회 재시도 (exponential backoff)
   - 로그에서 `tenacity` 재시도 메시지 확인

3. **데이터 손상 시 복구**:
   ```bash
   # Qdrant 데이터 삭제 후 재시작
   docker compose -f docker/compose.p2.yml down qdrant
   rm -rf /mnt/e/ai-data/vectors/qdrant/*
   docker compose -f docker/compose.p2.yml up -d qdrant

   # 문서 재인덱싱
   curl -X POST http://localhost:8002/index?collection=default
   ```

---

### Scenario 3: API Gateway 페일오버 동작 확인

**테스트 시나리오**:
```bash
# 1. inference-chat 강제 중지
docker stop inference-chat

# 2. Chat 요청 전송
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat-7b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 3. API Gateway 로그 확인 (failover 발생 여부)
docker logs api-gateway --tail 50 | grep -i retry

# 4. inference-chat 재시작
docker start inference-chat
```

**예상 동작**:
- API Gateway가 inference-chat 연결 실패 감지
- priority=2인 inference-code로 자동 전환
- 3회 재시도 후 응답 반환 (약 10-30초 소요)

---

### Scenario 4: 전체 서비스 재시작 (순서 보장)

**안전한 재시작 절차**:
```bash
# 1. 전체 중지
docker compose -f docker/compose.p2.yml down

# 2. 의존성 순서대로 시작 (Docker Compose가 자동 처리)
docker compose -f docker/compose.p2.yml up -d

# 3. 각 서비스 healthy 대기
echo "Waiting for services to be healthy..."
sleep 60

# 4. 전체 헬스체크
./health_check.sh
```

**시작 순서** (Docker Compose가 자동 관리):
1. qdrant, embedding, inference-chat, inference-code (병렬)
2. api-gateway (inference 서버 healthy 대기)
3. rag (qdrant, embedding, api-gateway healthy 대기)

---

## ⚙️ 설정 변경

### GPU 레이어 조정 (메모리 최적화)

**현재 설정** (`.env` 또는 `.env.example`):
```bash
CHAT_N_GPU_LAYERS=999    # 3B 모델 전체 GPU
CODE_N_GPU_LAYERS=20     # 7B 모델 일부 GPU
```

**OOM 발생 시 조정**:
```bash
# Chat 모델 GPU 레이어 감소
CHAT_N_GPU_LAYERS=500

# Code 모델 GPU 레이어 감소
CODE_N_GPU_LAYERS=15

# 재시작
docker compose -f docker/compose.p2.yml up -d inference-chat inference-code
```

### 타임아웃 조정

**현재 설정** (`.env.example`):
```bash
LLM_REQUEST_TIMEOUT=60           # 일반 LLM 호출
RAG_LLM_TIMEOUT=120              # RAG LLM 호출
QDRANT_TIMEOUT=30                # Qdrant 호출
EMBEDDING_TIMEOUT=30             # Embedding 호출
```

**느린 응답 시 증가**:
```bash
# .env 파일 수정
LLM_REQUEST_TIMEOUT=120
RAG_LLM_TIMEOUT=180

# RAG 서비스만 재시작
docker compose -f docker/compose.p2.yml restart rag
```

### Qdrant 재시도 설정

**현재 설정**:
```bash
QDRANT_MAX_RETRIES=3             # 재시도 횟수
QDRANT_RETRY_MIN_WAIT=2          # 최소 대기 (초)
QDRANT_RETRY_MAX_WAIT=10         # 최대 대기 (초)
```

**불안정한 네트워크 시 조정**:
```bash
# .env 파일 수정
QDRANT_MAX_RETRIES=5
QDRANT_RETRY_MIN_WAIT=3
QDRANT_RETRY_MAX_WAIT=20

# RAG 서비스 재시작
docker compose -f docker/compose.p2.yml restart rag
```

---

## 📊 로그 분석

### 중요 로그 패턴

**정상 동작**:
```
# Inference 서버
llama server listening at http://0.0.0.0:8001

# API Gateway
litellm.router: Checking health of all models

# RAG
INFO:     Application startup complete

# Qdrant
INFO: Qdrant is ready to serve
```

**장애 징후**:
```
# GPU OOM
CUDA error: out of memory

# Qdrant 연결 실패
qdrant_client.exceptions.ConnectionError

# 타임아웃
httpx.ReadTimeout

# LiteLLM 재시도
litellm.router: Retrying request to http://inference-chat:8001
```

### 로그 수집 명령어

```bash
# 전체 서비스 로그 (최근 100줄)
docker compose -f docker/compose.p2.yml logs --tail 100

# 특정 서비스 실시간 추적
docker compose -f docker/compose.p2.yml logs -f inference-chat

# 에러 로그만 필터링
docker compose -f docker/compose.p2.yml logs | grep -i error

# 특정 시간대 로그
docker compose -f docker/compose.p2.yml logs --since "2025-10-09T10:00:00"
```

---

## 🔧 성능 튜닝

### 추론 속도 개선

**병렬 처리 증가**:
```bash
# .env 파일 수정
LLAMA_PARALLEL=2  # 기본값 1 → 2로 증가

# 재시작
docker compose -f docker/compose.p2.yml restart inference-chat inference-code
```

**배치 크기 조정**:
```bash
# compose.p2.yml 수정
-b 256  # 기본값 128 → 256으로 증가

# 재빌드 및 재시작
docker compose -f docker/compose.p2.yml up -d --build
```

### RAG 검색 성능

**TopK 조정**:
```bash
# .env 파일
RAG_TOPK=2  # 기본값 4 → 2로 감소 (속도 향상)

# RAG 재시작
docker compose -f docker/compose.p2.yml restart rag
```

**청크 크기 조정**:
```bash
# 작은 문서: 빠른 검색
RAG_CHUNK_SIZE=256
RAG_CHUNK_OVERLAP=50

# 큰 문서: 정확도 우선
RAG_CHUNK_SIZE=1024
RAG_CHUNK_OVERLAP=200
```

---

## 📈 메트릭 수집 (Prometheus)

### Prometheus 설정 예시

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'rag-service'
    static_configs:
      - targets: ['localhost:8002']

  - job_name: 'api-gateway'
    static_configs:
      - targets: ['localhost:8000']
```

### 주요 메트릭

- **http_request_duration_seconds**: 응답 시간
- **http_requests_total**: 요청 수
- **http_request_size_bytes**: 요청 크기
- **http_response_size_bytes**: 응답 크기

---

## ✅ 체크리스트

### 일일 운영 체크리스트

- [ ] 모든 서비스 상태 확인 (`docker ps`)
- [ ] 헬스체크 실행 (`./health_check.sh`)
- [ ] GPU 메모리 사용량 확인 (`nvidia-smi`)
- [ ] 에러 로그 확인 (`docker logs | grep -i error`)
- [ ] 디스크 공간 확인 (`df -h /mnt/e/ai-data`)

### 주간 유지보수 체크리스트

- [ ] Qdrant 백업 수행
- [ ] 로그 로테이션 (`docker logs --since 7d`)
- [ ] 성능 메트릭 리뷰
- [ ] 의존성 버전 확인 및 업데이트

---

## 🆘 긴급 연락처 및 리소스

**문서**:
- 아키텍처 비교: `docs/architecture/PHASE2_VS_PHASE3_COMPARISON.md`
- GPU 메모리 검증: `docs/architecture/GPU_MEMORY_VERIFICATION.md`
- 헬스체크 스펙: `docs/architecture/HEALTHCHECK_SPECIFICATION.md`

**이슈 트래킹**:
- GitHub Issue #14: Service Reliability 개선
- 진행 상황: `docs/progress/v1/ri_7.md`

**참고 자료**:
- LiteLLM Failover: https://docs.litellm.ai/docs/routing
- Tenacity Retry: https://tenacity.readthedocs.io/
- Docker Healthcheck: https://docs.docker.com/compose/compose-file/compose-file-v3/#healthcheck

---

**최종 업데이트**: 2025-10-09
**담당자**: 시스템 운영팀
**검토 주기**: 월 1회
