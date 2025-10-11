# 모니터링 시스템 사용 가이드

## 1. 개요

Local AI Suite는 Prometheus + Grafana + Loki 스택을 사용하여 완전한 모니터링 시스템을 제공합니다.

### 모니터링 스택 구성
- **Prometheus**: 메트릭 수집 및 저장
- **Grafana**: 시각화 및 대시보드
- **Loki**: 로그 저장 및 검색
- **Promtail**: 로그 수집 에이전트
- **Alertmanager**: 알림 관리
- **cAdvisor**: 컨테이너 리소스 메트릭
- **Node Exporter**: 호스트 시스템 메트릭

### 포트 및 접속 정보
| 서비스 | 포트 | URL | 용도 |
|--------|------|-----|------|
| Grafana | 3001 | http://localhost:3001 | 대시보드 (admin/admin) |
| Prometheus | 9090 | http://localhost:9090 | 메트릭 쿼리 |
| Loki | 3100 | http://localhost:3100 | 로그 저장 |
| Alertmanager | 9093 | http://localhost:9093 | 알림 관리 |
| cAdvisor | 8080 | http://localhost:8080 | 컨테이너 메트릭 |
| Node Exporter | 9100 | http://localhost:9100 | 시스템 메트릭 |

---

## 2. Grafana 대시보드 사용법

### 접속
```bash
# 모니터링 스택 시작
docker compose -f docker/compose.monitoring.yml up -d

# 브라우저에서 접속
open http://localhost:3001
```

**초기 로그인**:
- Username: `admin`
- Password: `admin`
- 첫 로그인 후 비밀번호 변경 권장

### AI Suite Overview 대시보드

**위치**: Dashboards → AI Suite → Overview

**주요 패널**:
1. **Service Health**: 전체 서비스 상태 (Up/Down)
2. **Request Rate**: HTTP 요청 속도 (req/sec)
3. **Latency (p95/p99)**: 응답 시간 분포
4. **Error Rate**: 에러 발생률 (5xx)
5. **RBAC Permission Checks**: 권한 검증 통계
6. **Container Resources**: CPU/메모리 사용률
7. **System Metrics**: 호스트 디스크/네트워크

### 커스텀 쿼리 예시

**Explore 탭에서 Prometheus 데이터소스 선택 후**:

```promql
# 서비스별 요청 수
http_requests_total{job="api-gateway"}

# 5분간 요청 속도
rate(http_requests_total[5m])

# p95 응답 시간
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 에러율
rate(http_requests_total{status_code=~"5.."}[5m])

# RBAC 거부된 요청
rbac_permission_checks_total{result="denied"}
```

---

## 3. Prometheus 직접 쿼리

### 접속
```bash
open http://localhost:9090
```

### 유용한 PromQL 쿼리

**서비스 모니터링**:
```promql
# 모든 서비스 상태 (1=up, 0=down)
up

# API Gateway 요청 수
http_requests_total{job="api-gateway"}

# RAG Service 응답 시간
http_request_duration_seconds{job="rag-service"}

# Embedding Service 처리량
rate(http_requests_total{job="embedding-service"}[5m])
```

**리소스 모니터링**:
```promql
# 컨테이너별 CPU 사용률
rate(container_cpu_usage_seconds_total{name=~".*"}[5m])

# 컨테이너별 메모리 사용량
container_memory_usage_bytes{name=~".*"}

# 호스트 디스크 사용률
(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100
```

**애플리케이션 메트릭**:
```promql
# MCP 도구 실행 횟수
mcp_tool_executions_total{tool="read_file"}

# 승인 요청 통계
approval_requests_total{status="pending"}
```

---

## 4. Loki 로그 검색

### Grafana Explore에서 Loki 사용

**Explore 탭 → Loki 데이터소스 선택**

### LogQL 쿼리 예시

**기본 로그 검색**:
```logql
# MCP Server 로그
{service="mcp-server"}

# 에러 로그만
{service="mcp-server"} |= "error"

# RAG Service ERROR 레벨 로그
{job="rag-service"} | json | level="ERROR"

# 특정 시간대 로그 (최근 1시간)
{service="api-gateway"} [1h]
```

**고급 필터링**:
```logql
# JSON 파싱 후 필드 필터
{job="mcp-server"} | json | user_id="admin"

# 정규식 매칭
{service="rag-service"} |~ "timeout|failed|error"

# 특정 단어 제외
{job="embedding-service"} != "health check"

# 로그 카운트 (메트릭 변환)
count_over_time({service="mcp-server"} |= "error" [5m])
```

---

## 5. 알림 설정

### Alertmanager 접속
```bash
open http://localhost:9093
```

### 알림 규칙 커스터마이징

**파일 위치**: `docker/monitoring/prometheus/alert_rules.yml`

**예시 규칙**:
```yaml
groups:
  - name: custom_alerts
    rules:
      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes > 5e9  # 5GB
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} high memory"
          description: "Memory usage is {{ $value | humanize }}B"

      - alert: SlowAPIResponse
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 3
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "API response time degraded"
          description: "p95 latency is {{ $value }}s (threshold: 3s)"
```

