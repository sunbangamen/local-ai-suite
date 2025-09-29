# 전역 파일시스템 접근 정책

## 개요

Docker 컨테이너에서 호스트 파일시스템 접근이 필요한 서비스와 그 사용 범위를 정의합니다.

## 접근 권한 매트릭스

| 서비스 | 마운트 경로 | 권한 | 용도 | 필요성 |
|--------|-------------|------|------|--------|
| **memory-api** | `/mnt/host:ro` | 읽기 전용 | 프로젝트 경로 해석, 메모리 디렉토리 생성 | 높음 |
| **memory-maintainer** | `/mnt/host:ro` | 읽기 전용 | 백업 작업, 프로젝트 스캔 | 중간 |
| **mcp-server** | `/mnt/host:rw` | 읽기/쓰기 | MCP 도구의 파일 시스템 작업 | 높음 |
| **rag** | `/mnt/host:ro` | 읽기 전용 | 문서 인덱싱 (anywhere 모드) | 중간 |

## 서비스별 상세 정책

### memory-api

**접근 범위:**
- 프로젝트 디렉토리 탐지 (`get_project_id`)
- `.ai-memory` 디렉토리 생성/접근
- 프로젝트 경로 기반 UUID 생성

**보안 제약:**
- 읽기 전용 마운트
- 메모리 관련 경로로만 제한
- 실제 파일 생성은 `/app/memory` 내부

**예시 경로:**
```
/mnt/host/mnt/e/worktree/project-1/.ai-memory/
/mnt/host/home/user/projects/my-app/.ai-memory/
```

### memory-maintainer

**접근 범위:**
- 백업 파일 생성 시 프로젝트 정보 조회
- 프로젝트 목록 스캔
- 로그 파일 경로 해석

**보안 제약:**
- 읽기 전용 마운트
- 백업 데이터는 `/app/memory/backups` 내부 저장
- 호스트 파일 수정 금지

**사용 시나리오:**
- 프로젝트별 백업 메타데이터 생성
- 삭제된 프로젝트 정리
- 통계 수집

### mcp-server

**접근 범위:**
- MCP 도구를 통한 전역 파일 작업
- Git 저장소 작업
- 문서 읽기/쓰기

**보안 제약:**
- MCP 도구별 권한 제한
- 위험한 시스템 경로 차단
- 사용자 인증 기반 접근 제어

### rag

**접근 범위:**
- anywhere 문서 인덱싱
- 전역 문서 검색
- 파일 내용 분석

**보안 제약:**
- 읽기 전용 마운트
- 인덱싱된 내용만 저장
- 원본 파일 수정 금지

## 보안 고려사항

### 1. 최소 권한 원칙

```yaml
# ✅ 올바른 예시 - 읽기 전용
volumes:
  - /:/mnt/host:ro

# ❌ 피해야 할 예시 - 불필요한 쓰기 권한
volumes:
  - /:/mnt/host:rw
```

### 2. 경로 검증

모든 서비스는 다음 검증을 수행해야 합니다:

```python
def validate_host_path(path: str) -> bool:
    """호스트 경로 접근 검증"""
    forbidden_paths = [
        "/etc/passwd", "/etc/shadow", "/root/.ssh",
        "/var/run/docker.sock", "/proc", "/sys"
    ]

    resolved_path = Path(f"/mnt/host{path}").resolve()

    # 금지된 경로 확인
    for forbidden in forbidden_paths:
        if str(resolved_path).startswith(f"/mnt/host{forbidden}"):
            return False

    return True
```

### 3. 감사 로깅

모든 호스트 파일시스템 접근은 로그에 기록됩니다:

```
2025-09-29 04:44:29 [memory-api] HOST_ACCESS: /mnt/host/mnt/e/worktree/project/.ai-memory READ
2025-09-29 04:44:30 [mcp-server] HOST_ACCESS: /mnt/host/home/user/document.txt WRITE
```

## 설정 가이드

### 전역 접근이 필요한 경우

```yaml
services:
  service-name:
    volumes:
      - /:/mnt/host:ro  # 읽기 전용 권장
    environment:
      - HOST_MOUNT_PATH=/mnt/host
```

### 제한된 접근이 충분한 경우

```yaml
services:
  service-name:
    volumes:
      - ${DATA_DIR}:/app/data:rw          # 데이터 디렉토리만
      - ${PROJECT_DIR}:/app/project:ro    # 특정 프로젝트만
```

## 위험 평가

### 높은 위험 (피해야 할 설정)

```yaml
# 루트 쓰기 권한
- /:/mnt/host:rw

# Docker 소켓 접근
- /var/run/docker.sock:/var/run/docker.sock

# 시스템 디렉토리 직접 마운트
- /etc:/mnt/etc
- /proc:/mnt/proc
```

### 낮은 위험 (권장 설정)

```yaml
# 읽기 전용 전역 접근
- /:/mnt/host:ro

# 특정 디렉토리만
- /home/user/projects:/mnt/projects:ro
- /mnt/data:/app/data:rw
```

## 모니터링

### 접근 패턴 모니터링

```bash
# 호스트 접근 로그 확인
docker logs docker-memory-api-1 | grep "HOST_ACCESS"

# 의심스러운 경로 접근 탐지
docker logs docker-mcp-server-1 | grep -E "(etc|proc|sys|root)"
```

### 자동 알림

```bash
# 위험한 경로 접근 시 알림
docker logs --follow docker-mcp-server-1 | \
  grep -E "(etc/passwd|etc/shadow|root/.ssh)" | \
  while read line; do
    echo "SECURITY ALERT: $line" | mail -s "Security Alert" admin@example.com
  done
```

## 정기 검토

### 월간 점검 항목

1. 각 서비스의 실제 호스트 접근 패턴 분석
2. 불필요한 권한 제거
3. 새로운 보안 위협 평가
4. 접근 로그 아카이브

### 권한 최적화

```bash
# 서비스별 실제 접근 경로 분석
docker logs docker-memory-api-1 --since="30d" | \
  grep "HOST_ACCESS" | \
  awk '{print $4}' | sort | uniq -c | sort -nr

# 불필요한 권한 식별
if [ $(docker logs docker-memory-api-1 --since="30d" | grep "HOST_ACCESS.*WRITE" | wc -l) -eq 0 ]; then
  echo "memory-api는 읽기 전용으로 변경 가능"
fi
```

## 마이그레이션 가이드

### 기존 서비스에 전역 접근 추가

1. **점진적 적용**
   ```yaml
   # 단계 1: 읽기 전용으로 시작
   volumes:
     - /:/mnt/host:ro

   # 단계 2: 필요시에만 쓰기 권한 추가
   volumes:
     - /:/mnt/host:rw
   ```

2. **테스트 환경에서 검증**
   ```bash
   # 테스트 환경에서 권한 테스트
   docker compose -f docker/compose.test.yml up service-name
   ```

3. **프로덕션 적용**
   ```bash
   # 백업 후 적용
   docker compose -f docker/compose.p3.yml down service-name
   docker compose -f docker/compose.p3.yml up -d service-name
   ```

이제 전역 파일시스템 접근 정책이 명확하게 문서화되었습니다. 각 서비스의 필요성과 보안 제약이 명시되어 안전한 운영이 가능합니다.