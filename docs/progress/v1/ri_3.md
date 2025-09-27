# GitHub Issue #5 Analysis & Solution Planning

## Issue Information Summary

**이슈 번호**: #5
**제목**: [Feature] 프로젝트별 장기 기억 시스템 - 무제한 대화 지원 및 스마트 정리
**상태**: Open
**생성일**: 2025-09-27T09:15:00Z
**담당자**: 없음
**라벨**: 없음
**마일스톤**: 없음

### Issue Content Analysis

**문제 유형**: Feature Enhancement
**우선순위**: High
**복잡도**: Complex

**핵심 요구사항**:
- SQLite 기반 프로젝트별 대화 저장 시스템 구현
- 중요도 기반 자동 정리 스케줄러 동작
- 키워드 및 의미 검색 기능 (1초 이내 응답)
- CLI 및 Desktop App UI 완성
- 벡터 임베딩 및 Qdrant 연동 완료
- 100만개 대화 처리 성능 달성

**기술적 제약사항**:
- 기존 AI CLI 시스템과 완전 호환성 유지
- 로컬 저장 원칙, 사용자 프라이버시 보호
- Qdrant 장애 대비 재시도 파이프라인 필요

---

## Technical Investigation

### Code Analysis - Current Architecture

**현재 시스템 구조**:
- **AI CLI**: `scripts/ai.py` - 7B 모델 기반 자동 선택, MCP 도구 통합
- **Database Layer**: `services/rag/database.py` - RAG 검색 로그 및 캐싱용 SQLite
- **Vector Store**: Qdrant (포트 6333) - 문서 임베딩 저장
- **Embedding Service**: FastEmbed (포트 8003) - BAAI/bge-small-en-v1.5 모델
- **Data Directory**: `/mnt/e/ai-data/` - PostgreSQL, Qdrant, 문서, 로그

**영향 범위 분석**:
- **Backend**: `scripts/ai.py` 메인 로직, `services/rag/` 벡터 검색
- **Database**: 새로운 메모리 전용 SQLite 테이블 추가 필요
- **Frontend**: AI CLI 명령어 확장, Desktop App UI 추가
- **Infrastructure**: 기존 Qdrant/임베딩 서비스 활용

### Current Integration Points

**기존 데이터베이스 활용**:
- `services/rag/database.py`의 SQLite 구조 확장 가능
- 검색 분석, 캐싱 시스템 이미 구현됨
- Thread-safe 연결 관리 및 트랜잭션 지원

**기존 벡터 검색 시스템**:
- Qdrant 연동 및 임베딩 생성 파이프라인 완성
- FastEmbed 서비스로 로컬 임베딩 생성
- `services/rag/app.py`에서 문서 기반 RAG 구현

---

## Solution Strategy

### Approach Options

**Option 1: 기존 RAG 시스템 확장**
- **장점**: 기존 인프라 활용, 빠른 구현, 검증된 벡터 검색
- **단점**: RAG와 메모리 시스템 결합으로 복잡도 증가
- **예상 시간**: 8-10일
- **위험도**: Medium

**Option 2: 독립적인 메모리 시스템 구축**
- **장점**: 명확한 관심사 분리, 확장성, 유지보수성
- **단점**: 중복 인프라, 개발 시간 증가
- **예상 시간**: 12-15일
- **위험도**: Low

**Option 3: 하이브리드 접근법**
- **장점**: 핵심 기능은 독립적, 벡터 검색은 기존 인프라 활용
- **단점**: 복잡한 아키텍처, 의존성 관리
- **예상 시간**: 10-12일
- **위험도**: Medium

### Recommended Approach

**선택한 접근법**: Option 3 - 하이브리드 접근법
**선택 이유**:
- 기존 RAG 시스템의 벡터 검색 인프라 재사용으로 개발 효율성 극대화
- 메모리 시스템은 독립적 모듈로 관심사 분리
- 기존 시스템 안정성 유지하면서 점진적 확장 가능

---

## Detailed Implementation Plan

### Phase 1: 핵심 메모리 시스템 구축 (Day 1-4)

