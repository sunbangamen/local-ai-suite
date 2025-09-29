# Qdrant 자동 복구 기능 구현

## 개요

코덱스의 피드백을 바탕으로 Qdrant 장애 후 복구 시 벡터 기능이 자동으로 활성화되도록 개선했습니다.

## 문제점

기존 구현에서는 `ensure_memory_collection()`에서 예외가 한 번 발생하면 `_vector_enabled = False`로 고정되고, Qdrant가 복구되어도 수동 재시작 없이는 벡터 기능이 다시 활성화되지 않았습니다.

## 해결책

### 1. 자동 복구 로직 추가

**파일**: `scripts/memory_system.py`

```python
def ensure_memory_collection(self, project_id: str) -> bool:
    try:
        # ... 기존 로직 ...
        if response.status_code == 200:
            # 컬렉션 생성/확인 성공 시 벡터 기능 자동 활성화
            if not self._vector_enabled:
                self._vector_enabled = True
                print(f"🔄 벡터 검색 기능 자동 복구됨")
            return True
    except Exception as e:
        # ... 기존 오류 처리 ...
```

### 2. 수동 복구 메서드 추가

```python
def try_vector_recovery(self, project_id: str = None) -> bool:
    """벡터 기능 복구 시도"""
    if self._vector_enabled:
        return True  # 이미 활성화됨

    if not VECTOR_DEPS_AVAILABLE:
        return False  # 의존성 없음

    try:
        # Qdrant 연결 테스트
        result = self.ensure_memory_collection(project_id)
        if result:
            print(f"✅ 벡터 기능 복구 성공")
            return True
        else:
            return False
    except Exception as e:
        print(f"⚠️ 벡터 기능 복구 실패: {e}")
        return False
```

### 3. 헬스체크 자동 복구

**파일**: `services/api-gateway/memory_router.py`

```python
@memory_app.get("/v1/memory/health")
async def health_check():
    try:
        # ... 기존 로직 ...

        # 벡터 기능 복구 시도 (비활성화 상태인 경우)
        if not memory_system._vector_enabled:
            recovery_attempted = memory_system.try_vector_recovery(test_project_id)
            recovery_status = "attempted" if recovery_attempted else "failed"
        else:
            recovery_status = "not_needed"

        return {
            "status": "healthy",
            "memory_system": "available",
            "storage_available": memory_system._storage_available,
            "vector_enabled": memory_system._vector_enabled,
            "vector_recovery": recovery_status,  # 새 필드 추가
            "test_project_id": test_project_id,
            "test_stats": stats
        }
```

### 4. 수동 복구 엔드포인트

```python
@memory_app.post("/v1/memory/vector/recovery")
async def recover_vector_functionality():
    """벡터 기능 수동 복구 시도"""
    try:
        test_project_id = memory_system.get_project_id()
        recovery_success = memory_system.try_vector_recovery(test_project_id)

        return {
            "success": recovery_success,
            "vector_enabled": memory_system._vector_enabled,
            "message": "Vector functionality recovered successfully" if recovery_success
                      else "Vector recovery failed - Qdrant may still be unavailable"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recovering vector functionality: {e}")
```

## 복구 시나리오

### 자동 복구 (권장)

1. **헬스체크 호출 시**: `/v1/memory/health` 호출 시 자동으로 복구 시도
2. **벡터 검색 시**: 벡터 검색 시도 시 컬렉션 확인 과정에서 자동 복구
3. **대화 저장 시**: 임베딩 생성 과정에서 컬렉션 확인 시 자동 복구

### 수동 복구

```bash
# 수동 복구 요청
curl -X POST http://localhost:8005/v1/memory/vector/recovery

# 응답 예시
{
  "success": true,
  "vector_enabled": true,
  "message": "Vector functionality recovered successfully"
}
```

## 복구 확인

### 복구 전 상태
```json
{
  "status": "healthy",
  "vector_enabled": false,
  "vector_recovery": "failed"
}
```

### 복구 후 상태
```json
{
  "status": "healthy",
  "vector_enabled": true,
  "vector_recovery": "not_needed"
}
```

## 로그 메시지

### 성공적인 복구
```
🔄 벡터 검색 기능 자동 복구됨
✅ 벡터 기능 복구 성공
```

### 복구 실패
```
⚠️ 벡터 기능 복구 실패: Connection failed
⚠️ Qdrant 컬렉션 처리 실패, FTS 전용 모드로 전환: Qdrant unavailable
```

## 운영 가이드

### 복구 모니터링

```bash
# 주기적 헬스체크로 자동 복구 모니터링
watch -n 30 'curl -s http://localhost:8005/v1/memory/health | jq ".vector_enabled,.vector_recovery"'
```

### 수동 복구 스크립트

```bash
#!/bin/bash
# vector_recovery.sh
HEALTH=$(curl -s http://localhost:8005/v1/memory/health | jq -r '.vector_enabled')

if [ "$HEALTH" = "false" ]; then
    echo "벡터 기능 비활성화 감지, 복구 시도 중..."
    RESULT=$(curl -s -X POST http://localhost:8005/v1/memory/vector/recovery | jq -r '.success')

    if [ "$RESULT" = "true" ]; then
        echo "✅ 벡터 기능 복구 성공"
    else
        echo "❌ 벡터 기능 복구 실패"
        exit 1
    fi
else
    echo "✅ 벡터 기능 정상"
fi
```

## 제한사항

### 의존성 요구사항

벡터 기능 복구가 작동하려면 다음 의존성이 필요합니다:

```bash
pip install qdrant-client httpx
```

**Docker 환경**에서는 Dockerfile에 의존성 추가가 필요합니다:

```dockerfile
RUN pip install qdrant-client httpx
```

### 네트워크 요구사항

- Qdrant 서비스가 `QDRANT_URL`에서 접근 가능해야 함
- HTTP 연결 타임아웃: 30초
- 네트워크 지연이나 방화벽 설정 고려 필요

## 결론

이제 Qdrant가 복구되면 다음 상황에서 자동으로 벡터 기능이 활성화됩니다:

1. **헬스체크 요청 시** - 가장 일반적
2. **벡터 검색 시도 시** - 사용자 요청 기반
3. **수동 복구 엔드포인트 호출 시** - 관리자 제어

**안전성**: 복구가 실패해도 FTS 기능은 계속 정상 동작하며, 서비스 중단은 발생하지 않습니다.

**편의성**: 별도의 재시작이나 수동 개입 없이 자동으로 최적의 기능으로 복구됩니다.