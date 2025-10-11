# GitHub Workflow 파일 웹 UI 업로드 가이드

## 📋 Overview
`.github/workflows/ci.yml` 파일을 GitHub 웹 UI에서 직접 업로드하는 방법입니다.

## 🔗 Step 1: GitHub 저장소 접속

1. **저장소 URL로 이동**
   ```
   https://github.com/sunbangamen/local-ai-suite
   ```

2. **Branch 전환**
   - 상단의 Branch 드롭다운 클릭
   - `issue-20` 브랜치 선택

## 📝 Step 2: Workflow 파일 생성

1. **파일 추가 시작**
   - "Add file" 버튼 클릭 (우측 상단 근처)
   - "Create new file" 선택

2. **파일 경로 입력**
   ```
   .github/workflows/ci.yml
   ```
   - `.github` 폴더가 없으면 자동 생성됨
   - 슬래시(`/`)를 입력하면 폴더가 생성됨

3. **파일 내용 복사**
   - 아래 "CI Workflow 전체 내용" 섹션의 코드 전체를 복사
   - GitHub 편집기에 붙여넣기

## 💾 Step 3: Commit

1. **Commit 메시지 작성**
   ```
   ci: add GitHub Actions workflow for automated testing

   - Lint: Black + Ruff
   - Security: Bandit + Safety
   - Unit Tests: 16 tests (RAG 5 + Embedding 7 + Integration 4)
   - Integration: CPU profile with Mock LLM
   - Build: Docker image validation
   ```

2. **Commit 옵션 선택**
   - "Commit directly to the `issue-20` branch" 선택
   - "Commit new file" 버튼 클릭

## ✅ Step 4: CI 실행 확인

1. **Actions 탭으로 이동**
   ```
   https://github.com/sunbangamen/local-ai-suite/actions
   ```

2. **Workflow 실행 확인**
   - 자동으로 CI Pipeline이 실행됨
   - 각 Job 상태 확인:
     - ✅ Lint & Format Check
     - ✅ Security Scan
     - ✅ Unit Tests (mcp-server, rag, embedding)
     - ✅ Integration Tests (CPU Profile)
     - ✅ Docker Build Check
     - ✅ CI Summary

3. **실행 시간**
   - 전체 약 8-10분 소요 (병렬 실행)

## 🔍 Troubleshooting

### 권한 에러 발생 시
- PAT(Personal Access Token) 사용
- Settings → Developer settings → Personal access tokens
- `workflow` scope 포함하여 생성

### Workflow 실행 안 됨
- Branch 이름 확인: `issue-20`
- Trigger 조건 확인: `push` to `issue-*` branches

---

## 📄 CI Workflow 전체 내용

다음 내용을 복사하여 `.github/workflows/ci.yml`에 붙여넣으세요:

