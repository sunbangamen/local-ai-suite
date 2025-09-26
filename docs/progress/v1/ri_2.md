# Issue #3 Resolution Plan: MCP 서버 보안 및 경로 처리 개선

**Generated**: 2025-09-26
**Issue**: [#3] MCP 서버 보안 및 경로 처리 개선 - 3가지 핵심 이슈 해결
**Status**: Planning Phase
**Priority**: High (Security Issues)

---

## 📋 Issue Analysis Summary

### Core Requirements
1. **보안 필터 개선**: 과도하게 제한적인 필터 해결 (`import os` 등 기본 모듈 차단 해제)
2. **경로 처리 로직 수정**: working_dir 처리 문제 및 상대경로 해석 오동작 수정
3. **JSON 문자셋 처리**: 한국어 포함 요청의 이스케이프 에러 해결

### Technical Investigation Results

**Current Implementation Issues**:

#### 1. Security Filter (services/mcp-server/app.py:248-256)
```python
# 현재 구현: 과도하게 제한적
dangerous_imports = ["os", "sys", "subprocess", "shutil", "requests"]
if any(f"import {module}" in code or f"from {module}" in code for module in dangerous_imports):
    # 차단 처리 - 기본 모듈도 차단됨
```

**문제점**:
- `import os` 등 기본 Python 모듈도 차단
- 동적 import 우회 시도 탐지 불가능
- 화이트리스트 접근법 부재

#### 2. Path Processing (services/mcp-server/app.py:65-82)
```python
def resolve_path(path: str, working_dir: Optional[str] = None) -> Path:
    if working_dir and not os.path.isabs(path):
        full_path = Path(working_dir) / path
    elif os.path.isabs(path):
        full_path = Path(HOST_ROOT + path) if not path.startswith(HOST_ROOT) else Path(path)
    else:
        full_path = Path(PROJECT_ROOT) / path
    return full_path.resolve()  # resolve() 만으로는 탈출 방지 불충분
```

**문제점**:
- 심볼릭 링크를 통한 경로 탈출 가능
- 작업공간 경계 검증 미흡
- `../../../etc/passwd` 같은 직접적 탈출 시도 차단 불완전

#### 3. JSON Processing (scripts/ai.py:90-92)
```python
headers = {
    "Content-Type": "application/json"  # charset 명시 없음
}
# JSON 요청에서 한국어 처리 시 인코딩 문제 발생
```

**문제점**:
- UTF-8 charset 명시 없음
- 한국어 등 멀티바이트 문자 이스케이프 에러
- 클라이언트-서버 간 인코딩 불일치

---

## 🎯 Solution Strategy

### Selected Approach: AST 기반 커스텀 검증기 + 안전 API 래퍼

**선택 이유**:
- 보안성과 성능의 균형점
- 외부 의존성 없이 자체 제어 가능
- 점진적 개선 및 확장 가능
- 이슈의 3가지 문제 모두 해결 가능

### Alternative Approaches Considered
1. **RestrictedPython**: 강력한 보안성, 하지만 성능 오버헤드 및 복잡성
2. **개선된 키워드 필터**: 빠른 구현, 하지만 보안 수준 제한적

---

## 🚀 Implementation Plan

### Phase 1: 준비 및 설계 (Day 1)
**목표**: 구현을 위한 기반 작업 완료

#### Tasks:
1. **보안 모델 재설계**
   - AST 검증기 구조 설계
   - 안전 API 래퍼 인터페이스 정의
   - 위험 패턴 분석 및 탐지 로직 설계

2. **경로 처리 개선안 설계**
   - 경로 해석 로직 재설계
   - 작업공간 경계 검증 방식
   - 심볼릭 링크 및 경로 탈출 방지 메커니즘

3. **JSON 처리 개선안**
   - UTF-8 인코딩 명시적 처리
   - 클라이언트-서버 헤더 통일

### Phase 2: 핵심 구현 (Day 2-3)
**목표**: 주요 기능 개발 완료

#### 2.1 AST 보안 검증기 구현
```python
class SecurityValidator:
    """AST 기반 코드 보안 검증기"""

    DANGEROUS_NODES = [
        ast.Import, ast.ImportFrom  # import 문
    ]

    DANGEROUS_FUNCTIONS = [
        '__import__', 'exec', 'eval', 'compile',
        'getattr', 'setattr', 'delattr'
    ]

    ALLOWED_MODULES = [
        'pathlib', 'json', 'datetime', 'math',
        'random', 'string', 'collections'
    ]

    def validate_code(self, code: str) -> bool:
        """코드 보안성 검증"""
        try:
            tree = ast.parse(code)
            return self._check_ast_nodes(tree)
        except SyntaxError:
            return False

    def _check_ast_nodes(self, tree: ast.AST) -> bool:
        """화이트리스트 기반 AST 노드 검사"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [alias.name.split('.')[0] for alias in node.names]
                if not all(module in self.ALLOWED_MODULES for module in modules):
                    raise SecurityError(f"Import blocked: {modules}")
            if isinstance(node, ast.Call) and self._is_dangerous_call(node):
                raise SecurityError("Dangerous call blocked")
        return True

    def _is_dangerous_call(self, node: ast.Call) -> bool:
        """위험 함수 호출 여부 확인"""
        if isinstance(node.func, ast.Name):
            return node.func.id in self.DANGEROUS_FUNCTIONS
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in self.DANGEROUS_FUNCTIONS
        return False
```

#### 2.2 안전 API 래퍼 구현
```python
class SafeFileAPI:
    """안전한 파일 시스템 API 래퍼"""

    def read_text(self, path: str, working_dir: str = None) -> str:
        """경로 검증 후 안전한 파일 읽기"""
        safe_path = self._validate_path(path, working_dir)
        return Path(safe_path).read_text(encoding='utf-8')

    def write_text(self, path: str, content: str, working_dir: str = None) -> None:
        """경로 검증 후 안전한 파일 쓰기"""
        safe_path = self._validate_path(path, working_dir)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        Path(safe_path).write_text(content, encoding='utf-8')

    def _validate_path(self, path: str, working_dir: str = None) -> Path:
        """경로 탈출 방지 검증"""
        # 구현 세부사항...
```

#### 2.3 경로 정규화 강화
```python
def secure_resolve_path(path: str, working_dir: Optional[str] = None) -> Path:
    """보안이 강화된 경로 해석"""
    # 1단계: 기본 경로 해석
    if working_dir and not os.path.isabs(path):
        full_path = Path(working_dir) / path
    elif os.path.isabs(path):
        host_root = Path(HOST_ROOT)
        candidate = Path(path)
        if not str(candidate).startswith(str(host_root)):
            candidate = host_root / path.lstrip('/')
        full_path = candidate
    else:
        full_path = Path(PROJECT_ROOT) / path

    # 2단계: 실제 경로 해석 (심볼릭 링크 해결)
    resolved = full_path.resolve()

    # 3단계: 작업공간 경계 검증
    workspace = Path(PROJECT_ROOT).resolve()
    if not resolved.is_relative_to(workspace):
        raise SecurityError(f"Path traversal blocked: {path}")

    # 4단계: 위험한 시스템 경로 차단
    dangerous_paths = ["/etc", "/root", "/bin", "/sbin", "/usr/bin", "/usr/sbin"]
    for dangerous in dangerous_paths:
        if str(resolved).startswith(dangerous):
            raise SecurityError(f"Access to system path blocked: {resolved}")

    return resolved
```

#### 2.4 JSON UTF-8 처리 개선
```python
# 클라이언트 측 (scripts/ai.py)
headers = {
    "Content-Type": "application/json; charset=utf-8"
}

# JSON 인코딩 시 ensure_ascii=False 사용
json_data = json.dumps(kwargs, ensure_ascii=False).encode('utf-8')

# 서버 측 (services/mcp-server/app.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def ensure_utf8_content_type(request: Request, call_next):
    """모든 응답에 UTF-8 charset 부여"""
    response = await call_next(request)
    response.headers.setdefault("content-type", "application/json; charset=utf-8")
    return response
```

- FastAPI `Request` 객체를 사용하도록 `from fastapi import Request` 임포트 추가 예정

### Phase 3: 테스트 및 검증 (Day 4)
**목표**: 품질 보증 및 보안 검증

#### 3.1 보안 침투 테스트
```python
# 테스트 케이스 예시
security_test_cases = [
    # 샌드박스 탈출 시도
    "importlib.import_module('os')",
    "__import__('subprocess')",
    "eval('import os')",
    "getattr(__builtins__, 'exec')",

    # 경로 탈출 시도
    "../../../etc/passwd",
    "/etc/shadow",
    "../../root/.ssh/id_rsa",

    # 동적 코드 실행
    "exec('print(\"pwned\")')",
    "compile('import os', '<string>', 'exec')"
]
```

#### 3.2 기능 통합 테스트
- 모든 18개 MCP 도구 정상 동작 확인
- 한국어 포함 요청/응답 테스트
- working_dir 기반 경로 처리 테스트

#### 3.3 성능 검증 테스트
- AST 파싱 오버헤드 측정 (목표: 5% 이내)
- 메모리 사용량 증가 측정 (목표: 10MB 이하)
- 동시 요청 처리 능력 테스트

### Phase 4: 배포 및 문서화 (Day 5)
**목표**: 운영 환경 배포 및 문서 업데이트

#### Tasks:
1. **컨테이너 배포 테스트**: Docker 환경에서 정상 동작 확인
2. **문서 업데이트**: CLAUDE.md 및 보안 가이드 업데이트
3. **릴리스 노트 작성**: 변경사항 및 마이그레이션 가이드

---

## ⚠️ Risk Assessment & Mitigation

### High Risk Items
| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| AST 우회를 통한 샌드박스 탈출 | Very High | Medium | 다중 검증 계층 + 화이트리스트 접근법 |
| 경로 탈출 (심볼릭 링크 등) | High | High | realpath() + 작업공간 경계 강제 검증 |
| 성능 저하 (AST 파싱 오버헤드) | Medium | Medium | 코드 캐싱 + 비동기 처리 |
| 기존 사용자 워크플로우 영향 | Medium | Low | 점진적 마이그레이션 + 역호환성 유지 |

### Technical Challenges
1. **AST 파싱 성능 오버헤드** → 코드 캐싱 및 비동기 처리로 해결
2. **동적 import 우회 시도 탐지** → importlib, __import__, eval() 패턴 분석
3. **한국어 JSON 이스케이프 처리** → ensure_ascii=False + UTF-8 명시적 처리

### Rollback Plan
- **보안 이슈 발견** → 기존 키워드 필터로 즉시 복귀
- **성능 문제** → AST 검증 비활성화 옵션 제공
- **호환성 문제** → 레거시 모드 옵션 제공

---

## 🧪 Quality Assurance Plan

### Test Strategy
**테스트 레벨**:
- **Unit Tests**: AST 검증기, 경로 처리 함수, JSON 인코딩
- **Integration Tests**: MCP 도구 전체 워크플로우
- **Security Tests**: 샌드박스 탈출 시도, 경로 탈출 시도
- **Performance Tests**: AST 파싱 오버헤드, 메모리 사용량

### Test Cases
```gherkin
Feature: MCP 보안 개선

  Scenario: 안전한 코드 실행
    Given Python 코드 "import pathlib; print('safe')"
    When AST 검증기가 코드를 분석할 때
    Then 코드가 정상적으로 실행된다

  Scenario: 위험한 코드 차단
    Given Python 코드 "import os; os.system('rm -rf /')"
    When AST 검증기가 코드를 분석할 때
    Then SecurityError가 발생한다

  Scenario: 경로 탈출 시도 차단
    Given 파일 경로 "../../../etc/passwd"
    When resolve_path 함수가 경로를 처리할 때
    Then SecurityError가 발생한다

  Scenario: 한국어 JSON 처리
    Given JSON 데이터 {"query": "안녕하세요 🌍"}
    When MCP 서버가 요청을 처리할 때
    Then 정상적으로 응답한다
```

### Performance Criteria
- **응답시간**: 기존 대비 5% 이내 증가
- **메모리 사용률**: AST 파싱으로 인한 10MB 이하 추가 사용
- **처리량**: 초당 10개 요청 이상 처리 가능

---

## 📈 Resource Requirements

### Human Resources
- **개발자**: 1명 (Python, 보안, Docker 경험 필수)
- **리뷰어**: 1명 (보안 중점 리뷰)
- **테스터**: 1명 (침투 테스트 경험)

### Technical Resources
- **개발 도구**: Python AST 모듈, pathlib, FastAPI
- **테스트 환경**: Docker Compose, 로컬 MCP 서버
- **보안 도구**: 코드 정적 분석기, 침투 테스트 스크립트

### Time Estimation
- **총 예상 시간**: 5일
- **버퍼 시간**: 1일 (20% 버퍼)
- **완료 목표일**: 2025-10-01

---

## 📝 Implementation Details

### File Changes Required

#### 1. services/mcp-server/app.py
- `execute_python()` 함수 교체: AST 검증기 적용
- `resolve_path()` 함수 강화: 경로 탈출 방지
- 안전 API 래퍼 클래스 추가
- JSON 인코딩 헤더 개선

#### 2. scripts/ai.py
- HTTP 헤더에 UTF-8 charset 명시
- JSON 인코딩 시 ensure_ascii=False 적용

#### 3. 새 파일 추가
- `services/mcp-server/security.py`: AST 검증기 구현
- `services/mcp-server/safe_api.py`: 안전 API 래퍼
- `tests/security_tests.py`: 보안 테스트 스위트

---

## 🔄 Migration Strategy

### Backward Compatibility
1. **기존 API 유지**: 모든 MCP 도구 인터페이스 동일 유지
2. **설정 옵션**: 보안 수준 조정 가능한 환경변수 제공
3. **점진적 적용**: 단계적으로 보안 강화 적용

### Configuration Options
```python
# 환경변수로 보안 수준 조정
SECURITY_LEVEL = os.getenv("MCP_SECURITY_LEVEL", "normal")  # strict|normal|legacy (로컬 기본값 normal)
AST_VALIDATION = os.getenv("MCP_AST_VALIDATION", "true")    # true|false
PATH_VALIDATION = os.getenv("MCP_PATH_VALIDATION", "strict") # strict|normal
```

- 로컬 단독 사용 시 `MCP_SECURITY_LEVEL=normal`로 두고, 배포 전 `strict` 모드에서 최종 테스트 진행

---

## 📊 Success Metrics

### Functional Metrics
- [ ] 모든 18개 MCP 도구 정상 동작
- [ ] 한국어 포함 JSON 요청 100% 성공
- [ ] 경로 탈출 시도 100% 차단

### Security Metrics
- [ ] 샌드박스 탈출 시도 0건 성공
- [ ] 위험한 코드 실행 0건 허용
- [ ] 시스템 파일 접근 시도 100% 차단

### Performance Metrics
- [ ] 응답시간 증가 < 5%
- [ ] 메모리 사용량 증가 < 10MB
- [ ] 처리량 > 10 requests/sec

---

## 🎯 Next Actions

### Immediate Steps (Today)
1. **계획 승인**: 이해관계자 검토 및 승인
2. **개발 환경 준비**: 테스트 환경 설정
3. **보안 모델 상세 설계**: AST 검증기 구조 확정

### This Week
1. **Phase 1 완료**: 설계 및 준비 작업
2. **Phase 2 시작**: 핵심 기능 구현 착수
3. **보안 리뷰**: 중간 보안 검토 진행

### Next Week
1. **Phase 3-4 완료**: 테스트, 검증, 배포
2. **문서 업데이트**: CLAUDE.md 및 가이드 완성
3. **릴리스**: 개선된 MCP 서버 배포

---

**📝 Notes**:
- 이 계획은 보안을 최우선으로 하되, 기존 기능성과 사용성을 최대한 유지하는 것을 목표로 합니다.
- 각 단계마다 보안 검토를 거쳐 안전성을 확보합니다.
- 성능 및 호환성 문제 발생 시 즉시 롤백 가능한 구조로 설계되었습니다.
