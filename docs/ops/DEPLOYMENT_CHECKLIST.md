# 배포 체크리스트

## 사전 준비

### 환경 설정
- [ ] `.env` 파일 생성 및 설정 완료
  ```bash
  cp .env.example .env
  # 필수 환경 변수 설정 확인
  ```
- [ ] 모델 파일 존재 확인
  ```bash
  ls -lh /mnt/e/ai-models/Qwen2.5-3B-Instruct-Q4_K_M.gguf
  ls -lh /mnt/e/ai-models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
  # Phase 2: 3B (~2.5GB) + 7B (~4.4GB) = 총 7GB 필요
  ```
- [ ] 데이터 디렉토리 권한 확인
  ```bash
  ls -ld /mnt/e/ai-data
  ls -ld /mnt/e/ai-models
  ```

### 시스템 요구사항
- [ ] Docker 및 Docker Compose 설치 확인
  ```bash
  docker --version  # 20.10+
  docker compose version  # 2.0+
  ```
- [ ] NVIDIA Docker Runtime 설치 (GPU 사용 시)
  ```bash
  nvidia-smi  # GPU 확인
  docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
  ```
- [ ] 포트 충돌 확인
  ```bash
  # Phase 2 필수 포트
  sudo lsof -i :8000  # API Gateway
  sudo lsof -i :8001  # Inference Chat
  sudo lsof -i :8002  # RAG
  sudo lsof -i :8003  # Embedding
  sudo lsof -i :8004  # Inference Code
  sudo lsof -i :5432  # PostgreSQL
  sudo lsof -i :6333  # Qdrant
  ```
- [ ] 디스크 공간 확인
  ```bash
  df -h /mnt/e  # 최소 20GB 여유 공간 필요
  ```

---

## Phase별 배포 순서

### Phase 1 (Basic AI) - 단일 모델 테스트

**목적**: 기본 LLM 추론 서버 + API Gateway 검증

**배포**:
```bash
# 서비스 시작
make up-p1

# 또는
docker compose -f docker/compose.p1.yml up -d
```

**검증**:
```bash
# 1. 헬스체크
curl http://localhost:8001/health
# 예상 출력: {"status":"ok"} 또는 유사

# 2. 모델 목록 확인
curl http://localhost:8000/v1/models
# 예상 출력: {"data":[{"id":"qwen2.5-14b-instruct",...}]}

# 3. 간단한 추론 테스트
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-14b-instruct",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
# 예상 출력: {"choices":[{"message":{"content":"Hello! How can I help..."}}]}
```

**정리**:
```bash
make down
# 또는
docker compose -f docker/compose.p1.yml down
```

---

### Phase 2 (RAG System) - 전체 서비스 스택

**목적**: Dual-LLM + RAG + Embedding + Qdrant + PostgreSQL 통합 검증

**배포 (Mock LLM / CPU 기본)**:
```bash
# 서비스 시작 (의존성 순서대로 자동 시작)
make up-p2

# 또는
docker compose -f docker/compose.p2.yml up -d
```

**GPU 환경에서 실제 모델 사용 시**:
```bash
make up-p2-gpu
# 또는
docker compose -f docker/compose.p2.yml up -d
```

**헬스체크** (5개 서비스):
```bash
# 1. Inference Chat (3B)
curl -f http://localhost:8001/health || echo "FAIL: Inference Chat"

# 2. Inference Code (7B)
curl -f http://localhost:8004/health || echo "FAIL: Inference Code"

# 3. API Gateway
curl -f http://localhost:8000/health || curl -f http://localhost:8000/v1/models || echo "FAIL: API Gateway"

# 4. RAG Service
curl -f http://localhost:8002/health || echo "FAIL: RAG"

# 5. Embedding Service
curl -f http://localhost:8003/health || echo "FAIL: Embedding"

# 한 번에 실행
for port in 8001 8004 8000 8002 8003; do
  echo -n "Port $port: "
  curl -sf http://localhost:$port/health && echo "OK" || echo "FAIL"
done
```

**기능 테스트**:
```bash
# RAG 컬렉션 인덱싱
curl -X POST http://localhost:8002/index \
  -H "Content-Type: application/json" \
  -d '{"collection": "default"}'

# RAG 쿼리
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 파일 읽기", "collection": "default"}'

# Embedding 생성
curl -X POST http://localhost:8003/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello world", "Test embedding"]}'
```