**목표**: 기본 대화 저장 및 프로젝트별 메모리 관리

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 메모리 데이터베이스 설계 | SQLite 스키마 및 마이그레이션 스크립트 작성 | 개발자 | 테이블 생성 및 인덱스 완료 | Low |
| 프로젝트 식별 시스템 | `.ai-memory/project.json`에 UUID를 저장해 지속 가능한 프로젝트 ID 관리 | 개발자 | 프로젝트별 메모리 분리 및 경로 변경 후 재사용 확인 | Low |
| 대화 저장 핵심 로직 | `scripts/ai.py`에 메모리 저장 통합 | 개발자 | 모든 대화가 자동 저장됨 | Medium |
| 중요도 자동 판정 | 키워드 및 응답 패턴 기반 점수 계산 | 개발자 | 85% 이상 정확도 달성 | Medium |

### Phase 2: 검색 및 컨텍스트 시스템 (Day 5-7)

**목표**: 관련 대화 검색 및 자동 컨텍스트 포함

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 키워드 검색 구현 | SQLite FTS5 기반 전문 검색 | 개발자 | 1초 이내 검색 응답 | Low |
| 벡터 임베딩 연동 | 기존 FastEmbed 서비스 활용 | 개발자 | 의미적 유사성 검색 가능 | Medium |
| 컨텍스트 자동 포함 | 관련 대화를 AI 응답에 자동 포함 | 개발자 | 관련성 80% 이상 정확도 | High |
| Qdrant 동기화 | 메모리 대화를 벡터 저장소에 비동기 저장 | 개발자 | 장애 복구 메커니즘 완료 | High |
| 메모리 API 엔드포인트 | `api-gateway`에 메모리 CRUD/검색 REST 엔드포인트 추가 | 개발자 | Desktop/CLI에서 공용 API 호출 | Medium |

### Phase 3: 자동 정리 시스템 (Day 8-9)

**목표**: TTL 기반 자동 삭제 및 백그라운드 스케줄러

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| TTL 기반 정리 로직 | 중요도별 보관 기간 자동 삭제 | 개발자 | 안전한 삭제 확인 시스템 | Low |
| 백그라운드 스케줄러 | APScheduler 기반 자동 정리 실행 | 개발자 | 일일 자동 정리 동작 | Medium |
| 백업 시스템 | JSON 백업 및 복원 기능 | 개발자 | 데이터 무결성 보장 | Low |
| 정리 스케줄러 서비스 배치 | `services/rag` 백그라운드 태스크에서 APScheduler 상시 실행 | 개발자 | Docker 서비스 상시 구동 및 CLI 독립 운영 | Medium |

### Phase 4: 사용자 인터페이스 (Day 10-11)

**목표**: CLI 명령어 및 Desktop App UI 완성

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| AI CLI 메모리 명령어 | 15개 메모리 관리 명령어 구현 | 개발자 | 모든 명령어 동작 확인 | Low |
| Desktop App UI | 메모리 관리 탭 및 검색 인터페이스 | 프론트엔드 | 사용자 시나리오 테스트 통과 | Medium |
| 통계 및 시각화 | 메모리 사용량 및 프로젝트별 통계 | 프론트엔드 | 실시간 통계 표시 | Low |

### Phase 5: 성능 최적화 및 고급 기능 (Day 12)

**목표**: 100만개 대화 처리 성능 및 AI 요약 기능

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 성능 테스트 및 최적화 | 대용량 데이터 처리 성능 검증 | 개발자 | 1초 이내 검색 달성 | High |
| AI 요약 생성 | 주기적 대화 요약 자동 생성 | 개발자 | 의미있는 요약 품질 | Medium |
| 모니터링 시스템 | 메모리 시스템 성능 모니터링 | 개발자 | 실시간 성능 지표 | Low |

---

### Architecture Adjustments for Implementation