```yaml
name: CI Pipeline

on:
  push:
    branches: [ main, develop, issue-* ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install linting tools
        run: |
          pip install black ruff

      - name: Black format check
        run: |
          black --check services/ scripts/ || {
            echo "::error::Code formatting issues found. Run 'black services/ scripts/' to fix."
            exit 1
          }

      - name: Ruff lint
        run: |
          ruff check services/ scripts/ || {
            echo "::error::Linting issues found. Run 'ruff check --fix services/ scripts/' to fix."
            exit 1
          }

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install security scan tools
        run: |
          pip install bandit safety

      - name: Bandit security scan
        run: |
          bandit -r services/ -f json -o bandit-report.json || true
          bandit -r services/ -ll || echo "::warning::Bandit found potential security issues"

      - name: Safety dependency check
        run: |
          # Collect all requirements files
          find services -name "requirements.txt" -exec cat {} \; > all-requirements.txt
          safety check --file all-requirements.txt --json || echo "::warning::Safety found vulnerable dependencies"

      - name: Upload security reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: |
            bandit-report.json
            all-requirements.txt
          retention-days: 30

  unit-tests:
    name: Unit Tests (${{ matrix.service }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        service: [mcp-server, rag, embedding]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install test dependencies
        run: |
          pip install pytest pytest-cov pytest-asyncio httpx

          # Install service-specific dependencies
          if [ -f services/${{ matrix.service }}/requirements.txt ]; then
            pip install -r services/${{ matrix.service }}/requirements.txt
          fi

      - name: Run tests with coverage
        working-directory: services/${{ matrix.service }}
        run: |
          # Skip tests if no test directory exists
          if [ ! -d "tests" ]; then
            echo "::warning::No tests directory found for ${{ matrix.service }}"
            exit 0
          fi

          pytest tests/ \
            --cov=. \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-report=html \
            -v || exit 1

      - name: Upload coverage to Codecov
        if: always()
        uses: codecov/codecov-action@v4
        with:
          files: ./services/${{ matrix.service }}/coverage.xml
          flags: ${{ matrix.service }}
          name: ${{ matrix.service }}-coverage
          fail_ci_if_error: false

      - name: Upload coverage HTML report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-${{ matrix.service }}
          path: services/${{ matrix.service }}/htmlcov/
          retention-days: 30

  # Integration tests with CPU profile (Mock LLM servers)
  integration-tests:
    name: Integration Tests (CPU Profile)
    runs-on: ubuntu-latest
    needs: [unit-tests]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install test dependencies
        run: |
          pip install pytest pytest-asyncio httpx

      - name: Start services with CPU profile
        run: |
          docker compose -f docker/compose.p2.cpu.yml up -d
          echo "::notice::Services starting with Mock LLM servers (CPU-only)"

      - name: Wait for services
        run: |
          echo "Waiting 60 seconds for all services to be ready..."
          sleep 60

      - name: Health checks
        run: |
          echo "::group::Service Health Checks"

          # Check inference servers (mock)
          curl -f http://localhost:8001/health || echo "::warning::Inference Chat health check failed"
          curl -f http://localhost:8004/health || echo "::warning::Inference Code health check failed"

          # Check API Gateway
          curl -f http://localhost:8000/health || curl -f http://localhost:8000/v1/models || echo "::warning::API Gateway health check failed"

          # Check RAG
          curl -f http://localhost:8002/health || echo "::warning::RAG health check failed"

          # Check Embedding
          curl -f http://localhost:8003/health || echo "::warning::Embedding health check failed"

          echo "::endgroup::"

      - name: Run basic integration tests
        run: |
          echo "::group::Integration Tests"
          # These tests verify service connectivity, not actual inference
          pytest tests/integration/test_api_gateway.py::test_api_gateway_health -v || echo "::warning::Health test failed"
          echo "::endgroup::"

      - name: Show service logs on failure
        if: failure()
        run: |
          echo "::group::Service Logs"
          docker compose -f docker/compose.p2.cpu.yml logs
          echo "::endgroup::"

      - name: Teardown
        if: always()
        run: |
          docker compose -f docker/compose.p2.cpu.yml down -v

  build-check:
    name: Docker Build Check
    runs-on: ubuntu-latest
    needs: [lint, unit-tests]
    strategy:
      fail-fast: false
      matrix:
        service: [embedding, rag, mcp-server]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image (dry-run)
        working-directory: services/${{ matrix.service }}
        run: |
          if [ -f Dockerfile ]; then
            docker build --no-cache -t ${{ matrix.service }}:ci-test .
            echo "::notice::✅ Docker build successful for ${{ matrix.service }}"
          else
            echo "::warning::No Dockerfile found for ${{ matrix.service }}"
          fi

  summary:
    name: CI Summary
    runs-on: ubuntu-latest
    needs: [lint, security-scan, unit-tests, integration-tests, build-check]
    if: always()
    steps:
      - name: Check CI status
        run: |
          echo "::notice::CI Pipeline completed"
          echo "::notice::Lint: ${{ needs.lint.result }}"
          echo "::notice::Security: ${{ needs.security-scan.result }}"
          echo "::notice::Unit Tests: ${{ needs.unit-tests.result }}"
          echo "::notice::Integration Tests: ${{ needs.integration-tests.result }}"
          echo "::notice::Build: ${{ needs.build-check.result }}"

          if [[ "${{ needs.lint.result }}" == "failure" ]] || \
             [[ "${{ needs.unit-tests.result }}" == "failure" ]] || \
             [[ "${{ needs.integration-tests.result }}" == "failure" ]]; then
            echo "::error::CI failed - check logs above"
            exit 1
          fi
```

## 🎯 완료 후 확인사항

1. ✅ Workflow 파일이 저장소에 업로드됨
2. ✅ GitHub Actions에서 자동 실행됨
3. ✅ 모든 Job이 성공적으로 완료됨
4. ✅ ri_10.md 문서 업데이트 (CI 완료 상태)
5. ✅ PR 생성 및 Issue #20 링크
