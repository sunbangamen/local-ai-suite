# AI CLI Tool 설치 가이드

## 🚀 설치 방법

### Windows (PowerShell/CMD)
```cmd
# 1. scripts 폴더를 PATH에 추가하거나
# 2. 이 폴더에서 직접 실행
cd /mnt/e/worktree/issue-1/scripts
ai.bat "안녕하세요!"
```

### WSL / Linux / macOS
```bash
# 1. 실행 권한 확인 (이미 설정됨)
chmod +x scripts/ai

# 2. PATH에 추가 (옵션)
echo 'export PATH="/mnt/e/worktree/issue-1/scripts:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 3. 사용
ai "안녕하세요!"
```

## 📝 사용법

### 기본 사용
```bash
# 자동 모델 선택
ai "안녕하세요!"                    # → 채팅 모델
ai "Python 함수 만들어줘"           # → 코딩 모델 (자동 감지)

# 수동 모델 선택
ai --code "일반 질문이지만 코딩모델 사용"
ai --chat "코딩 질문이지만 채팅모델 사용"

# 응답 길이 제한
ai --tokens 100 "짧게 답해줘"
```

### 인터랙티브 모드
```bash
ai -i
# 또는
ai --interactive
```

## 🤖 모델 자동 선택 키워드

**코딩 모델로 자동 선택되는 키워드들:**
- 한국어: 코드, 함수, 변수, 클래스, 메서드, 알고리즘, 디버깅, 버그, 리팩토링, 프로그래밍
- 영어: code, function, debug, programming, python, javascript, etc.
- 코드 패턴: `def `, `function `, `class `, `import `, etc.

나머지는 모두 **채팅 모델**로 자동 선택됩니다.

## ⚙️ 문제 해결

### "Cannot connect to local AI server" 오류
```bash
# 서버가 실행 중인지 확인
make up-p1

# 포트 확인
curl http://localhost:8000/v1/models
```

### Python 설치 확인
```bash
python --version   # Windows
python3 --version  # Linux/macOS
```

### 권한 오류 (Linux/macOS)
```bash
chmod +x scripts/ai
```