- **Scheduler Hosting**: TTL 정리와 중요도 기반 백그라운드 작업은 `services/rag`(추후 필요 시 전용 `memory-service`)의 FastAPI 백그라운드 태스크에서 APScheduler로 구동한다. Docker 컨테이너 라이프사이클과 함께 동작하므로 CLI 종료와 무관하게 일일 정리가 수행된다.
- **Shared Memory API**: CLI와 Desktop App은 동일한 `api-gateway` 메모리 엔드포인트를 사용해 대화 CRUD, 검색, 통계 데이터를 요청한다. REST 스펙(예: `GET /v1/memory/projects/{project_id}/conversations`)을 명시하여 Electron 앱이 직접 SQLite 파일에 접근하지 않아도 된다.
- **Project Identity Persistence**: 각 프로젝트 루트에 `.ai-memory/project.json` 파일을 두고 UUID·프로젝트 메타데이터를 저장한다. 최초 실행 시 생성하고 경로 변경·머신 이동 후에도 동일 ID를 재사용한다.
- **CLI Responsibility**: `scripts/ai.py`는 메모리 저장/검색을 API 호출로 위임하고, 로컬 캐시가 필요할 때만 SQLite 폴백을 사용한다. MCP 호출과 동일한 경로 처리로 개발 경험을 유지한다.

---

## Risk Assessment & Mitigation

### High Risk Items

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| Qdrant 벡터 동기화 실패 | High | Medium | 로컬 SQLite 벡터 검색으로 폴백, 재시도 큐 구현 |
| 대용량 데이터 성능 저하 | High | Medium | 인덱스 최적화, 페이징 처리, 캐싱 레이어 추가 |
| 기존 시스템 호환성 문제 | Medium | Low | 점진적 통합, 기능 플래그로 단계적 활성화 |

### Technical Challenges

**예상 기술적 난점**:
1. **벡터 임베딩 성능 최적화** - 배치 처리 및 비동기 처리로 해결
2. **SQLite 동시성 제한** - WAL 모드 및 연결 풀링으로 개선
3. **메모리 사용량 관리** - 대화 압축 및 캐시 정책 구현

### Rollback Plan

**롤백 시나리오**:
- **성능 문제 발생** → 메모리 기능 비활성화, 기존 시스템 유지
- **데이터 손실 위험** → JSON 백업에서 복구, 메모리 시스템 재구축

---

## Resource Requirements

### Human Resources
- **백엔드 개발자**: Python, SQLite, FastAPI 경험 (1명)
- **프론트엔드 개발자**: React, Electron 경험 (1명, Phase 4만)
- **리뷰어**: 시스템 아키텍처 및 성능 검토 (1명)

### Technical Resources
- **개발 도구**: SQLite, FastEmbed, Qdrant, APScheduler
- **테스트 환경**: 100만개 대화 데이터셋 생성 도구
- **모니터링**: 성능 지표 수집 및 알람 시스템

### Time Estimation
- **총 예상 시간**: 12일
- **버퍼 시간**: 3일 (25% 버퍼)
- **완료 목표일**: 2025-10-12

---

## Quality Assurance Plan

### Test Strategy

**테스트 레벨**:
- **Unit Tests**: 메모리 저장/검색, 중요도 계산 로직
- **Integration Tests**: AI CLI와 메모리 시스템 통합
- **Performance Tests**: 100만개 대화 처리, 1초 검색 응답

### Test Cases

```gherkin
Feature: 프로젝트별 장기 기억 시스템

  Scenario: 대화 자동 저장
    Given AI CLI를 통해 질문을 입력할 때
    When AI가 응답을 생성하면
    Then 대화가 프로젝트별 메모리에 자동 저장됨
    And 중요도 점수가 자동 계산됨

  Scenario: 관련 컨텍스트 자동 포함
    Given 이전에 관련된 대화가 있을 때
    When 새로운 질문을 입력하면
    Then 관련된 이전 대화가 컨텍스트로 포함됨
    And AI 응답 품질이 향상됨

  Scenario: 성능 목표 달성
    Given 100만개의 대화가 저장되어 있을 때
    When 키워드 검색을 실행하면
    Then 1초 이내에 결과가 반환됨
```

### Performance Criteria
- **검색 응답시간**: 1초 이내
- **대화 저장 시간**: 100ms 이내
- **중요도 판정 정확도**: 85% 이상
- **메모리 사용량**: 8GB 이하 (100만개 대화 기준)

---

## Communication Plan

