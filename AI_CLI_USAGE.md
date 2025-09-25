# AI CLI 사용법 가이드

## 🚀 빠른 시작

### Windows
```cmd
# PowerShell/CMD에서
scripts\ai.bat "안녕하세요!"
scripts\ai.bat "Python 함수 만들어줘"
```

### WSL / Linux / macOS
```bash
# 터미널에서
scripts/ai "안녕하세요!"
scripts/ai "Python 함수 만들어줘"

# 또는 직접 Python 실행
python3 scripts/ai.py "질문"
```

## 📝 기본 사용법

### 1. 자동 모델 선택 (추천)
```bash
ai "안녕하세요!"                    # → 채팅 모드 (일반 대화)
ai "Python 함수 만들어줘"           # → 코딩 모드 (자동 감지)
ai "이 코드 설명해줘: def hello():" # → 코딩 모드 (자동 감지)
ai "오늘 날씨 어때?"                # → 채팅 모드 (일반 대화)
```

### 2. 수동 모델 선택
```bash
ai --code "일반 질문이지만 코딩 관점에서 답변해줘"
ai --chat "코딩 질문이지만 일반적인 설명으로 답변해줘"
```

### 3. RAG (문서 기반 질의응답) 🔍
```bash
# 문서 검색을 통한 답변
ai --rag "Python에서 파일을 읽는 방법은?"
ai --rag "프로젝트 설치 방법 알려줘"

# 특정 컬렉션에서 검색
ai --rag --collection myproject "이 프로젝트에서 API 사용법은?"

# 문서 인덱싱 (최초 1회 또는 문서 업데이트 시)
ai --index                    # default 컬렉션에 인덱싱
ai --index myproject          # myproject 컬렉션에 인덱싱
```

### 4. 응답 길이 조절
```bash
ai --tokens 100 "짧게 답해줘"      # 최대 100토큰
ai --tokens 1000 "자세히 설명해줘"  # 최대 1000토큰 (기본값: 500)
```

## 🎮 인터랙티브 모드

### 시작
```bash
ai -i
# 또는
ai --interactive
```

### 인터랙티브 모드 명령어
```
💬 You: 안녕하세요!                    # 일반 질문
💬 You: :code Python 함수 만들어줘     # 강제 코딩 모드
💬 You: :chat 코딩을 일반적으로 설명해줘 # 강제 채팅 모드
💬 You: :rag 파일 읽기 방법은?          # RAG 검색
💬 You: :index myproject              # 문서 인덱싱
💬 You: help                          # 도움말
💬 You: exit                          # 종료
```

## 🤖 자동 모델 선택 로직

### 코딩 모델로 자동 선택되는 키워드
**한국어:**
- 코드, 함수, 변수, 클래스, 메서드, 알고리즘
- 디버깅, 버그, 리팩토링, 프로그래밍, 개발
- API, 데이터베이스, 스크립트

**영어:**
- code, function, variable, class, method, algorithm
- debug, bug, refactor, programming, development
- API, database, script, framework, library

**코드 패턴 감지:**
- `def `, `function `, `class `, `import `, `from `
- `console.log`, `print(`, `if (`, `for (`
- `{ }`, `#include`, `#TODO`

### 채팅 모델 (기본값)
위 키워드가 없는 모든 질문은 일반 채팅 모델로 처리됩니다.

## 🛠️ 고급 사용법

### 1. 길고 복잡한 질문
```bash
# 파일로 질문 작성
echo "복잡한 알고리즘 구현해줘..." > question.txt
ai "$(cat question.txt)"
```

### 2. 파이프라인 사용
```bash
echo "Python 함수 만들어줘" | ai --code
```

### 3. 환경변수로 설정
```bash
export AI_TOKENS=200    # 기본 토큰 수 변경 (향후 지원 예정)
export AI_MODEL=chat    # 기본 모델 변경 (향후 지원 예정)
```

## 📊 사용 예시

### 코딩 관련 질문
```bash
ai "Python에서 파일 읽기 함수 만들어줘"
ai "이 코드의 버그를 찾아줘: def calc(x): return x/0"
ai "JavaScript 배열 정렬 알고리즘 설명해줘"
ai "SQL 쿼리 최적화 방법 알려줘"
```

### RAG 기반 문서 검색
```bash
ai --rag "Python에서 파일을 읽는 방법은?"      # 문서에서 파일 읽기 예제 검색
ai --rag "프로젝트 설치 방법 알려줘"           # 설치 가이드 검색
ai --rag "Local AI Suite 사용법"           # 프로젝트 사용법 검색
ai --rag "Docker 설정은 어떻게 해?"         # Docker 설정 관련 검색
```

