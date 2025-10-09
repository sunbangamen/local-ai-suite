# GPU Memory Verification for Dual Inference Setup

**작성일**: 2025-10-09
**대상 GPU**: NVIDIA RTX 4050 (6GB VRAM)
**목적**: Phase 2 이중화 구성 시 GPU 메모리 사용량 검증

---

## 📊 메모리 사용량 시나리오 분석

### Scenario 1: 7B + 7B (기존 계획)

| 구성 요소 | 모델 | VRAM 예상 사용량 | 비고 |
|----------|------|------------------|------|
| **inference-chat** | Qwen2.5-7B-Instruct-Q4_K_M | ~4.4GB | 7B 파라미터, Q4_K_M 양자화 |
| **inference-code** | Qwen2.5-Coder-7B-Instruct-Q4_K_M | ~4.4GB | 7B 파라미터, Q4_K_M 양자화 |
| **시스템 오버헤드** | - | ~0.5GB | CUDA context, 프레임워크 |
| **총 VRAM 필요량** | - | **9.3GB** | ❌ **초과** |

**결론**: RTX 4050 6GB로는 **불가능**

---

### Scenario 2: 3B + 7B (대안 - 채택)

| 구성 요소 | 모델 | VRAM 예상 사용량 | 비고 |
|----------|------|------------------|------|
| **inference-chat** | Qwen2.5-3B-Instruct-Q4_K_M | ~2.2GB | 3B 파라미터, Q4_K_M 양자화 |
| **inference-code** | Qwen2.5-Coder-7B-Instruct-Q4_K_M | ~4.4GB | 7B 파라미터, Q4_K_M 양자화 |
| **시스템 오버헤드** | - | ~0.5GB | CUDA context, 프레임워크 |
| **총 VRAM 필요량** | - | **7.1GB** | ⚠️ **경계선** |

**결론**:
- 이론상 초과하지만, 실제로는 **일부 레이어 CPU 오프로드** 가능
- `--n-gpu-layers` 조정으로 VRAM 사용량 제어
- **채택 가능** (성능 저하 감수)

---

### Scenario 3: 3B + 7B (CPU Fallback 최적화)

| 구성 요소 | 모델 | GPU 레이어 | VRAM 사용량 | CPU 레이어 |
|----------|------|-----------|-------------|-----------|
| **inference-chat** | Qwen2.5-3B-Instruct-Q4_K_M | 999 (전체) | ~2.2GB | 0 |
| **inference-code** | Qwen2.5-Coder-7B-Instruct-Q4_K_M | 20-25 | ~2.5GB | 나머지 |
| **시스템 오버헤드** | - | - | ~0.5GB | - |
| **총 VRAM 사용량** | - | - | **~5.2GB** | ✅ **안전** |

**장점**:
- VRAM 여유 확보 (~0.8GB 버퍼)
- 안정적인 동시 실행
- OOM (Out of Memory) 위험 최소화

**단점**:
- Code 모델 추론 속도 약 20-30% 저하
- CPU 병목 가능성

**결론**: **권장 설정** (안정성 우선)

---

## 🔧 Llama.cpp GPU 레이어 제어

### 환경변수 조정

```bash
# compose.p2.yml 또는 .env 파일

# Chat 모델 (3B): 전체 GPU 사용
CHAT_MODEL_N_GPU_LAYERS=999

# Code 모델 (7B): 일부 CPU 오프로드
CODE_MODEL_N_GPU_LAYERS=20
```

### Docker Compose 적용 예시

```yaml
services:
  inference-chat:
    command: >
      --host 0.0.0.0 --port 8001
      --model /models/${CHAT_MODEL:-Qwen2.5-3B-Instruct-Q4_K_M.gguf}
      --n-gpu-layers ${CHAT_N_GPU_LAYERS:-999}  # 전체 GPU
      -c 1024 -b 128 -t 4
      --parallel 1 --cont-batching

  inference-code:
    command: >
      --host 0.0.0.0 --port 8001
      --model /models/${CODE_MODEL:-qwen2.5-coder-7b-instruct-q4_k_m.gguf}
      --n-gpu-layers ${CODE_N_GPU_LAYERS:-20}   # 일부 CPU 오프로드
      -c 1024 -b 128 -t 4
      --parallel 1 --cont-batching
```

---

## 🧪 실제 검증 방법

### 1. VRAM 사용량 모니터링

