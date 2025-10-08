FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (Playwright + Docker + Enhanced Security)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xvfb \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Git 설정 (안전 디렉토리 + 사용자 정보)
RUN git config --global --add safe.directory /mnt/workspace && \
    git config --global --add safe.directory /mnt/workspace/.git-main && \
    git config --global --add safe.directory /mnt/e/local-ai-suite && \
    git config --global user.name "MCP Server" && \
    git config --global user.email "mcp@local-ai-suite.local" || true

# Playwright 브라우저 설치
RUN playwright install --with-deps chromium

# 애플리케이션 및 보안 모듈 복사
COPY app.py security.py safe_api.py sandbox.py security_admin.py rate_limiter.py __init__.py .

# RBAC 및 감사 로깅 모듈 복사 (Issue #8)
COPY settings.py security_database.py rbac_manager.py audit_logger.py rbac_middleware.py .

# 보안 스크립트 및 스키마 복사
COPY scripts/ ./scripts/

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8020/health || exit 1

# 기본 포트 (MCP 서버 + Security Admin API)
EXPOSE 8020 8021

# 실행 (HTTP 모드로 헬스체크 서버 및 보안 관리 API 실행)
CMD ["python", "app.py", "--http"]