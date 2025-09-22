# GitHub Issue Creation Command

**Usage:** `생성할 이슈 내용을 입력하세요`

**Input:** $ARGUMENT

---

## Issue Details

### Title
`[타입] $ARGUMENT의 핵심 요약`

**타입 옵션:**
- `[Feature]` - 새로운 기능
- `[Bug]` - 버그 수정
- `[Enhancement]` - 기존 기능 개선
- `[Docs]` - 문서 관련
- `[Refactor]` - 코드 리팩토링
- `[Test]` - 테스트 관련
- `[Chore]` - 기타 작업

### Description

#### 📋 Overview
**문제/요구사항**: $ARGUMENT

**배경**: 
- [이 이슈가 필요한 이유]
- [현재 상황의 문제점]
- [해결했을 때의 기대효과]

#### 🎯 Acceptance Criteria
**완료 조건:**
- [ ] [구체적인 완료 기준 1]
- [ ] [구체적인 완료 기준 2]
- [ ] [구체적인 완료 기준 3]

**Definition of Done:**
- [ ] 기능 구현 완료
- [ ] 단위 테스트 작성
- [ ] 코드 리뷰 통과
- [ ] 문서 업데이트
- [ ] QA 테스트 통과

#### 🔧 Technical Requirements

**기술 스택:**
- [사용할 기술/프레임워크]
- [필요한 라이브러리]
- [API/서비스 연동]

**구현 고려사항:**
- [성능 요구사항]
- [보안 고려사항]
- [호환성 요구사항]
- [확장성 고려사항]

#### 📝 Implementation Plan

**Phase 1: 분석 및 설계**
- [ ] 요구사항 상세 분석
- [ ] 기술 스택 확정
- [ ] API 설계 (필요시)
- [ ] UI/UX 모크업 (필요시)

**Phase 2: 개발**
- [ ] 핵심 기능 구현
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성

**Phase 3: 테스트 및 배포**
- [ ] QA 테스트
- [ ] 성능 테스트
- [ ] 문서 작성
- [ ] 배포 준비

#### 🧪 Test Cases

**테스트 시나리오:**
1. **정상 케이스**: [예상되는 일반적 사용 시나리오]
2. **엣지 케이스**: [경계값이나 특수한 상황]
3. **에러 케이스**: [예외 상황 처리]

**테스트 데이터:**
- [필요한 테스트 데이터 설명]
- [목업 데이터 요구사항]

#### 🔗 Related Issues/PRs
- Related to: #[이슈번호] - [관련 이슈 설명]
- Depends on: #[이슈번호] - [의존성 이슈]
- Blocks: #[이슈번호] - [이 이슈가 차단하는 작업]

#### 📚 Resources & References
- [관련 문서 링크]
- [참고할 레퍼런스]
- [디자인 가이드라인]
- [API 문서]

#### 🚨 Risks & Considerations
| 위험 요소 | 가능성 | 영향도 | 대응 방안 |
|-----------|--------|--------|-----------|
| [기술적 위험] | [High/Medium/Low] | [High/Medium/Low] | [구체적 대응책] |
| [일정 위험] | [High/Medium/Low] | [High/Medium/Low] | [구체적 대응책] |
| [리소스 위험] | [High/Medium/Low] | [High/Medium/Low] | [구체적 대응책] |

#### 🏷️ Labels
**Suggested Labels:**
- `priority: [high/medium/low]`
- `type: [feature/bug/enhancement/docs]`
- `component: [frontend/backend/database/infra]`
- `effort: [S/M/L/XL]` (Small/Medium/Large/Extra Large)
- `status: [todo/in-progress/review/done]`

#### 👥 Assignment
**담당자**: @[github-username]
**리뷰어**: @[reviewer-username]
**예상 소요시간**: [X일/X주]

#### 📅 Timeline
- **시작 예정일**: [YYYY-MM-DD]
- **완료 목표일**: [YYYY-MM-DD]
- **마일스톤**: [v1.0.0 등]

---

## Quick Templates

### 🐛 Bug Report Template
```
## Bug Description
[버그 상세 설명]

## Steps to Reproduce
1. [재현 단계 1]
2. [재현 단계 2]
3. [재현 단계 3]

## Expected Behavior
[예상되는 정상 동작]

## Actual Behavior
[실제 발생한 문제]

## Environment
- OS: [운영체제]
- Browser: [브라우저 정보]
- Version: [버전 정보]

## Screenshots
[스크린샷이나 에러 로그]
```

### ✨ Feature Request Template
```
## Feature Summary
[기능 요약]

## User Story
As a [사용자 역할], I want [원하는 기능] so that [목적/이유].

## Mockups/Designs
[디자인 파일이나 와이어프레임]

## Business Value
[비즈니스 가치나 우선순위 근거]
```

---

**💡 사용 팁**
- 이슈 생성 전 중복 이슈 검색
- 명확하고 구체적인 제목 작성
- 스크린샷이나 코드 스니펫 적극 활용
- 정기적인 진행상황 업데이트

#### 🌀 Branch & Commit Conventions
- 브랜치명: `feature/<short-slug>` (예: `feature/photo-upload`)
- 커밋 메시지(Conventional Commits): `type(scope): subject`
  - 예) `feat(photos): 사진 업로드 API 추가`
  - type: feat, fix, docs, refactor, test, chore …
  - scope: photos, events, infra 등