### Slack/Discord/Email 웹훅 연동

**Alertmanager 설정**: `docker/monitoring/alertmanager/alertmanager.yml`

```yaml
route:
  receiver: 'slack-notifications'

receivers:
  - name: 'slack-notifications'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
        title: 'AI Suite Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'discord-notifications'
    webhook_configs:
      - url: 'https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN'
```

**적용**:
```bash
docker compose -f docker/compose.monitoring.yml restart alertmanager
```

---

## 6. 트러블슈팅

### 메트릭이 수집되지 않을 때

**원인 1: Prometheus 스크래핑 실패**
```bash
# Prometheus 타겟 상태 확인
open http://localhost:9090/targets

# 서비스 메트릭 엔드포인트 직접 확인
curl http://localhost:8002/metrics  # RAG Service
curl http://localhost:8003/metrics  # Embedding
curl http://localhost:8020/metrics  # MCP Server
```

**해결**:
- 서비스가 실행 중인지 확인: `docker compose -f docker/compose.p3.yml ps`
- 헬스체크: `curl http://localhost:8002/health`
- 방화벽/포트 충돌 확인

**원인 2: 서비스에 Prometheus Instrumentator 미적용**
```python
# services/*/app.py 확인
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

---

### Grafana 대시보드가 비어있을 때

**원인 1: 데이터소스 연결 실패**
```bash
# Grafana에서 Configuration → Data Sources 확인
# Prometheus: http://prometheus:9090 (Docker 내부 주소)
# Loki: http://loki:3100
```

**해결**:
```bash
# 모니터링 스택 재시작
docker compose -f docker/compose.monitoring.yml down
docker compose -f docker/compose.monitoring.yml up -d

# 데이터소스 테스트
# Grafana → Configuration → Data Sources → Prometheus → Save & Test
```

**원인 2: 메트릭 수집 간격**
- Prometheus 스크래핑 간격: 15초 (기본)
- 최소 1분 대기 후 대시보드 새로고침

---

### 알림이 발송되지 않을 때

**디버깅 체크리스트**:
```bash
# 1. Alertmanager 실행 확인
docker compose -f docker/compose.monitoring.yml ps alertmanager

# 2. Alert 규칙 로드 확인
open http://localhost:9090/alerts

# 3. Alertmanager 설정 검증
open http://localhost:9093/#/status

# 4. 웹훅 URL 테스트 (Slack/Discord)
curl -X POST YOUR_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text": "Test alert"}'
```

**일반적인 문제**:
- Alert 규칙 `for: 2m` 조건 미충족 (임계값 도달 후 2분 대기 필요)
- Alertmanager route 설정 오류
- 웹훅 URL 만료 또는 권한 문제

---

### 로그가 Loki에 표시되지 않을 때

**원인: Promtail 설정 오류**
```bash
# Promtail 로그 확인
docker logs promtail

# Loki 연결 테스트
curl http://localhost:3100/ready
```

**해결**:
```bash
# Promtail 설정 확인
cat docker/monitoring/promtail/promtail.yml

# 로그 파일 경로 매핑 확인
docker compose -f docker/compose.monitoring.yml config | grep -A 5 promtail

# 재시작
docker compose -f docker/compose.monitoring.yml restart promtail loki
```

---

## 7. 모니터링 모범 사례

### 정기 점검 체크리스트
- [ ] 주간: Grafana 대시보드 리뷰 (이상 패턴 확인)
- [ ] 주간: Alertmanager 알림 히스토리 검토
- [ ] 월간: Prometheus 데이터 retention 확인 (기본 30일)
- [ ] 월간: 디스크 사용량 모니터링 (로그/메트릭 저장소)

### 성능 최적화
```bash
# Prometheus Retention 조정 (디스크 절약)
# docker/compose.monitoring.yml
--storage.tsdb.retention.time=7d  # 30d → 7d로 단축

# 샘플링 간격 조정 (부하 감소)
scrape_interval: 30s  # 15s → 30s
```

### 주요 메트릭 모니터링 대상
1. **가용성**: `up` (서비스 정상 여부)
2. **응답 시간**: `http_request_duration_seconds` p95/p99
3. **에러율**: `http_requests_total{status_code=~"5.."}`
4. **리소스**: CPU/메모리 사용률 80% 이하 유지
5. **디스크**: 여유 공간 20% 이상 유지

---

## 8. 참고 자료

- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Grafana 튜토리얼](https://grafana.com/tutorials/)
- [Loki LogQL 가이드](https://grafana.com/docs/loki/latest/logql/)
- [Alertmanager 설정](https://prometheus.io/docs/alerting/latest/configuration/)

**프로젝트 관련 문서**:
- `docker/compose.monitoring.yml` - 모니터링 스택 구성
- `docker/monitoring/prometheus/prometheus.yml` - Prometheus 설정
- `docker/monitoring/grafana/dashboards/ai-suite-overview.json` - 대시보드 JSON
- `docs/ops/SERVICE_RELIABILITY.md` - 서비스 안정성 가이드