**로그 확인**:
```bash
# 전체 로그
docker compose -f docker/compose.p2.yml logs

# 특정 서비스 로그
docker compose -f docker/compose.p2.yml logs api-gateway
docker compose -f docker/compose.p2.yml logs rag

# 실시간 tail
docker compose -f docker/compose.p2.yml logs -f --tail=50
```

---

### Phase 3 (MCP + Monitoring) - 완전한 시스템

**목적**: MCP Server + 모니터링 스택 + 전체 시스템 검증

**배포**:
```bash
# Phase 3 서비스 시작
make up-p3

# 모니터링 스택 시작 (선택적)
docker compose -f docker/compose.monitoring.yml up -d
```

**헬스체크** (8개 서비스):
```bash
# Phase 2 서비스 (위와 동일)
# ...

# 추가 서비스
curl -f http://localhost:8020/health  # MCP Server
curl -f http://localhost:6333/collections  # Qdrant

# PostgreSQL 연결 테스트
docker compose -f docker/compose.p3.yml exec postgres pg_isready
```

**모니터링 확인**:
```bash
# Grafana 접속
curl -f http://localhost:3001 && echo "Grafana OK"
open http://localhost:3001  # admin/admin

# Prometheus 접속
curl -f http://localhost:9090/-/healthy && echo "Prometheus OK"

# Loki 준비 상태
curl -f http://localhost:3100/ready && echo "Loki OK"
```

