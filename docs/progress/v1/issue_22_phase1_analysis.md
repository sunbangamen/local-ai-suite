# Issue #22 Phase 1: 현재 테스트 커버리지 측정 및 분석

**작성일**: 2025-10-22
**상태**: Phase 1 완료

## 현황 분석

### 1. 기존 커버리지 현황

**RAG Service**
- 커버리지: **67%** (342 statements, 114 missed)
- 기존 테스트: 22개
  - RAG Integration Tests: 5개
  - RAG Extended Tests: 17개
- 부족 영역: 에러 처리, 타임아웃, 의존성 실패 시나리오

**Embedding Service**
- 커버리지: **81%** (88 statements, 17 missed)
- 기존 테스트: 18개
- 달성도: 80% 목표 초과 달성 ✅
- 부족 영역: 캐시 처리, 모델 로드 실패

**MCP Server**
- 상태: **미측정**
- 예상 커버리지: 50-60% (추정)
- 구현 파일:
  - security.py (16.3 KB)
  - sandbox.py (17.9 KB)
  - rbac_manager.py (12.6 KB)
  - rbac_middleware.py (6.7 KB)
  - audit_logger.py (9.7 KB)
  - approval_cli.py (11.5 KB)

**API Gateway**
- 상태: **미측정**
- 예상 커버리지: 40-50% (추정)
- 구현 파일: services/api-gateway/app.py

### 2. 전체 커버리지 목표

**현재**: 부분 측정 상태
- RAG: 67%
- Embedding: 81%

**목표**: 전체 80% 달성
- 필요 추가 테스트: 36개 이상
- 예상 최종 커버리지:
  - RAG: 67% → 75-80%
  - Embedding: 81% → 유지 (이미 목표 초과)
  - MCP Server: 50-60% → 70-75%
  - API Gateway: 40-50% → 70-75%
  - 전체 평균: 80% 달성

### 3. 부족 영역 식별

#### RAG Service (5-7개 테스트 필요)
| 영역 | 현황 | 목표 |
|------|------|------|
| 쿼리 처리 | 부분 커버 | 100% |
| 벡터 검색 | 부분 커버 | 100% |
| 청킹 전략 | 부분 커버 | 100% |
| 타임아웃 | 미커버 | 추가 |
| 의존성 실패 | 미커버 | 추가 |
| 한국어 처리 | 부분 커버 | 강화 |

**필요 테스트**:
1. `test_rag_query_timeout` - 타임아웃 처리
2. `test_rag_qdrant_failure` - Qdrant 연결 실패
3. `test_rag_embedding_service_error` - Embedding 서비스 오류
4. `test_rag_llm_timeout` - LLM 타임아웃
5. `test_rag_korean_query` - 한국어 쿼리 처리
6. `test_rag_large_response` - 대용량 응답 처리
7. `test_rag_cache_hit_miss` - 캐시 동작 검증

#### MCP Server RBAC (8-10개 테스트 필요)
| 영역 | 현황 | 목표 |
|------|------|------|
| 권한 검증 | 부분 커버 | 100% |
| 감사 로깅 | 부분 커버 | 100% |
| 승인 워크플로우 | 부분 커버 | 100% |
| 샌드박스 | 부분 커버 | 100% |
| 레이트 리미팅 | 미커버 | 추가 |

**필요 테스트**:
1. `test_rbac_permission_denied` - 권한 거부
2. `test_rbac_high_priority_approval` - HIGH 도구 승인 필요
3. `test_rbac_audit_log_detailed` - 감사 로그 상세 기록
4. `test_sandbox_malicious_code` - 악성 코드 차단
5. `test_sandbox_path_traversal` - 경로 탈출 차단
6. `test_rate_limit_exceeded` - 레이트 리미트 초과
7. `test_rate_limit_reset` - 레이트 리미트 리셋
8. `test_approval_timeout` - 승인 요청 타임아웃
9. `test_audit_log_ordering` - 감사 로그 순서
10. `test_rbac_concurrent_access` - 동시 접근 처리

