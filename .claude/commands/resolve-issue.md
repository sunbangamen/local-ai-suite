# GitHub Issue Analysis & Solution Planning Command

**Usage:** `해결할 GitHub 이슈 번호를 입력하세요`

**Input:** $ARGUMENT (GitHub Issue Number)

---

## Step 1: Issue Retrieval & Analysis

### Fetch Issue Details
```bash
# GitHub CLI를 사용해 이슈 정보 가져오기
gh issue view $ARGUMENT --json title,body,labels,assignees,milestone,state,createdAt,updatedAt
```

### Issue Information Summary
**이슈 번호**: #$ARGUMENT
**제목**: [이슈 제목]
**상태**: [Open/Closed]
**생성일**: [생성 날짜]
**담당자**: [담당자 목록]
**라벨**: [라벨 목록]
**마일스톤**: [마일스톤 정보]

### Issue Content Analysis
**문제 유형**: [Bug/Feature/Enhancement/Documentation/등]
**우선순위**: [High/Medium/Low]
**복잡도**: [Simple/Medium/Complex]

**핵심 요구사항**:
- [요구사항 1]
- [요구사항 2]
- [요구사항 3]

**기술적 제약사항**:
- [제약사항 1]
- [제약사항 2]

---

## Step 2: Technical Investigation

### Code Analysis Required
```bash
# 관련 파일들 검색
rg -l "관련키워드" --type js --type py --type go
```

**영향 범위 분석**:
- **Frontend**: [영향받는 컴포넌트/페이지]
- **Backend**: [영향받는 API/서비스]
- **Database**: [영향받는 테이블/스키마]
- **Infrastructure**: [영향받는 배포/설정]

### Dependency Check
**의존성 이슈**:
- Depends on: [의존하는 다른 이슈들]
- Blocks: [이 이슈가 블록하는 작업들]
- Related to: [관련 이슈들]

---

## Step 3: Solution Strategy

### Approach Options
**Option 1: [접근법 1 이름]**
- **장점**: [장점들]
- **단점**: [단점들]
- **예상 시간**: [개발 시간]
- **위험도**: [High/Medium/Low]

**Option 2: [접근법 2 이름]**
- **장점**: [장점들]
- **단점**: [단점들]
- **예상 시간**: [개발 시간]
- **위험도**: [High/Medium/Low]

**Option 3: [접근법 3 이름]**
- **장점**: [장점들]
- **단점**: [단점들]
- **예상 시간**: [개발 시간]
- **위험도**: [High/Medium/Low]

### Recommended Approach
**선택한 접근법**: Option [X] - [접근법 이름]
**선택 이유**: [구체적인 선택 근거]

---

## Step 4: Detailed Implementation Plan

### Phase 1: 준비 및 설계 (Day 1-2)
**목표**: 구현을 위한 기반 작업 완료

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 요구사항 재검토 | 이슈의 모든 요구사항 상세 분석 | [담당자] | 요구사항 명세서 완성 | Low |
| 기술 스펙 설계 | API/컴포넌트 구조 설계 | [담당자] | 설계 문서 완성 | Medium |
| 개발 환경 준비 | 필요한 도구/라이브러리 설정 | [담당자] | 로컬 환경 구동 확인 | Low |

### Phase 2: 핵심 구현 (Day 3-5)
**목표**: 주요 기능 개발 완료

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| [핵심 기능 1] | [구체적 구현 내용] | [담당자] | [완료 기준] | [위험도] |
| [핵심 기능 2] | [구체적 구현 내용] | [담당자] | [완료 기준] | [위험도] |
| [핵심 기능 3] | [구체적 구현 내용] | [담당자] | [완료 기준] | [위험도] |

### Phase 3: 테스트 및 통합 (Day 6-7)
**목표**: 품질 보증 및 배포 준비

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 단위 테스트 작성 | 주요 함수/컴포넌트 테스트 | [담당자] | 테스트 커버리지 80%+ | Low |
| 통합 테스트 | 전체 플로우 테스트 | [담당자] | 사용자 시나리오 통과 | Medium |
| 코드 리뷰 | 팀원 코드 리뷰 요청 | [담당자] | 리뷰 승인 완료 | Low |

### Phase 4: 배포 및 검증 (Day 8)
**목표**: 운영 환경 배포 및 검증

| Task | Description | Owner | DoD | Risk |
|------|-------------|-------|-----|------|
| 스테이징 배포 | 테스트 환경 배포 | [담당자] | 스테이징 정상 동작 | Low |
| QA 테스트 | 최종 품질 검증 | [QA] | 모든 테스트 케이스 통과 | Medium |
| 운영 배포 | 프로덕션 배포 | [담당자] | 운영 환경 정상 동작 | High |

---

## Step 5: Risk Assessment & Mitigation

### High Risk Items
| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| [위험 요소 1] | [High/Medium/Low] | [High/Medium/Low] | [구체적 대응 방안] |
| [위험 요소 2] | [High/Medium/Low] | [High/Medium/Low] | [구체적 대응 방안] |