### Status Updates
- **일일 스탠드업**: 구현 진행상황 및 블로커 공유
- **이슈 댓글 업데이트**: Phase 완료시마다 상세 보고
- **데모 세션**: Phase 2, 4 완료시 기능 시연

### Stakeholder Notification
- **프로젝트 매니저**: 주간 진행률 보고서
- **사용자 커뮤니티**: 베타 테스트 참여 요청
- **기술팀**: 아키텍처 리뷰 및 코드 리뷰 참여

---

## 📋 User Review Checklist

**다음 항목들을 검토해주세요:**

### Planning Review
- [ ] **이슈 분석이 정확한가요?**
  - 프로젝트별 장기 기억, 무제한 대화 지원, 스마트 정리 요구사항 완전 반영
  - 성능 목표 (100만개 대화, 1초 검색) 및 기술 제약사항 정확히 파악

- [ ] **선택한 해결 방안이 적절한가요?**
  - 하이브리드 접근법: 기존 RAG 인프라 활용 + 독립적 메모리 시스템
  - 기존 시스템 안정성 유지하면서 점진적 확장 가능
  - SQLite + Qdrant 조합으로 로컬 우선, 벡터 검색 보조 구조

- [ ] **구현 계획이 현실적인가요?**
  - 12일 + 3일 버퍼로 총 15일 일정
  - Phase별 명확한 목표와 완료 조건 설정
  - 기존 `scripts/ai.py` 및 `services/rag/` 시스템과의 통합 지점 명확

### Resource Review
- [ ] **시간 추정이 합리적인가요?**
  - Phase 1-3: 핵심 기능 (9일) - 적절
  - Phase 4-5: UI 및 최적화 (3일) - 타이트하지만 실현 가능
  - 25% 버퍼 시간으로 위험 완충

- [ ] **필요한 리소스가 확보 가능한가요?**
  - 백엔드 개발자 1명 (주요), 프론트엔드 개발자 1명 (Phase 4만)
  - 기존 인프라 (Qdrant, FastEmbed) 활용으로 추가 리소스 최소화

### Risk Review
- [ ] **위험 요소가 충분히 식별되었나요?**
  - High Risk: Qdrant 동기화, 성능 최적화, 기존 시스템 호환성
  - Medium Risk: 컨텍스트 정확도, UI 복잡성
  - 각 위험에 대한 구체적 완화 방안 제시

- [ ] **롤백 계획이 현실적인가요?**
  - 기능 플래그로 점진적 활성화
  - JSON 백업 시스템으로 데이터 복구 가능

### Quality Review
- [ ] **테스트 전략이 충분한가요?**
  - 단위/통합/성능 테스트 모두 포함
  - 구체적인 성능 기준 및 정확도 목표 설정
  - 100만개 대화 스케일 테스트 계획

---

## 🚀 Next Steps

**검토 완료 후 진행할 작업:**

1. **Plan Approval**: 위 검토를 통과하면 계획 승인
2. **Issue Update**: GitHub 이슈에 상세 계획 댓글로 추가
3. **Branch Creation**: `feature/memory-system` 브랜치 생성
4. **Memory API Scaffold**: `api-gateway`에 메모리 CRUD/검색 엔드포인트 뼈대 추가 후 Desktop/CLI 연동 계약 확정
5. **Scheduler Service Wiring**: `services/rag` 백그라운드 태스크에 APScheduler 기반 TTL 정리 루프 구현 및 Docker compose 반영
6. **Project ID Persistence**: `.ai-memory/project.json` 생성 로직과 마이그레이션 스크립트 작성

**수정이 필요한 경우:**
- 시간 추정이나 기술적 접근법에 대한 조정 사항
- 추가 위험 요소나 제약 사항 발견
- 리소스 가용성 변경

---

**💡 핵심 장점**
- 기존 시스템과 완전 호환하면서 점진적 확장
- 검증된 RAG 인프라 재사용으로 개발 위험 최소화
- 프로젝트별 독립적 메모리로 확장성 확보
- 자동 중요도 및 정리 시스템으로 사용자 편의성 극대화

**주의:** PR 생성 및 병합은 자동으로 실행하지 않습니다.
필요 시 사용자가 직접 `gh pr create` 등의 명령으로 수동 진행하세요.