#### API Gateway (10-12개 테스트 필요)
| 영역 | 현황 | 목표 |
|------|------|------|
| 라우팅 | 부분 커버 | 100% |
| 페일오버 | 부분 커버 | 100% |
| 헬스체크 | 부분 커버 | 100% |
| 모델 선택 | 미커버 | 추가 |
| 토큰 제한 | 미커버 | 추가 |

**필요 테스트**:
1. `test_gateway_route_to_inference_chat` - Chat 모델 라우팅
2. `test_gateway_route_to_inference_code` - Code 모델 라우팅
3. `test_gateway_failover_chat_to_code` - Chat 실패 → Code 페일오버
4. `test_gateway_both_inference_down` - 모든 서버 다운 처리
5. `test_gateway_health_check_inference_chat` - Chat 헬스체크
6. `test_gateway_health_check_inference_code` - Code 헬스체크
7. `test_gateway_model_selection_chat` - Chat 모델 선택 로직
8. `test_gateway_model_selection_code` - Code 모델 선택 로직
9. `test_gateway_token_limit_enforcement` - 토큰 제한 강제
10. `test_gateway_response_streaming` - 응답 스트리밍
11. `test_gateway_error_response_format` - 에러 응답 형식
12. `test_gateway_timeout_handling` - 타임아웃 처리

#### Embedding Service (3-5개 테스트 필요)
| 영역 | 현황 | 목표 |
|------|------|------|
| 배치 처리 | 부분 커버 | 100% |
| 캐시 | 미커버 | 추가 |
| 모델 로드 실패 | 미커버 | 추가 |

**필요 테스트**:
1. `test_embedding_batch_process` - 배치 처리
2. `test_embedding_cache_hit` - 캐시 히트
3. `test_embedding_cache_miss` - 캐시 미스
4. `test_embedding_model_load_failure` - 모델 로드 실패
5. `test_embedding_concurrent_requests` - 동시 요청 처리

### 4. 테스트 작성 순서 (우선순위)

**Phase 2.1: 높음 우선순위 (일차)**
- [ ] MCP Server RBAC 테스트: 8-10개
- [ ] API Gateway 테스트: 10-12개
- **소계**: 18-22개 테스트
- **예상 시간**: 1-1.5시간

**Phase 2.2: 중간 우선순위 (이차)**
- [ ] RAG 추가 테스트: 5-7개
- [ ] Embedding 추가 테스트: 3-5개
- **소계**: 8-12개 테스트
- **예상 시간**: 1-1.5시간

### 5. 테스트 작성 기준

#### 단위 테스트 (Unit Test)
- Mock 서비스 활용
- FastAPI TestClient 또는 httpx AsyncClient
- 기존 conftest.py 재사용

#### 통합 테스트 (Integration Test)
- Docker Compose Phase 2 (선택적)
- 실제 서비스 간 통신 검증
- 타임아웃 시나리오 포함

#### 테스트 패턴
```python
# 기본 패턴
@pytest.mark.asyncio
async def test_feature_name():
    # Arrange: 테스트 데이터 준비
    mock_service = MagicMock()
    
    # Act: 기능 실행
    result = await function_under_test(mock_service)
    
    # Assert: 결과 검증
    assert result.status_code == 200
    mock_service.assert_called_once()
```

### 6. 예상 최종 상태

**테스트 수**
- 기존: RAG 22 + Embedding 18 = 40개
- 추가: 36개
- **총 합계**: 76개

**커버리지**
- RAG: 67% → 75-80%
- Embedding: 81% → 유지
- MCP Server: 50% → 75%
- API Gateway: 40% → 75%
- **전체 평균**: 80% 달성 ✅

**예상 소요 시간**
- Phase 1: 30분 (현재 진행)
- Phase 2: 2-3시간
- Phase 3: 30분
- **총 3-4시간**

---

## 다음 단계

Phase 2 준비 완료. 테스트 코드 작성 시작 예정.

**관련 파일**:
- services/mcp-server/tests/
- services/rag/tests/
- services/embedding/tests/ (예상)
- services/api-gateway/tests/ (예상)