**MCP Server 테스트**:
```bash
# MCP 도구 실행 (read_file)
curl -X POST http://localhost:8020/tools/read_file \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/app/README.md"}'

# Git 상태 확인
curl -X POST http://localhost:8020/tools/git_status \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 배포 후 검증

### 필수 체크리스트
- [ ] 모든 서비스 헬스체크 통과 (`curl http://localhost:*/health`)
- [ ] Grafana 대시보드 메트릭 표시 (최소 1분 대기)
- [ ] Loki 로그 정상 수집 (Grafana Explore → Loki)
- [ ] Prometheus 타겟 UP 상태 (http://localhost:9090/targets)
- [ ] Alertmanager 알림 규칙 로드 (http://localhost:9093)
- [ ] RAG 쿼리 정상 응답
- [ ] MCP 도구 실행 성공 (최소 1개)

### 성능 체크리스트
- [ ] API 응답 시간 < 3초 (p95)
- [ ] GPU 메모리 사용률 < 90% (`nvidia-smi`)
- [ ] 컨테이너 CPU 사용률 < 80% (cAdvisor)
- [ ] 디스크 여유 공간 > 10GB

---

## 롤백 절차

### 즉시 롤백 (서비스 중단 발생 시)

```bash
# 1. 현재 버전 중단
make down
# 또는
docker compose -f docker/compose.p3.yml down
docker compose -f docker/compose.monitoring.yml down

# 2. 이전 버전으로 체크아웃
git log --oneline -5  # 이전 커밋 확인
git checkout <previous-commit-hash>

# 3. 이전 버전 재시작
make up-p3

# 4. 헬스체크 재검증
curl http://localhost:8000/health
```

### 점진적 롤백 (일부 서비스만)

```bash
# 특정 서비스만 재시작
docker compose -f docker/compose.p3.yml restart rag

# 특정 서비스 이미지 변경
docker compose -f docker/compose.p3.yml up -d --no-deps rag
```

### 데이터 백업 (롤백 전)

```bash
# PostgreSQL 덤프
docker compose -f docker/compose.p3.yml exec postgres pg_dump \
  -U ai_user ai_suite > backup-$(date +%Y%m%d).sql

# Qdrant 스냅샷
curl -X POST http://localhost:6333/collections/default/snapshots

# SQLite RBAC DB 백업 (Issue #8)
cp /mnt/e/ai-data/sqlite/security.db /mnt/e/ai-data/sqlite/security.db.backup
```

---

## 트러블슈팅

### 서비스 시작 실패

**증상**: `docker compose up` 실패, 컨테이너 즉시 종료

**디버깅**:
```bash
# 로그 확인
docker compose -f docker/compose.p2.yml logs <service-name>

# 컨테이너 상태
docker compose -f docker/compose.p2.yml ps

# 특정 서비스 재시작
docker compose -f docker/compose.p2.yml restart <service-name>
```

**일반적인 원인**:
1. **모델 파일 없음**: `/mnt/e/ai-models/` 경로 확인
2. **포트 충돌**: `lsof -i :<port>` → 기존 프로세스 종료
3. **의존성 실패**: `depends_on` 서비스 헬스체크 확인
4. **권한 오류**: `chown -R 1000:1000 /mnt/e/ai-data`

---

### GPU 메모리 부족

**증상**: Inference 서버 OOM, 응답 없음

**해결**:
```bash
# 1. GPU 메모리 확인
nvidia-smi

# 2. GPU 레이어 줄이기 (.env 파일)
CHAT_N_GPU_LAYERS=999  # → 500
CODE_N_GPU_LAYERS=20   # → 10

# 3. 서비스 재시작
docker compose -f docker/compose.p2.yml restart inference-chat inference-code
```

**Phase 2 권장 설정 (RTX 4050 6GB)**:
- Chat Model (3B): `CHAT_N_GPU_LAYERS=999` (전체 GPU)
- Code Model (7B): `CODE_N_GPU_LAYERS=20` (부분 CPU 오프로드)

---

### Qdrant 연결 실패

**증상**: RAG Service "Qdrant connection refused"

**해결**:
```bash
# 1. Qdrant 상태 확인
docker compose -f docker/compose.p2.yml ps qdrant

# 2. Qdrant 재시작
docker compose -f docker/compose.p2.yml restart qdrant

# 3. 연결 테스트
curl http://localhost:6333/collections

# 4. RAG Service 재시작 (재시도 메커니즘 활성화)
docker compose -f docker/compose.p2.yml restart rag
```

**재시도 설정** (Issue #14):
- `QDRANT_MAX_RETRIES=3`
- `QDRANT_RETRY_MIN_WAIT=2`
- `QDRANT_RETRY_MAX_WAIT=10`

---

### API Gateway 타임아웃

**증상**: `504 Gateway Timeout`

**해결**:
```bash
# 1. LLM 타임아웃 늘리기 (.env)
LLM_REQUEST_TIMEOUT=60  # → 120
RAG_LLM_TIMEOUT=120     # → 180

# 2. API Gateway 재시작
docker compose -f docker/compose.p2.yml restart api-gateway

# 3. 추론 서버 응답 확인
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}],"max_tokens":5}'
```

---

## 모니터링 확인 포인트

### 서비스 시작 직후 (0-5분)
- [ ] 모든 컨테이너 Running 상태
- [ ] 헬스체크 통과
- [ ] GPU 메모리 할당 완료 (`nvidia-smi`)

### 정상 운영 중 (1시간+)
- [ ] Prometheus 타겟 모두 UP
- [ ] Grafana 대시보드 메트릭 정상 표시
- [ ] Loki 로그 수집 정상
- [ ] CPU/메모리 사용률 안정

### 주간 점검
- [ ] 디스크 사용량 트렌드 (Prometheus retention)
- [ ] 에러 로그 패턴 (Loki)
- [ ] API 응답 시간 추세 (Grafana)

---

## 배포 자동화 (선택적)

### Git Hooks를 통한 자동 배포

**파일 위치**: `.git/hooks/post-merge`

```bash
#!/bin/bash
# post-merge hook: 자동으로 서비스 재시작

echo "Detected git merge, restarting services..."

# 의존성 재설치
pip install -r requirements.txt

# 서비스 재시작
docker compose -f docker/compose.p3.yml up -d --build

echo "Deployment complete!"
```

**활성화**:
```bash
chmod +x .git/hooks/post-merge
```

---

## 참고 자료

- `docker/compose.p1.yml` - Phase 1 구성
- `docker/compose.p2.yml` - Phase 2 구성 (권장)
- `docker/compose.p3.yml` - Phase 3 구성 (전체)
- `docker/compose.monitoring.yml` - 모니터링 스택
- `.env.example` - 환경 변수 템플릿
- `docs/ops/MONITORING_GUIDE.md` - 모니터링 가이드
- `docs/ops/SERVICE_RELIABILITY.md` - 서비스 안정성 가이드
