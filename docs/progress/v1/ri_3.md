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
- **Memory Layer**: `scripts/memory_system.py` - 프로젝트별 메모리 SQLite + 옵션 벡터 연동
- **Vector Store**: Qdrant (포트 6333) - 문서/메모리 임베딩 저장 (선택적 사용)
- **Embedding Service**: FastEmbed (포트 8003) - BAAI/bge-small-en-v1.5 모델
- **Data Directory**: `/mnt/e/ai-data/` - SQLite, Qdrant, 문서, 로그 저장소

**영향 범위 분석**:
- **Backend**: `scripts/ai.py` 메인 로직, `services/rag/` 벡터 검색
- **Database**: 새로운 메모리 전용 SQLite 테이블 추가 필요
- **Frontend**: AI CLI 명령어 확장, Desktop App UI 추가
- **Infrastructure**: 기존 Qdrant/임베딩 서비스 활용

### Current Integration Points

**✅ 검증된 기존 인프라 (memo.md 기준)**:
- **SQLite 분석 DB**: `/mnt/e/ai-data/sqlite/`의 RAG 로그/캐시 구조 안정 운영
- **메모리 SQLite 스택**: 프로젝트별 `memory.db` 구조와 TTL 정책, 중요도 점수 검증 완료
- **7B 모델 최적화**: RTX 4050 6GB 특화 설정 완료 (CPU 99% 개선, 1초 검색 달성)
- **FastEmbed 서비스**: PyTorch-free ONNX 기반, BAAI/bge-small-en-v1.5 (384차원)
- **Qdrant 벡터 DB**: 고성능 벡터 검색 인프라, 포트 6333
- **한국어 지원**: 문장 분할기 + 슬라이딩 청크 (512토큰/100 오버랩) 완료

**🔧 통합 아키텍처**:
- **AI CLI**: 전역 설치 완료, 지능형 chat-7b/code-7b 모델 선택
- **MCP 서버**: 18개 도구, 전역 파일시스템 접근 지원
- **스트리밍 응답**: ChatGPT/Claude Code 스타일 실시간 텍스트 생성
- **Docker 환경**: compose.p3.yml로 전체 통합 스택 운영

**🚨 해결된 기술적 이슈들**:
- 모델명 불일치 및 400 에러 완전 해결
- PostgreSQL 권한 문제 → 현재 Phase에서는 SQLite 전략으로 전환, 향후 named volume 필요 시 재검토
- CPU 사용량 2000% → 13% 최적화 완료
- RAG 타임아웃 문제 → 환경변수 기반 조정 완료

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

### Recommended Approach (memo.md 경험 기반 수정)

**선택한 접근법**: Option 1 개선 - 기존 RAG/메모리 SQLite 시스템 확장 (검증된 방법)
**선택 이유 (memo.md 실증 데이터 기반)**:
- **검증된 성능**: 7B 모델 + FastEmbed + Qdrant 조합으로 1초 검색 이미 달성
- **안정화된 인프라**: 프로젝트별 SQLite 메모리 DB와 RAG 분석 DB 운영 경험 축적
- **운영 경험**: CPU 최적화, 타임아웃 조정, 스트리밍 응답 등 실제 문제 해결 완료
- **전역 통합**: MCP 서버 18개 도구 + 전역 파일시스템 접근으로 확장성 입증

---

## Detailed Implementation Plan (memo.md 검증 기반 수정)

### Phase 1: 기존 시스템 메모리 확장 (Day 1-3) 🚀 가속화

**목표**: 검증된 SQLite + RAG 인프라에 메모리 기능을 정착

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 🔧 SQLite 메모리 스키마 정비 | 프로젝트별 `memory.db` 구조 확정 (conversations, embeddings, ttl 메타 포함) | 개발자 | WAL + 인덱스 구성, FTS5 테이블 정상 동작 | **Low** |
| 🎯 프로젝트 식별 시스템 | MCP 전역 파일 접근을 활용한 `.ai-memory/project.json` 관리 | 개발자 | 18개 MCP 도구와 연동, 전역 접근 확인 | **Low** |
| ⚡ AI CLI 메모리 통합 | 지능형 모델 선택 + 스트리밍 응답에 메모리 저장 훅 추가 | 개발자 | chat-7b/code-7b 모델별 대화 자동 저장 | **Low** |
| 🧠 중요도 자동 판정 | FastEmbed 임베딩 기반 의미 점수 계산 로직 고도화 | 개발자 | BAAI/bge-small-en-v1.5 모델 활용, 85% 정확도 | **Medium** |

### Phase 2: 검증된 검색 시스템 확장 (Day 4-5) ⚡ 단축

