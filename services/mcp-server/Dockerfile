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

# Git 안전 디렉토리 설정 (workspace mount path and main repo)
RUN git config --global --add safe.directory /mnt/workspace && \
    git config --global --add safe.directory /mnt/workspace/.git-main && \
    git config --global --add safe.directory /mnt/e/local-ai-suite || true

# Playwright 브라우저 설치
RUN playwright install --with-deps chromium

# 애플리케이션 및 보안 모듈 복사
COPY app.py security.py safe_api.py sandbox.py security_admin.py __init__.py .

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8020/health || exit 1

# 기본 포트 (MCP 서버 + Security Admin API)
EXPOSE 8020 8021

# 실행 (HTTP 모드로 헬스체크 서버 및 보안 관리 API 실행)
CMD ["python", "app.py", "--http"]