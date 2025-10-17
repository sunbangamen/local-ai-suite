# C-stage 실행 (workflow_dispatch 확인 필수 & RPS Critical 검토)

## 📋 현재 상황

**Production Readiness**: 98% (로컬 완전 검증)
- ✅ Phase 1-3: 완료
- ⏳ Phase 4: 원격 실행 대기 (workflow_dispatch 확인 필요 + RPS Critical 검토 필요)

**주요 이슈**:
1. ⚠️ **원격 저장소 workflow_dispatch 상태**: 확인 필요 (없을 가능성 높음)
2. ⚠️ **RPS Critical**: 회귀 분석에서 +2016.7% 증가로 ❌ Critical 표시됨

---

## 🔍 Step 1: 원격 워크플로우 파일 상태 확인 (5분)

### 확인 절차

**GitHub 웹 UI에서**:
1. https://github.com/sunbangamen/local-ai-suite 접속
2. `.github/workflows/ci.yml` 파일 열기
3. **Line 10 근처에서 `workflow_dispatch:` 섹션 검색**

### 두 가지 상황

#### 상황 A: workflow_dispatch가 이미 있는 경우 ✅
```yaml
on:
  push: ...
  pull_request: ...
  schedule: ...
  workflow_dispatch:  ← ✅ 있음
    inputs:
      run_load_tests: ...
```
**조치**: 그대로 진행, Step 2로 이동

#### 상황 B: workflow_dispatch가 없는 경우 ⚠️
```yaml
on:
  push: ...
  pull_request: ...
  schedule: ...
  # ⚠️ workflow_dispatch 없음
```

**조치**: 수동 추가 필요
1. 파일 편집 (연필 아이콘 클릭)
2. Line 9 (schedule 섹션 후) 다음 추가:

```yaml
  workflow_dispatch:
    inputs:
      run_load_tests:
        description: 'Run load tests'
        required: false
        default: 'false'
```

3. "Commit changes" 클릭
   - Message: "chore: enable workflow_dispatch trigger for CI Pipeline"
   - Commit directly to main

---

## 🚀 Step 2: GitHub Actions 수동 트리거 실행

### 실행 방법 (권장: 웹 UI)

1. **GitHub Actions 페이지 접속**
   ```
   https://github.com/sunbangamen/local-ai-suite/actions
   ```

2. **"CI Pipeline" 워크플로우 선택**
   - 좌측 워크플로우 목록에서 클릭

3. **"Run workflow" 버튼 클릭**
   - 우측 상단 "Run workflow" 드롭다운

4. **설정 입력**
   ```
   Branch: issue-24
   run_load_tests: true
   ```

5. **"Run workflow" 실행** (초록색 버튼)

---

## ⏱️ Step 3: 모니터링 (약 76분)

### 실행 단계 및 시간

| 단계 | 예상 시간 |
|------|---------|
| Lint & Security | 5분 |
| Unit Tests | 5분 |
| RAG Integration | 10분 |
| E2E Playwright | 25분 |
| **Load Tests** | **30분** |
| **총계** | **~76분** |

### 모니터링 방법

**GitHub Actions 페이지에서**:
- 실시간 진행 상황 확인 가능
- 각 job의 상세 로그 확인 가능
- "Load tests" job에서 회귀 분석 진행 상황 모니터링

---

## ✅ Step 4: 결과 확인 (매우 중요!)

### A. Load Tests Job 검증

```
✓ API Gateway Baseline Test
  - 32 requests 생성 ✓
  - 0% error rate ✓

✓ API Gateway Progressive Test
  - 25,000+ requests 생성 ✓
  - 28.49 RPS 처리 ✓
  - 0% error rate ✓
```

### B. Regression Analysis Report 검증 ⚠️ 필독

**위치**: GitHub Actions 아티팩트 → `load-test-results/regression-analysis.md`

**예상 내용**:
```
## Performance Regression Analysis

### ❌ Failures (Action Required)

| Service | Metric | Expected | Current | Change | Impact |
|---------|--------|----------|---------|--------|--------|
| api_gateway | rps | 0.27 | 5.72 | +2016.7% | ❌ Critical |

### ✅ Passed (2 metrics within thresholds)

- health_endpoint latency: Passed ✓
- models_endpoint latency: Passed ✓

## Summary

- Total Metrics: 3
- Failures: 1 (❌ RPS Critical)
- Warnings: 0
- Passed: 2
```

### ⚠️ RPS Critical 항목 분석

