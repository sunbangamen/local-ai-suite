# 🧠 프로젝트별 장기 기억 시스템 - 완전한 설계 계획

## 📋 요구사항 분석

**핵심 목표:**
- 프로젝트별 독립적인 장기 기억
- 아주 긴 대화 지원 (무제한)
- 시간 경과에 따른 스마트한 정리
- 실무적 관리 편의성
- 관리자 친화적 제어

## 🏗️ 시스템 아키텍처 설계

### 1. 데이터 저장 구조
```
${MEMORY_ROOT:-~/.local/share/local-ai/memory}/
├── projects/
│   ├── [project_hash]/
│   │   ├── memory.db          # SQLite 데이터베이스
│   │   ├── conversations.json # JSON 백업
│   │   ├── summaries.json     # AI 생성 요약
│   │   └── metadata.json      # 프로젝트 정보
├── global/
│   ├── user_preferences.json
│   └── cleanup_log.json
└── temp/
    └── processing/            # 임시 처리 파일
```

> `MEMORY_ROOT` 환경 변수를 통해 저장 경로를 제어하고, 미설정 시 플랫폼 기본 경로(`~/.local/share/local-ai/memory`)를 사용.
> 태그는 JSON 필드가 아닌 `conversation_tags` 보조 테이블로 관리해 검색 성능과 정규화를 동시에 확보.

### 2. 데이터베이스 스키마 (SQLite)
```sql
-- 대화 기록 (핵심 메타데이터)
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_query TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    model_used VARCHAR(50),
    importance_score INTEGER DEFAULT 5, -- 1(삭제) ~ 10(영구보관)
    session_id VARCHAR(50),
    token_count INTEGER,
    response_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 대화 태그 (정규화)
CREATE TABLE conversation_tags (
    conversation_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, tag),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 대화 요약
CREATE TABLE conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_range TEXT,              -- "2024-09-01 to 2024-09-07"
    summary TEXT,                 -- AI 생성 요약
    conversation_count INTEGER,
    importance_level INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 중요 사실
CREATE TABLE important_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL,
    category VARCHAR(100),        -- code, config, decision, etc.
    source_conversation_id INTEGER,
    user_marked BOOLEAN DEFAULT FALSE,
    ai_suggested BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);

-- 사용자 선호도
CREATE TABLE user_preferences (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 의미 검색용 임베딩 (로컬 캐시 + 외부 벡터스토어 핸들)
CREATE TABLE conversation_embeddings (
    conversation_id INTEGER PRIMARY KEY,
    embedding BLOB NOT NULL,                     -- 1536 float32 벡터 직렬화
    vector_store_id TEXT,                        -- Qdrant 등 외부 스토어 식별자
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 인덱스
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_conversations_importance ON conversations(importance_score);
CREATE INDEX idx_conversation_tags_tag ON conversation_tags(tag);
```

> 대용량 의미 검색이 필요하면 Qdrant/Weaviate 등 외부 벡터 스토어에 `vector_store_id`로 동기화하고, 로컬 SQLite는 캐시/백업 용도로 유지.

### 3. 중요도 기반 자동 정리 시스템

**중요도 점수 시스템 (1-10):**
```python
IMPORTANCE_LEVELS = {
    1: {"name": "즉시삭제", "ttl_days": 0, "description": "인사, 테스트"},
    2: {"name": "단기보관", "ttl_days": 3, "description": "간단한 질문"},
    3: {"name": "1주보관", "ttl_days": 7, "description": "일반 대화"},
    4: {"name": "2주보관", "ttl_days": 14, "description": "정보성 질문"},
    5: {"name": "기본보관", "ttl_days": 30, "description": "기본값"},
    6: {"name": "1개월", "ttl_days": 30, "description": "코드 관련"},
    7: {"name": "3개월", "ttl_days": 90, "description": "프로젝트 설정"},
    8: {"name": "6개월", "ttl_days": 180, "description": "중요 결정사항"},
    9: {"name": "1년보관", "ttl_days": 365, "description": "핵심 문서화"},
    10: {"name": "영구보관", "ttl_days": -1, "description": "사용자 중요표시"}
}
```

**자동 중요도 판정 로직:**
```python
def calculate_importance_score(query: str, response: str, context: dict) -> int:
    score = 5  # 기본값

    # 키워드 기반 점수 조정
    high_importance_keywords = [
        "설정", "config", "환경변수", "architecture", "design pattern",
        "버그", "해결", "문제", "오류", "에러", "fix", "bug",
        "구현", "알고리즘", "최적화", "성능", "performance"
    ]

    low_importance_keywords = [
        "안녕", "hello", "테스트", "test", "확인", "체크"
    ]

    if any(word in query or word in response for word in high_importance_keywords):
        score += 2
    if any(word in query or word in response for word in low_importance_keywords):
        score -= 2

    # 응답 길이 고려 (긴 응답 = 더 중요)
    if len(response) > 1000:
        score += 1
    if len(response) > 2000:
        score += 1

    # 코드 포함 여부
    if "```" in response or "def " in response or "class " in response:
        score += 1

    # 사용자 피드백 반영
    if context.get("user_saved", False):
        score = 10
    if context.get("user_dismissed", False):
        score = min(score, 3)

    return max(1, min(10, score))
