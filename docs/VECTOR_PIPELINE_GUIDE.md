# Phase 2 벡터 임베딩 파이프라인 가이드

## 🎯 개요

Phase 2에서는 메모리 시스템에 벡터 임베딩 기능이 추가되었습니다. 이제 대화 저장 시 자동으로 벡터화되어 의미론적 검색이 가능합니다.

### 핵심 특징
- ✅ **자동 큐잉**: 대화 저장 시 임베딩 큐에 자동 추가
- ✅ **배치 처리**: 효율적인 벡터 생성 및 저장
- ✅ **상태 추적**: pending → synced → failed 상태 관리
- ✅ **하이브리드 검색**: FTS5 + 벡터 유사도 결합
- ✅ **안전한 폴백**: 의존성 없이도 기본 기능 작동

## 🔧 설치 및 설정

### 1. 의존성 설치

#### 🐳 컨테이너 환경 (권장)

의존성은 이미 `services/rag/Dockerfile`에서 `requirements.txt`를 통해 설치됩니다.
새로운 의존성 추가 후에는 이미지 리빌드만 하면 됩니다:

```bash
# 백엔드 스택만 사용 (CI와 동일한 CPU 프로필)
make build-p2 && make up-p2
# GPU 환경에서 실제 모델 사용 시: make up-p2-gpu

# 전체 스택 (데스크톱 포함)
make build-p3 && make up-p3
```

#### 🖥️ 호스트 직접 실행 (선택적)

호스트에서 `example_vector_pipeline.py` 같은 스크립트를 직접 실행하려면:

```bash
# 가상환경 생성 권장
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는 venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r services/rag/requirements.txt
# 또는
pip install qdrant-client httpx
```

### 2. 서비스 실행

```bash
# Phase 2 서비스 시작 (FastEmbed + Qdrant + 전체 인프라)
make up-p2          # CPU 프로필
# GPU 실행은 make up-p2-gpu
```

### 3. 서비스 상태 확인

```bash
# FastEmbed 서비스 확인
curl http://localhost:8003/health

# Qdrant 서비스 확인
curl http://localhost:6333/collections
```

## 🚀 사용 방법

### 기본 사용법

```python
from memory_system import MemorySystem
import asyncio

# 메모리 시스템 초기화
ms = MemorySystem()
project_id = ms.get_project_id('/path/to/your/project')

# 대화 저장 (자동으로 임베딩 큐에 추가)
conv_id = ms.save_conversation(
    project_id=project_id,
    user_query="Python에서 비동기 프로그래밍 방법은?",
    ai_response="asyncio 모듈을 사용하여...",
    model_used="chat-7b"
)

# 대기 중인 임베딩 처리 (비동기)
processed = asyncio.run(ms.process_pending_embeddings(project_id))
print(f"처리된 대화: {processed}개")
```

### 벡터 검색

```python
# 의미론적 유사도 검색
results = await ms.vector_search_conversations(
    project_id=project_id,
    query="asyncio 사용법",
    limit=5,
    score_threshold=0.7
)

# 하이브리드 검색 (FTS5 + 벡터)
hybrid_results = await ms.hybrid_search_conversations(
    project_id=project_id,
    query="Python 비동기",
    limit=10
)
```

### 상태 모니터링

```python
# 임베딩 처리 상태 확인
with ms.transaction(project_id) as conn:
    cursor = conn.execute("""
        SELECT sync_status, COUNT(*) as count
        FROM conversation_embeddings
        GROUP BY sync_status
    """)

    for row in cursor.fetchall():
        print(f"{row['sync_status']}: {row['count']}개")
```

## 📊 아키텍처

### 데이터 흐름

```
1. 대화 저장 → conversations 테이블
     ↓
2. 자동 큐잉 → conversation_embeddings (sync_status='pending')
     ↓
3. 배치 처리 → FastEmbed 서비스 (/embed)
     ↓
4. 벡터 저장 → Qdrant (컬렉션: conversations_{project_id})
     ↓
5. 상태 업데이트 → sync_status='synced', synced_at=timestamp
```

### 서비스 구성

- **FastEmbed 서비스** (포트 8003): BAAI/bge-small-en-v1.5 모델, 384차원
- **Qdrant** (포트 6333): 벡터 데이터베이스
- **SQLite**: 메타데이터 및 상태 추적

### 스키마

```sql
-- 임베딩 상태 추적
CREATE TABLE conversation_embeddings (
    conversation_id INTEGER PRIMARY KEY,
    embedding_vector BLOB,              -- 로컬 폴백용
    qdrant_point_id TEXT,               -- Qdrant 포인트 ID
    sync_status TEXT DEFAULT 'pending', -- 'pending', 'synced', 'failed'
    synced_at DATETIME,                 -- 동기화 완료 시각
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

## 🔍 검색 방식

### 1. FTS5 검색 (키워드)
```python
results = ms.search_conversations(project_id, "Python 함수", limit=10)
```

### 2. 벡터 검색 (의미론적)
```python
results = await ms.vector_search_conversations(
    project_id, "프로그래밍 질문", limit=5, score_threshold=0.7
)
```

### 3. 하이브리드 검색 (결합)
```python
results = await ms.hybrid_search_conversations(
    project_id, "코딩 도움", limit=10, combine_results=True
)
```

## 🛠️ 문제 해결

### 의존성 문제
```bash
# 모듈 없음 오류 시
pip install qdrant-client httpx

# 또는 전체 의존성 설치
pip install -r services/rag/requirements.txt
```

### 서비스 연결 문제
```bash
# 서비스 상태 확인
docker ps | grep -E "(embedding|qdrant)"

# 서비스 재시작 (CPU 프로필)
make down && make up-p2
# GPU 환경이라면 make up-p2-gpu 사용
```

### 임베딩 처리 실패
```python
# 실패한 대화 재처리
with ms.transaction(project_id) as conn:
    conn.execute("""
        UPDATE conversation_embeddings
        SET sync_status = 'pending'
        WHERE sync_status = 'failed'
    """)

# 재처리 실행
asyncio.run(ms.process_pending_embeddings(project_id))
```

## 📈 성능 최적화

### 배치 크기 조정
```python
# 큰 배치로 처리 (기본값: 10)
processed = await ms.process_pending_embeddings(project_id, batch_size=50)
```

### 임계값 조정
```python
# 검색 정확도 vs 결과 수 조절
results = await ms.vector_search_conversations(
    project_id, query,
    limit=10,
    score_threshold=0.8  # 높을수록 정확하지만 결과 적음
)
```

## 🔄 백그라운드 처리

프로덕션 환경에서는 주기적으로 임베딩을 처리하는 백그라운드 작업을 설정할 수 있습니다:

```python
import asyncio
import schedule
import time

async def process_all_pending():
    ms = MemorySystem()
    # 모든 프로젝트의 대기 중인 임베딩 처리
    # (실제 구현 시 프로젝트 목록 가져오기 로직 필요)

def run_background_processor():
    asyncio.run(process_all_pending())

# 매 10분마다 실행
schedule.every(10).minutes.do(run_background_processor)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 📚 관련 문서

- [Phase 1 메모리 시스템 가이드](./MEMORY_SYSTEM_GUIDE.md)
- [전체 아키텍처 문서](../docs/progress/v1/ri_3.md)
- [API 엔드포인트 문서](./API_ENDPOINTS.md)

---

이제 `make up-p2`(CPU 프로필)와 의존성 설치만으로 완전한 벡터 검색 시스템을 사용할 수 있습니다! GPU 모델이 필요하면 `make up-p2-gpu`를 사용하세요. 🚀