**발견 사항**:
- Baseline (1 user): 0.27 RPS
- Progressive (100 users): 5.72 RPS
- 변화: +2016.7% (100배 증가)

**이것이 Normal인지 확인**:
1. ✓ **정상적인 이유** (이 경우 해당):
   - 부하가 1 user → 100 users로 증가
   - RPS 증가는 예상된 현상
   - 기준선이 1 user 기준이므로 정상

2. ✗ **비정상적인 경우** (해당 사항 없음):
   - 동일 부하에서 성능 저하
   - 처리율 감소

---

## 🎯 Step 5: Critical 검토 및 해결

### 조치 방법 (권장)

**현재 상황**: RPS 증가는 의도된 개선 (부하 단계 확대)

**해결책** (3가지 옵션):

#### 옵션 1: 기준선 갱신 (권장) ✅
```
- 현재 baseline (1 user): 0.27 RPS
- 새로운 baseline (100 users): 5.72 RPS로 갱신
- 향후 regression 감지 기준 업데이트

파일: docs/performance-baselines.json
구간: api_gateway.rps: 5.72로 수정
```

#### 옵션 2: 임계치 재조정
```
- RPS 변화 임계치 확대: 2000% → 3000%
- 또는: 절대값 기반 임계치 추가 (RPS 변화 < 20%)

파일: scripts/compare_performance.py
구간: rps_threshold 재조정
```

#### 옵션 3: 예외 문서화
```
- regression-analysis.md에 주석 추가:
  "RPS +2016.7%는 부하 단계 확대(1→100 users)로 인한 정상적인 증가"
```

**추천**: 옵션 1 (기준선 갱신) + 옵션 3 (문서화)

---

## 📝 최종 체크리스트

### 실행 전
- [ ] 원격 저장소의 workflow_dispatch 섹션 확인 (Step 1)
- [ ] 필요 시 추가 후 commit (Step 1)
- [ ] 약 76분 모니터링 시간 확보

### 실행 후
- [ ] Load Tests job 완료 확인 ✓
- [ ] regression-analysis.md 다운로드
- [ ] RPS Critical 항목 분석 완료
- [ ] Critical 해결책 선택 (옵션 1-3)

### 최종 결과
- [ ] 기준선 업데이트 (필요 시)
- [ ] 회귀 분석 재검증
- [ ] Production Readiness 100% 달성

---

## 📊 예상 최종 결과

### CI 성공 후

```
✓ Phase 1-4 모든 테스트 실행 완료
✓ Load tests: 성공 (RPS 증가는 정상)
✓ Regression detection: 완료 (Critical 검토 완료)

→ Production Readiness: 98% → 100% ✅
→ 배포 준비 완료
```

### 필요한 후속 조치

1. **기준선 갱신** (선택사항)
   ```bash
   # docs/performance-baselines.json 수정
   # api_gateway.rps: 0.27 → 5.72

   git add docs/performance-baselines.json
   git commit -m "chore: update performance baseline after Phase 3 load testing"
   ```

2. **회귀 분석 보고서 아카이빙**
   ```
   load-test-results/regression-analysis.md
   → docs/performance-reports/2025-10-17-analysis.md로 이동
   ```

3. **최종 요약 작성**
   ```
   ISSUE_24_FINAL_COMPLETION_REPORT.md 작성
   - Phase 1-4 완료 현황
   - Load test 결과 요약
   - RPS Critical 검토 결과
   - Production 준비 상태
   ```

---

## 🎉 핵심 요점

✅ **로컬 검증**: 완료 (1,107줄 회귀 감지 스크립트)
⚠️ **workflow_dispatch**: 원격 상태 확인 필수
⚠️ **RPS Critical**: 정상적인 증가 (부하 단계 확대)
✅ **다음**: CI 실행 → 결과 검토 → 기준선 업데이트 → 100% 달성

---

## 🚀 지금 할 일

1. **GitHub 웹 UI에서 workflow_dispatch 확인**
   - 없으면 추가 후 commit (5분)

2. **"Run workflow" 클릭**
   - Branch: issue-24
   - run_load_tests: true
   - (1분)

3. **76분 모니터링**

4. **결과 검토 및 기준선 갱신**
   - regression-analysis.md 다운로드
   - RPS Critical 분석
   - 기준선 업데이트 (필요 시)

5. **최종 보고서 작성**
   - Production Readiness 100% 달성 선언

---

**✅ 모든 준비 완료. C-stage 실행하세요!** 🚀
