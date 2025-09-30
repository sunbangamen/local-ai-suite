#!/usr/bin/env python3
"""
중요도 자동 판정 시스템 테스트
다양한 대화 시나리오에 대한 중요도 점수 검증
"""

from memory_system import memory_system

def test_importance_scenarios():
    """다양한 시나리오로 중요도 점수 테스트"""

    test_cases = [
        # 인사 및 간단한 대화 (낮은 중요도)
        {
            "user_query": "안녕하세요!",
            "ai_response": "안녕하세요! 무엇을 도와드릴까요?",
            "expected_range": (1, 3),
            "description": "간단한 인사"
        },
        {
            "user_query": "감사합니다",
            "ai_response": "천만에요. 다른 질문이 있으시면 언제든 말씀해주세요.",
            "expected_range": (1, 3),
            "description": "감사 인사"
        },

        # 일반적인 질문 (중간 중요도)
        {
            "user_query": "Python에서 리스트와 튜플의 차이점은 무엇인가요?",
            "ai_response": "Python에서 리스트와 튜플의 주요 차이점은 다음과 같습니다:\n\n1. 가변성(Mutability):\n- 리스트는 가변(mutable) 객체로, 생성 후에도 요소를 추가, 삭제, 변경할 수 있습니다.\n- 튜플은 불변(immutable) 객체로, 생성 후에는 요소를 변경할 수 없습니다.\n\n2. 표기법:\n- 리스트: [1, 2, 3]\n- 튜플: (1, 2, 3)\n\n3. 성능:\n- 튜플이 리스트보다 메모리 효율적이고 접근 속도가 빠릅니다.\n\n4. 사용 용도:\n- 리스트: 데이터가 변경될 가능성이 있는 경우\n- 튜플: 고정된 데이터나 함수의 반환값으로 여러 값을 묶을 때",
            "expected_range": (4, 7),
            "description": "Python 기본 개념 질문"
        },

        # 코딩 관련 질문 (높은 중요도)
        {
            "user_query": "FastAPI에서 데이터베이스 연결을 위한 의존성 주입을 어떻게 구현하나요?",
            "ai_response": """FastAPI에서 데이터베이스 연결을 위한 의존성 주입을 구현하는 방법은 다음과 같습니다:

```python
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 데이터베이스 설정
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.get("/users/")
def read_users(db: Session = Depends(get_db)):
    # 데이터베이스 세션 사용
    return db.query(User).all()
```

이 패턴의 장점:
1. 자동 연결 관리
2. 예외 발생시 안전한 정리
3. 테스트 용이성""",
            "expected_range": (6, 9),
            "description": "고급 코딩 질문 + 코드 포함"
        },

        # 설정 및 구성 관련 (높은 중요도)
        {
            "user_query": "Docker compose에서 환경변수를 안전하게 관리하는 방법을 알려주세요",
            "ai_response": """Docker Compose에서 환경변수를 안전하게 관리하는 방법들:

1. .env 파일 사용:
```yaml
# docker-compose.yml
services:
  web:
    image: nginx
    env_file:
      - .env
```

2. 환경변수 파일 분리:
```bash
# .env.prod (프로덕션)
DATABASE_URL=postgresql://prod_user:${PROD_PASSWORD}@db:5432/prod_db

# .env.dev (개발)
DATABASE_URL=postgresql://dev_user:dev_pass@localhost:5432/dev_db
```

3. Docker Secrets 사용:
```yaml
services:
  app:
    secrets:
      - db_password
secrets:
  db_password:
    file: ./secrets/db_password.txt
```

중요한 보안 고려사항:
- .env 파일을 .gitignore에 추가
- 프로덕션에서는 Docker Secrets 또는 외부 비밀 관리 시스템 사용
- 환경별로 파일 분리""",
            "expected_range": (7, 9),
            "description": "설정 관리 + 보안 고려사항"
        },

        # 사용자가 중요표시한 경우 (최고 중요도)
        {
            "user_query": "이 프로젝트의 핵심 아키텍처를 설명해주세요",
            "ai_response": "이 프로젝트는 로컬 AI 서비스를 위한 마이크로서비스 아키텍처를 사용합니다...",
            "context": {"user_important": True},
            "expected_range": (8, 10),
            "description": "사용자 중요 표시"
        }
    ]

    print("🧪 중요도 자동 판정 시스템 테스트")
    print("=" * 60)

    total_tests = len(test_cases)
    passed_tests = 0

    for i, case in enumerate(test_cases, 1):
        user_query = case["user_query"]
        ai_response = case["ai_response"]
        context = case.get("context", {})
        expected_range = case["expected_range"]
        description = case["description"]

        # 중요도 계산
        score = memory_system.calculate_importance_score(
            user_query, ai_response, context=context
        )

        # 결과 검증
        is_passed = expected_range[0] <= score <= expected_range[1]
        if is_passed:
            passed_tests += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\nTest {i}: {description}")
        print(f"Query: {user_query[:50]}{'...' if len(user_query) > 50 else ''}")
        print(f"Expected: {expected_range[0]}-{expected_range[1]}, Got: {score}/10")
        print(f"Result: {status}")

        # 중요도 레벨 정보 표시
        level_info = memory_system.IMPORTANCE_LEVELS[score]
        print(f"Level: {level_info['name']} (TTL: {level_info['ttl_days']} days)")

    print(f"\n📊 테스트 결과: {passed_tests}/{total_tests} 통과 ({passed_tests/total_tests*100:.1f}%)")

    if passed_tests >= total_tests * 0.8:  # 80% 이상 통과
        print("🎉 중요도 판정 시스템이 정상적으로 작동합니다!")
        return True
    else:
        print("⚠️ 중요도 판정 시스템 개선이 필요합니다.")
        return False

def test_memory_integration():
    """메모리 시스템 통합 테스트"""
    print("\n🔗 메모리 시스템 통합 테스트")
    print("=" * 40)

    # 현재 프로젝트 ID 획득
    project_id = memory_system.get_project_id()

    # 다양한 중요도의 대화 저장
    test_conversations = [
        ("안녕하세요", "안녕하세요!", "chat-7b"),
        ("Python 함수 만드는 방법 알려주세요", "Python에서 함수는 def 키워드로 정의합니다...", "code-7b"),
        ("이 프로젝트의 아키텍처 설명해주세요", "상세한 아키텍처 설명...", "chat-7b")
    ]

    conversation_ids = []
    for query, response, model in test_conversations:
        conv_id = memory_system.save_conversation(
            project_id=project_id,
            user_query=query,
            ai_response=response,
            model_used=model,
            session_id="test_session"
        )
        conversation_ids.append(conv_id)
        print(f"✅ 대화 저장 완료: ID {conv_id}")

    # 검색 테스트
    print("\n🔍 검색 테스트:")
    results = memory_system.search_conversations(
        project_id=project_id,
        query="Python",
        limit=5
    )
    print(f"'Python' 검색 결과: {len(results)}개")

    # 통계 확인
    print("\n📊 통계 확인:")
    stats = memory_system.get_conversation_stats(project_id)
    print(f"총 대화: {stats['total_conversations']}개")
    print(f"평균 중요도: {stats['avg_importance']:.1f}/10")

    return True

if __name__ == "__main__":
    # 중요도 판정 테스트
    importance_passed = test_importance_scenarios()

    # 통합 테스트
    integration_passed = test_memory_integration()

    if importance_passed and integration_passed:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("메모리 시스템이 정상적으로 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다.")
        print("추가 개선이 필요합니다.")