### 일반 대화
```bash
ai "오늘 기분이 좋지 않아"
ai "건강한 식단 추천해줘"
ai "영화 추천해줘"
ai "시간 관리 팁 알려줘"
```

### 혼합 사용
```bash
ai "프로그래밍을 배우고 싶은데 어떻게 시작해야 할까?"  # → 채팅 모드
ai --code "프로그래밍 학습용 간단한 예제 코드 만들어줘"   # → 코딩 모드
```

## ⚙️ 설정 및 설치

### PATH 추가 (선택사항)

**Windows (PowerShell):**
```powershell
$env:PATH += ";C:\path\to\issue-1\scripts"
# 이후 어디서든 ai.bat 사용 가능
```

**Linux/macOS:**
```bash
echo 'export PATH="/mnt/e/worktree/issue-1/scripts:$PATH"' >> ~/.bashrc
source ~/.bashrc
# 이후 어디서든 ai 사용 가능
```

### 필요한 라이브러리
```bash
pip install requests  # 대부분 이미 설치되어 있음
```

## 🔧 문제 해결

### "Cannot connect to local AI server" 오류
```bash
# Phase 1 서버 시작 (기본 AI)
make up-p1

# Phase 2 서버 시작 (RAG 포함)
make up-p2

# 서버 상태 확인
curl http://localhost:8000/v1/models
curl http://localhost:8002/health     # RAG 서비스 확인

# 서비스 재시작
make down && make up-p2
```

### "Cannot connect to RAG service" 오류
```bash
# RAG 시스템이 포함된 Phase 2 시작
make up-p2

# RAG 서비스 상태 확인
curl http://localhost:8002/health

# 문서 재인덱싱
ai --index

# 전체 재시작
make down && make up-p2
```

### "Request timed out" 오류
```bash
# 더 짧은 응답 요청
ai --tokens 100 "간단히 답해줘"

# 또는 서버 재시작
make down && make up-p1
```

### Python 실행 오류
```bash
# Python 버전 확인
python --version    # Windows
python3 --version   # Linux/macOS

# 필요시 python3로 직접 실행
python3 scripts/ai.py "질문"
```

### 권한 오류 (Linux/macOS)
```bash
chmod +x scripts/ai
```

## 📈 향후 개선 예정 사항

### Phase 2 완료 ✅
- [x] **RAG 통합**: `ai --rag "질문"` - 업로드된 문서를 참조한 답변
- [x] **문서 인덱싱**: `ai --index` - 문서 자동 인덱싱
- [x] **컬렉션 관리**: `ai --collection name` - 여러 문서 그룹 관리
- [x] **두 모델 지원**: 채팅용/코딩용 모델 자동 선택

### Phase 3 예정 기능
- [ ] **MCP 서버**: Claude Desktop과 연동
- [ ] **컨텍스트 유지**: 이전 대화 기억
- [ ] **실시간 문서 업데이트**: 파일 변경 감지 및 자동 재인덱싱

### 일반 개선 사항
- [ ] **설정 파일**: `~/.ai-config.yaml`로 개인 설정 저장
- [ ] **다중 모델 지원**: 실제 두 개 모델 동시 실행
- [ ] **스트리밍 응답**: 실시간 답변 출력
- [ ] **히스토리 기능**: 이전 질문/답변 검색
- [ ] **플러그인 시스템**: 사용자 정의 기능 추가

### UI/UX 개선
- [ ] **컬러 출력**: 구문 강조 및 예쁜 포맷팅
- [ ] **진행 표시**: 응답 생성 중 로딩 표시
- [ ] **자동완성**: 자주 사용하는 질문 패턴 제안
- [ ] **다국어 지원**: 영어, 일본어 등 추가 언어

## 🎯 팁과 요령

### 효과적인 질문 방법
1. **구체적으로 질문**: "함수 만들어줘" → "CSV 파일을 읽는 Python 함수 만들어줘"
2. **컨텍스트 제공**: "이 에러 해결해줘: TypeError..."
3. **원하는 형태 명시**: "주석과 함께 코드 작성해줘"

### 성능 최적화
1. **토큰 수 조절**: 간단한 질문은 `--tokens 100`
2. **적절한 모드 선택**: 확실하면 `--code` 또는 `--chat` 지정
3. **서버 상태 확인**: 느려지면 `make down && make up-p1`

### 보안 주의사항
- 개인정보나 민감한 코드는 질문에 포함하지 마세요
- 모든 데이터는 로컬에서 처리되지만 로그에 남을 수 있습니다

---

**💡 이 문서는 지속적으로 업데이트됩니다. 새로운 기능이나 개선사항이 있으면 이 파일을 수정해주세요!**