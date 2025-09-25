# Local AI Suite 프로젝트 가이드

## 개요
Local AI Suite는 로컬 환경에서 AI 모델을 서빙하는 완전한 솔루션입니다.

## 설치 방법

### 필수 요구사항
- Docker Desktop with WSL integration
- NVIDIA GPU (RTX 4050 이상 권장)
- 최소 16GB RAM
- 외장 SSD 공간 20GB 이상

### 설치 단계
1. 리포지토리 클론
```bash
git clone <repository-url>
cd local-ai-suite
```

2. 환경 설정
```bash
cp .env.example .env
# .env 파일에서 모델명 설정
```

3. 모델 다운로드
```bash
# models/ 폴더에 GGUF 모델 파일 배치
# 예: qwen2.5-14b-instruct-q4_k_m.gguf
```

4. 서비스 시작
```bash
make up-p1  # Phase 1: 기본 모델 서빙
make up-p2  # Phase 2: RAG 시스템 추가
```

## 사용법

### CLI 도구
```bash
ai "안녕하세요!"
ai "Python 함수 만들어줘"
ai --code "코딩 질문"
ai --chat "일반 대화"
```

### API 사용
```bash
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-14b-instruct", "messages": [{"role": "user", "content": "Hello"}]}'
```

## 문제 해결

### GPU 인식 안됨
1. Docker Desktop에서 WSL GPU 지원 확인
2. NVIDIA 드라이버 최신 버전 설치
3. nvidia-smi 명령어로 GPU 상태 확인

### 서비스 시작 실패
1. 포트 충돌 확인 (8000, 8001, 8002 포트)
2. 모델 파일 경로 및 권한 확인
3. Docker 로그 확인: `docker logs <container-name>`

### 성능 최적화
- GPU 메모리가 부족하면 smaller 모델 사용
- 컨텍스트 크기 조정 (기본값: 8192)
- 병렬 처리 수 조정 (기본값: 4)