```

### 4. 컨텍스트 검색 및 관련성 시스템

**관련성 검색 알고리즘:**
```python
def get_relevant_context(current_query: str, project_path: str, limit: int = 5) -> List[Dict]:
    """현재 질문과 관련된 이전 대화 검색"""

    # 1. 키워드 매칭
    # 2. 의미적 유사성 (임베딩 기반)
    # 3. 시간적 근접성
    # 4. 중요도 가중치

    return relevant_conversations
```

> 의미 검색은 `conversation_embeddings` 테이블 또는 Qdrant 컬렉션에서 cosine 유사도로 수행하고, 결과는 태그/중요도 기준으로 재정렬.

### 5. 사용자 인터페이스 설계

**AI CLI 명령어:**
```bash
# 메모리 관리
ai --memory                           # 메모리 상태 보기
ai --memory --save "중요한 내용"       # 영구 저장
ai --memory --important "결정사항"     # 중요도 9로 저장
ai --memory --forget "패턴"           # 특정 내용 삭제
ai --memory --cleanup                 # 수동 정리 실행
ai --memory --export                  # 백업 파일 생성
ai --memory --import backup.json      # 백업 복원

# 검색 및 조회
ai --memory --search "키워드"         # 메모리 검색
ai --memory --summary                 # 프로젝트 요약
ai --memory --stats                   # 통계 정보
ai --memory --recent                  # 최근 대화
ai --memory --important-only          # 중요한 것만

# 설정
ai --memory --set-retention 90        # 기본 보관기간
ai --memory --set-auto-cleanup on     # 자동 정리 켜기
ai --memory --set-importance-threshold 6 # 자동 삭제 임계값
```

**Desktop App UI:**
- 메모리 관리 탭 추가
- 대화별 중요도 설정 버튼
- 검색 기능
- 백업/복원 기능

## 📊 구현 단계별 계획

### Phase 1: 기본 저장 시스템 (3일)
- [ ] SQLite 데이터베이스 설계 및 생성
- [ ] 기본 대화 저장/조회 기능
- [ ] 프로젝트 식별 시스템
- [ ] JSON 백업 시스템

### Phase 2: 자동 정리 시스템 (2일)
- [ ] 중요도 자동 판정 로직
- [ ] TTL 기반 자동 삭제
- [ ] 백그라운드 정리 스케줄러
- [ ] 안전한 삭제 확인 시스템

### Phase 3: 검색 및 컨텍스트 시스템 (3일)
- [ ] 키워드 기반 검색
- [ ] 관련성 점수 계산
- [ ] 컨텍스트 자동 포함 로직
- [ ] 성능 최적화 (인덱싱)
- [ ] Qdrant 등 벡터 스토어 동기화 및 임베딩 캐싱

### Phase 4: 사용자 인터페이스 (2일)
- [ ] AI CLI 메모리 명령어
- [ ] Desktop App 메모리 관리 UI
- [ ] 통계 및 시각화
- [ ] 설정 관리

### Phase 5: 고급 기능 (2일)
- [ ] AI 요약 생성
- [ ] 중요 사실 자동 추출
- [ ] 백업/복원 시스템
- [ ] 성능 모니터링

## 🔧 실무적 고려사항

### 안전성
- 삭제 전 확인 시스템
- 백업 자동화
- 데이터 무결성 검사
- 롤백 기능

### 성능
- 인덱스 최적화
- 페이징 처리
- 캐싱 시스템
- 백그라운드 처리

### 관리성
- 로깅 시스템
- 오류 처리
- 설정 파일 관리
- 마이그레이션 지원

## 🎯 성공 지표

**기술적 목표:**
- 100만개 대화 처리 가능
- 1초 이내 검색 응답
- 99.9% 데이터 안정성

**사용성 목표:**
- 제로 설정 자동 동작
- 직관적인 명령어
- 명확한 피드백

## 📝 구현 시작점

### 1. 우선 구현할 핵심 기능
1. **프로젝트 식별**: 현재 디렉토리 기반 프로젝트 구분
2. **기본 저장**: SQLite + JSON 백업 + `conversation_tags` 정규화
3. **자동 중요도**: 가중치 증감/사용자 피드백 반영 점수 계산
4. **컨텍스트 임베딩**: OpenAI/로컬 임베딩 생성 후 `conversation_embeddings` + Qdrant 동기화
5. **기본 정리**: TTL 기반 삭제

### 2. 파일 구조
```
scripts/
├── ai_memory.py              # 메모리 시스템 코어
├── memory_manager.py         # 관리 인터페이스
├── memory_cleanup.py         # 정리 시스템
└── memory_vector_sync.py     # Qdrant 등 벡터 스토어 연동

${MEMORY_ROOT}/
├── schema.sql               # 데이터베이스 스키마
├── projects/                # 프로젝트별 메모리
└── global/                  # 전역 설정 및 백업
```

### 3. 통합 지점
- `scripts/ai.py`의 `call_api()` 함수에 메모리 저장 로직 추가
- 응답 전에 관련 컨텍스트 검색 및 포함
- 새로운 `--memory` 관련 명령어 추가

이 계획서를 기반으로 단계별 구현을 진행할 수 있습니다.