### Technical Challenges
**예상 기술적 난점**:
1. [기술적 챌린지 1] - [해결 방안]
2. [기술적 챌린지 2] - [해결 방안]
3. [기술적 챌린지 3] - [해결 방안]

### Rollback Plan
**롤백 시나리오**:
- [문제 상황 1] → [롤백 절차]
- [문제 상황 2] → [롤백 절차]

---

## Step 6: Resource Requirements

### Human Resources
- **개발자**: [필요 인원 및 스킬셋]
- **리뷰어**: [리뷰 담당자]
- **QA**: [테스트 담당자]

### Technical Resources
- **개발 도구**: [필요한 도구/라이브러리]
- **테스트 환경**: [테스트 서버/도구]
- **모니터링**: [성능/에러 모니터링 도구]

### Time Estimation
- **총 예상 시간**: [X일]
- **버퍼 시간**: [Y일] (예상 시간의 20-30%)
- **완료 목표일**: [YYYY-MM-DD]

---

## Step 7: Quality Assurance Plan

### Test Strategy
**테스트 레벨**:
- **Unit Tests**: [단위 테스트 전략]
- **Integration Tests**: [통합 테스트 전략]
- **E2E Tests**: [엔드투엔드 테스트 전략]

### Test Cases
```gherkin
Feature: [기능명]
  
  Scenario: [시나리오 1]
    Given [전제조건]
    When [실행동작]
    Then [예상결과]
  
  Scenario: [시나리오 2]
    Given [전제조건]
    When [실행동작]
    Then [예상결과]
```

### Performance Criteria
- **응답시간**: [목표 응답시간]
- **처리량**: [목표 TPS/동시사용자]
- **리소스 사용률**: [CPU/메모리 목표]

---

## Step 8: Communication Plan

### Status Updates
- **일일 스탠드업**: [진행상황 공유]
- **이슈 댓글 업데이트**: [주요 마일스톤마다]
- **슬랙/팀즈 채널**: [실시간 소통]

### Stakeholder Notification
- **프로젝트 매니저**: [진행률 보고]
- **관련 팀**: [영향도 공유]
- **사용자/고객**: [배포 일정 안내]

---

## 📋 User Review Checklist

**다음 항목들을 검토해주세요:**

### Planning Review
- [ ] **이슈 분석이 정확한가요?** 
  - 핵심 요구사항이 누락된 것은 없나요?
  - 기술적 제약사항이 제대로 파악되었나요?

- [ ] **선택한 해결 방안이 적절한가요?**
  - 다른 접근법과 비교했을 때 최선인가요?
  - 기술적/비즈니스적 트레이드오프가 합리적인가요?

- [ ] **구현 계획이 현실적인가요?**
  - 각 Phase별 작업량이 적절한가요?
  - 의존성과 순서가 올바르게 설정되었나요?

### Resource Review  
- [ ] **시간 추정이 합리적인가요?**
  - 각 작업의 예상 시간이 현실적인가요?
  - 버퍼 시간이 충분히 확보되었나요?

- [ ] **필요한 리소스가 확보 가능한가요?**
  - 담당자들의 일정이 확보되었나요?
  - 필요한 도구/환경이 준비되었나요?

### Risk Review
- [ ] **위험 요소가 충분히 식별되었나요?**
  - 놓친 기술적/일정적 위험은 없나요?
  - 각 위험에 대한 대응 방안이 구체적인가요?

- [ ] **롤백 계획이 현실적인가요?**
  - 문제 발생 시 빠른 복구가 가능한가요?

### Quality Review
- [ ] **테스트 전략이 충분한가요?**
  - 모든 기능과 엣지 케이스가 커버되나요?
  - 성능/보안 테스트가 포함되었나요?

---

## 🚀 Next Steps

**검토 완료 후 진행할 작업:**

1. **Plan Approval**: 위 검토를 통과하면 계획 승인
2. **Issue Update**: GitHub 이슈에 상세 계획 댓글로 추가
3. **Task Creation**: 세부 작업들을 별도 이슈/태스크로 분할
4. **Timeline Setup**: 프로젝트 관리 도구에 일정 등록
5. **Kickoff Meeting**: 팀원들과 킥오프 미팅 진행

**수정이 필요한 경우:**
- 구체적인 수정 사항을 알려주시면 계획을 업데이트하겠습니다.
- 추가 조사가 필요한 부분이 있다면 먼저 조사 후 계획을 보완하겠습니다.

---

**💡 피드백 요청**
이 계획에 대해 어떤 부분을 수정하거나 보완해야 할까요? 특히 우려되는 부분이나 추가로 고려해야 할 사항이 있다면 알려주세요.

**주의:** PR 생성 및 병합은 자동으로 실행하지 않습니다.  
필요 시 사용자가 직접 `gh pr create` 등의 명령으로 수동 진행하세요.