```bash
# nvidia-smi로 실시간 모니터링
watch -n 1 nvidia-smi

# 또는 상세 정보 출력
nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 1
```

### 2. 컨테이너별 VRAM 사용량 확인

```bash
# inference-chat 시작 후 VRAM 체크
docker compose -f docker/compose.p2.yml up -d inference-chat
nvidia-smi

# inference-code 시작 후 VRAM 체크
docker compose -f docker/compose.p2.yml up -d inference-code
nvidia-smi
```

### 3. 부하 테스트

```bash
# Chat 모델 동시 요청 (10개)
seq 1 10 | xargs -P 10 -I {} curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "안녕하세요"}]}'

# Code 모델 동시 요청 (10개)
seq 1 10 | xargs -P 10 -I {} curl -X POST http://localhost:8004/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "파이썬 함수 작성해줘"}]}'
```

---

## 📈 예상 성능 비교

| 설정 | VRAM 사용량 | Chat 속도 | Code 속도 | 안정성 | 권장도 |
|------|------------|----------|----------|--------|--------|
| **7B + 7B (불가능)** | 9.3GB | - | - | ❌ OOM | ❌ |
| **3B + 7B (전체 GPU)** | 7.1GB | 100% | 100% | ⚠️ 불안정 | ⚠️ |
| **3B + 7B (CPU 오프로드)** | 5.2GB | 100% | 70-80% | ✅ 안정 | ✅ **권장** |

---

## 🎯 Phase 2 최종 권장 설정

### .env 파일

```bash
# Phase 2: RTX 4050 6GB 최적화
CHAT_MODEL=Qwen2.5-3B-Instruct-Q4_K_M.gguf
CODE_MODEL=qwen2.5-coder-7b-instruct-q4_k_m.gguf

# GPU 레이어 설정
CHAT_N_GPU_LAYERS=999   # Chat: 전체 GPU (2.2GB)
CODE_N_GPU_LAYERS=20    # Code: 일부 CPU 오프로드 (2.5GB)
```

### 메모리 제한

```yaml
services:
  inference-chat:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 6G    # 시스템 메모리 제한

  inference-code:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 6G
```

---

## 🔍 문제 해결

### OOM (Out of Memory) 발생 시

1. **Code 모델 GPU 레이어 감소**
   ```bash
   CODE_N_GPU_LAYERS=15  # 20 → 15로 감소
   ```

2. **Context 크기 감소**
   ```bash
   -c 512  # 1024 → 512로 감소
   ```

3. **병렬 처리 비활성화**
   ```bash
   --parallel 1  # 이미 최소값
   ```

### 성능 저하 발생 시

1. **CPU 스레드 증가**
   ```bash
   -t 6  # 4 → 6으로 증가
   ```

2. **배치 크기 조정**
   ```bash
   -b 256  # 128 → 256으로 증가
   ```

---

## 📊 모델 파일 크기 참고

| 모델 | 파일 크기 | VRAM 예상 (전체 GPU) |
|------|----------|---------------------|
| Qwen2.5-3B-Instruct-Q4_K_M | ~2.0GB | ~2.2GB |
| Qwen2.5-7B-Instruct-Q4_K_M | ~4.1GB | ~4.4GB |
| Qwen2.5-Coder-7B-Instruct-Q4_K_M | ~4.1GB | ~4.4GB |
| Qwen2.5-14B-Instruct-Q4_K_M | ~8.2GB | ~8.8GB (RTX 4050 불가) |

---

## ✅ 검증 체크리스트

Phase 2 배포 전 확인 사항:

- [ ] 3B Chat 모델 파일 존재 확인 (`Qwen2.5-3B-Instruct-Q4_K_M.gguf`)
- [ ] 7B Code 모델 파일 존재 확인 (`qwen2.5-coder-7b-instruct-q4_k_m.gguf`)
- [ ] `.env` 파일에 GPU 레이어 설정 적용
- [ ] `nvidia-smi`로 현재 VRAM 사용량 확인 (< 1GB)
- [ ] inference-chat 단독 시작 후 VRAM 체크 (~2.2GB)
- [ ] inference-code 추가 시작 후 VRAM 체크 (~4.7GB 이하)
- [ ] 양쪽 모델 동시 추론 테스트 성공
- [ ] 30분 부하 테스트 후 OOM 미발생 확인

---

**검증 담당**: 시스템 운영자
**검증 완료 시**: `docs/progress/v1/fb_7.md`에 결과 기록