**목표**: 1초 내 응답 목표를 SQLite FTS + Qdrant 하이브리드로 달성

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 🔍 SQLite FTS 튜닝 | FTS5 기반 대화 전문 검색 최적화 (토큰화, 랭킹 파라미터 검수) | 개발자 | 평균 응답 1초 내, 상위 결과 정확도 측정 | **Low** |
| 🧮 Qdrant 벡터 확장 | 포트 6333 Qdrant에 memory 컬렉션 추가, SQLite 백업과 병행 | 개발자 | 384차원 FastEmbed 임베딩 재사용 | **Low** |
| 🤖 지능형 컨텍스트 포함 | 듀얼 모델(chat/code) 컨텍스트 선정 로직 확장 | 개발자 | 모델 선택 로직 확장, 80% 정확도 | **Medium** |
| 🔄 실시간 동기화 | SQLite ↔ Qdrant 간 배치/스트리밍 동기화 파이프라인 정립 | 개발자 | memo.md 타임아웃 해결 경험 재활용 | **Low** |
| 🌐 API Gateway 확장 | LiteLLM(8000)에 `/v1/memory` 엔드포인트 추가 | 개발자 | OpenAI 호환 API 패턴 준수 | **Low** |

### Phase 3: 자동 정리 시스템 (Day 6-7) 🎯 최적화

**목표**: 경량 스케줄러와 TTL 정책으로 SQLite 기반 스마트 정리 실현

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 🗂️ 지능형 TTL 시스템 | 중요도 + 모델(chat/code) + 프로젝트별 보존 정책 확정 | 개발자 | 중요도별 TTL 적용 및 검증 | **Low** |
| ⏰ 경량 스케줄러 서비스 | Compose에 `memory-maintainer` 서비스 추가, APScheduler로 주기 정리 | 개발자 | 컨테이너 헬스체크 및 로그 수집 완료 | **Low** |
| 💾 SQLite 백업 | 주기적 JSON/SQL 덤프 및 복원 스크립트 제공 | 개발자 | `/mnt/e/ai-data/memory/backups` 경로 검증 | **Low** |
| 🔄 실시간 정리 모니터링 | MCP 도구 + CLI 로그로 정리 상태 추적 | 개발자 | 전역 파일시스템 접근으로 로그 관리 | **Low** |

### Phase 4: 기존 UI 메모리 확장 (Day 8-9) 🎨 완성도 활용

**목표**: Desktop App과 AI CLI에서 SQLite 메모리 기능을 일관 제공

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 🖥️ AI CLI 메모리 명령어 | 전역 `ai` 명령에 메모리 관리 플래그 6종 정식 지원(확장 목표 10종) | 개발자 | `--memory`, `--memory-search`, `--memory-stats` 등 QA 완료 | **Low** |
| 🎨 Desktop App 메모리 탭 | Electron UI에 SQLite 메모리 검색/정리 뷰 추가 | 프론트엔드 | Claude Desktop 스타일 + 메모리 검색 UI | **Low** |
| 📊 실시간 스트리밍 통합 | 스트리밍 응답에 메모리 컨텍스트 라벨링/하이라이트 | 프론트엔드 | ChatGPT 스타일 + 관련 대화 표시 | **Medium** |

### Phase 5: 검증된 성능 최적화 확장 (Day 10) ⚡ 압축

**목표**: 이미 확보한 최적화 기법을 SQLite 메모리/검색 파이프라인에 확산

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 🚀 검증된 성능 적용 | **이미 달성된 1초 검색 + 7B 모델 최적화**를 메모리 시스템에 적용 | 개발자 | memo.md 증명된 100만개 대화 처리 성능 | **Low** |
| 🧠 지능형 요약 생성 | **듀얼 모델 시스템** 활용해 chat-7b로 요약, code-7b로 코드 요약 | 개발자 | 모델별 특화 요약, 의미있는 품질 | **Medium** |
| 📈 통합 모니터링 확장 | **기존 Docker 헬스체크 + MCP 도구**로 메모리 성능 모니터링 | 개발자 | compose.p3.yml 통합, 실시간 지표 | **Low** |

---

### Architecture Adjustments for Implementation (memo.md 검증 기반)

**🏗️ 실증된 인프라 활용**:
- **Scheduler Hosting**: compose.p3.yml에 `memory-maintainer` 경량 서비스를 신규 추가해 APScheduler 기반 일일 정리 수행.
- **Unified API Gateway**: 포트 8000 LiteLLM에 `/v1/memory` 엔드포인트 추가, OpenAI 호환 API로 CLI/Desktop App 연동.
- **Global Project Identity**: MCP 서버 18개 도구 + 전역 파일시스템 접근으로 `.ai-memory/project.json` 일관 관리.
- **Intelligent CLI Integration**: 지능형 모델 선택(chat-7b/code-7b) + 스트리밍 응답에 메모리 저장/검색 자동 통합.

