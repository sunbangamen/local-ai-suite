# ⚠️ Workflow 파일 원격 상태 확인

## 상황

**로컬 상태**: ✅ `.github/workflows/ci.yml`에 `workflow_dispatch` 트리거 설정 완료
**원격 상태**: ⏳ 최신 상태 확인 필요 (이전에 HTTP 422 오류 발생 보고)

---

## 원인

이전에 GitHub Actions CLI (`gh workflow run`) 실행 시 아래 오류가 보고됨:
```
Error: Workflow does not have 'workflow_dispatch' trigger
```

원격 저장소의 `.github/workflows/ci.yml`이 최신 상태가 아닐 가능성이 있으므로 수동 확인이 필요함

---

## 해결 방법 (3가지 옵션)

### ✅ 옵션 1: GitHub 웹 UI에서 워크플로우 파일 확인 및 보정 (권장)

**단계별 진행**:

1. **GitHub 레포지토리 접속**
   ```
   https://github.com/sunbangamen/local-ai-suite
   ```

2. **`.github/workflows/ci.yml` 파일로 이동**
   - 상단 검색 또는 파일 브라우저에서 찾기

3. `workflow_dispatch` 섹션 포함 여부를 확인
4. 누락된 경우에만 아래 블록을 추가하고 Commit

```yaml
  workflow_dispatch:
    inputs:
      run_load_tests:
        description: 'Run load tests'
        required: false
        default: 'false'
```

---

### ✅ 옵션 2: 로컬 파일을 원격에 강제 푸시 (고급)

**전제**: GitHub Personal Access Token with `workflow` scope 필요

```bash
# 현재 로컬 파일이 이미 올바름
# 다만 OAuth scope 이슈가 있어 푸시 불가

# 대신 GitHub 웹 UI를 통한 수동 편집 권장
```

---

### ✅ 옵션 3: 웹 UI에서 직접 워크플로우 트리거 (가능한 경우)

`workflow_dispatch` 없어도 다른 방법으로 실행:

1. **GitHub Actions 페이지**
   ```
   https://github.com/sunbangamen/local-ai-suite/actions
   ```

2. **왼쪽에서 "CI Pipeline" 선택**

3. **"Run workflow" 버튼 (있으면 클릭)**
   - 없으면 Option 1로 진행

---

## 추천 흐름 (사용자 제공)

### 1단계: 빠른 점검 (선택)
```bash
# 워크플로우 파일 상태 확인 후
gh workflow run ci.yml -f run_load_tests=true
```

### 2단계: 전체 워크플로우 실행
```
GitHub 웹 UI에서:
- CI Pipeline 선택
- issue-24 브랜치 대상
- "Run workflow" 실행
```

또는

```bash
# GitHub에서 수동 편집 후 자동 트리거 (push 시)
git push origin issue-24
```

### 3단계: 결과 확인
- Load tests + regression detection job 성공 여부 확인
- `regression-analysis.md` 등 아티팩트 확인

---

## 현재 로컬 파일 상태 확인

✅ 로컬 `.github/workflows/ci.yml` 확인:
```bash
grep -A 5 "workflow_dispatch:" .github/workflows/ci.yml
```

**결과**:
```
workflow_dispatch:
  inputs:
    run_load_tests:
      description: 'Run load tests'
      required: false
      default: 'false'
```

✅ 로컬 파일은 최신 상태 → 원격이 동일한지 확인하세요

---

## 다음 단계

1. ⏳ **GitHub 웹 UI에서 워크플로우 파일 상태 확인** (5분)
   - Option 1 절차 참고

2. ✅ **수정 후 CI Pipeline 워크플로우 실행**
   - 웹 UI에서 "Run workflow" 클릭

3. ✅ **결과 확인** (약 76분 대기)
   - Load tests + regression detection 성공 확인

4. ✅ **최종 보고서 작성**
   - Production Readiness 100% 달성 선언

---

## 파일 비교

### 로컬 (올바름) ✅
```yaml
on:
  push: ...
  pull_request: ...
  schedule: ...
  workflow_dispatch:  ← ✅ 있음
    inputs:
      run_load_tests: ...
```

### 원격 (확인 필요) ⏳
```yaml
on:
  push: ...
  pull_request: ...
  schedule: ...
  # ⏳ workflow_dispatch 확인 필요
```

---

## 예상 완료 후 흐름

1. 웹 UI 편집: 5분
2. GitHub Actions 실행: 76분
3. 결과 확인: 5분
4. 최종 보고서: 5분

**총 소요**: 약 90분 + 작업 시간

---

**상태**: 원격 워크플로우 파일 업데이트 필요 (GitHub 웹 UI)
**다음**: Option 1 참고하여 수동 편집 진행