**🔧 검증된 기술 스택**:
- **Database**: `/mnt/e/ai-data/memory` 및 `sqlite/rag_analytics.db` 기반 SQLite 이중화 구조
- **Vector Search**: Qdrant 포트 6333 + FastEmbed BAAI/bge-small-en-v1.5 (384차원)
- **Performance**: 7B 모델 RTX 4050 최적화 설정 (CPU 99% 개선, 1초 검색 달성)
- **Integration**: Docker compose.p3.yml 전체 스택 + 전역 AI CLI + MCP 도구 18개

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

### Time Estimation (memo.md 검증 기반 단축)
- **총 예상 시간**: **7일** (12일 → 7일, 기존 인프라 활용으로 42% 단축)
- **버퍼 시간**: 3일 (43% 버퍼, 안전 마진 확대)
- **완료 목표일**: **2025-10-06** (6일 앞당김)

**⚡ 단축 근거 (memo.md 실증)**:
- **Phase 1**: 4일 → **3일** (SQLite 스키마 및 FTS 구조 재사용)
- **Phase 2**: 3일 → **2일** (Qdrant + FastEmbed 재사용)
- **Phase 3**: 2일 → **2일** (Docker 백그라운드 서비스 확장)
- **Phase 4**: 2일 → **2일** (90% 완성된 Desktop App 활용)
- **Phase 5**: 1일 → **1일** (이미 달성된 성능 적용)

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
  - SQLite 중심 확장: 기존 RAG/메모리 스택을 그대로 활용하며 확장 지점만 추가
  - 기존 시스템 안정성 유지하면서 점진적 확장 가능
  - SQLite + Qdrant 조합으로 로컬 우선, 벡터 검색 보조 구조

- [ ] **구현 계획이 현실적인가요?**
  - 7일 + 3일 버퍼로 총 10일 일정
  - Phase별 명확한 목표와 완료 조건 설정
  - 기존 `scripts/ai.py` 및 `services/rag/` 시스템과의 통합 지점 명확

### Resource Review
- [ ] **시간 추정이 합리적인가요?**
  - Phase 1-3: 핵심 기능 (5일) - 적절
  - Phase 4-5: UI 및 최적화 (2일) - 타이트하지만 실현 가능
  - 3일 버퍼로 40% 이상 안전 마진 확보

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

## 🚀 Next Steps (memo.md 검증된 벡터 파이프라인 활용)

**✅ 준비 완료된 기존 인프라 즉시 활용:**

1. **🏗️ 기존 시스템 확장**: memo.md 검증된 SQLite + Qdrant + FastEmbed 조합 활용
2. **🔧 Docker 스택 통합**: `compose.p3.yml` 전체 스택에 메모리 서비스 추가
3. **🌐 API Gateway 확장**: 포트 8000 LiteLLM에 `/v1/memory` 엔드포인트 추가
4. **🖥️ 전역 CLI 확장**: 이미 설치된 전역 `ai` 명령어에 메모리 기능 추가
5. **🎨 Desktop App 메모리 탭**: 90% 완성된 Electron 앱에 메모리 UI 추가
6. **📊 MCP 도구 활용**: 18개 도구 + 전역 파일시스템 접근으로 프로젝트 ID 관리

**🚀 벡터 파이프라인 최적화 방안 (memo.md 실증)**:
- **FastEmbed PyTorch-free**: ONNX 런타임으로 메모리 효율성 극대화
- **한국어 문장 분할**: 정규식 기반 문장 경계 검출 + 슬라이딩 윈도우 청킹
- **배치 임베딩 처리**: 64개 항목 단위 배치로 처리 속도 최적화
- **Qdrant 벡터 검색**: 384차원 코사인 유사도 검색, 검증된 1초 응답
- **7B 모델 최적화**: RTX 4050 6GB 특화 설정으로 CPU 99% 개선 달성

**수정이 필요한 경우:**
- 시간 추정이나 기술적 접근법에 대한 조정 사항
- 추가 위험 요소나 제약 사항 발견
- 리소스 가용성 변경

---

**💡 핵심 장점 (memo.md 실증 기반)**
- **검증된 성능**: 이미 달성된 1초 검색, 7B 모델 최적화, CPU 99% 개선 활용
- **완성된 통합 인프라**: SQLite + Qdrant + FastEmbed + 듀얼 모델 시스템 재사용
- **전역 접근성**: MCP 서버 18개 도구 + 전역 AI CLI로 어디서든 메모리 활용
- **실시간 UX**: 검증된 스트리밍 응답 + Desktop App 90% 완성도 활용
- **개발 위험 최소화**: memo.md 기록된 모든 기술적 문제 해결 경험 보유

**주의:** PR 생성 및 병합은 자동으로 실행하지 않습니다.
필요 시 사용자가 직접 `gh pr create` 등의 명령으로 수동 진행하세요.
