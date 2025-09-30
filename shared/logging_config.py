#!/usr/bin/env python3
"""
Shared Logging Configuration for Local AI Suite
모든 Python 서비스에서 공통으로 사용하는 로깅 설정
"""

import logging
import logging.handlers
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON 형식 로그 포맷터"""

    def __init__(self, service_name: str = None):
        super().__init__()
        self.service_name = service_name or "unknown"

    def format(self, record: logging.LogRecord) -> str:
        # 기본 로그 데이터
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # 추가 컨텍스트 정보
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'session_id'):
            log_data["session_id"] = record.session_id
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'endpoint'):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, 'method'):
            log_data["method"] = record.method
        if hasattr(record, 'status_code'):
            log_data["status_code"] = record.status_code
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms

        # 예외 정보
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """일반 텍스트 형식 로그 포맷터 (개발용)"""

    def __init__(self, service_name: str = None):
        super().__init__()
        self.service_name = service_name or "unknown"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        module = f"{record.module}:{record.lineno}"
        message = record.getMessage()

        # 추가 컨텍스트
        context_parts = []
        if hasattr(record, 'request_id'):
            context_parts.append(f"req:{record.request_id[:8]}")
        if hasattr(record, 'session_id'):
            context_parts.append(f"sess:{record.session_id[:8]}")
        if hasattr(record, 'endpoint'):
            context_parts.append(f"{record.method} {record.endpoint}")

        context = f"[{','.join(context_parts)}]" if context_parts else ""

        log_line = f"{timestamp} | {self.service_name} | {level:8} | {module:20} | {message} {context}"

        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


def setup_logging(
    service_name: str,
    log_level: str = None,
    structured_logging: bool = None,
    log_dir: str = None,
    enable_file_logging: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    공통 로깅 설정

    Args:
        service_name: 서비스 이름 (예: "rag", "mcp-server", "memory-api")
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured_logging: JSON 형식 로깅 여부
        log_dir: 로그 파일 저장 디렉토리
        enable_file_logging: 파일 로깅 활성화 여부
        max_bytes: 로그 파일 최대 크기
        backup_count: 로그 파일 백업 개수

    Returns:
        구성된 로거 인스턴스
    """
    # 환경변수에서 기본값 읽기
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    structured_logging = structured_logging if structured_logging is not None else \
        os.getenv("STRUCTURED_LOGGING", "true").lower() == "true"
    log_dir = log_dir or os.getenv("LOG_DIR", "/mnt/e/ai-data/logs")

    # 로거 생성
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level))

    # 기존 핸들러 제거 (중복 방지)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 포맷터 선택
    if structured_logging:
        formatter = JSONFormatter(service_name)
    else:
        formatter = PlainFormatter(service_name)

    # 콘솔 핸들러 (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (선택적)
    if enable_file_logging:
        try:
            # 로그 디렉토리 생성
            log_dir_path = Path(log_dir)
            log_dir_path.mkdir(parents=True, exist_ok=True)

            # 로그 파일 경로
            log_file = log_dir_path / f"{service_name}.log"

            # 로테이팅 파일 핸들러
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info(f"파일 로깅 활성화: {log_file}")

        except Exception as e:
            logger.warning(f"파일 로깅 설정 실패: {e}")

    # 로깅 설정 완료 메시지
    logger.info(f"로깅 설정 완료", extra={
        "service": service_name,
        "log_level": log_level,
        "structured_logging": structured_logging,
        "file_logging": enable_file_logging
    })

    return logger


def get_request_logger(logger: logging.Logger, request_id: str = None) -> logging.LoggerAdapter:
    """
    요청별 로거 어댑터 생성

    Args:
        logger: 기본 로거
        request_id: 요청 ID (없으면 자동 생성)

    Returns:
        요청 ID가 포함된 로거 어댑터
    """
    if not request_id:
        request_id = str(uuid.uuid4())[:8]

    class RequestLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            extra = kwargs.get('extra', {})
            extra['request_id'] = self.extra['request_id']
            kwargs['extra'] = extra
            return msg, kwargs

    return RequestLoggerAdapter(logger, {'request_id': request_id})


def log_request_response(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    request_id: str = None,
    user_id: str = None,
    error: str = None
):
    """
    HTTP 요청/응답 로깅

    Args:
        logger: 로거 인스턴스
        method: HTTP 메서드
        endpoint: 엔드포인트 경로
        status_code: 응답 상태 코드
        duration_ms: 처리 시간 (밀리초)
        request_id: 요청 ID
        user_id: 사용자 ID
        error: 에러 메시지
    """
    level = logging.ERROR if status_code >= 500 else \
           logging.WARNING if status_code >= 400 else \
           logging.INFO

    message = f"{method} {endpoint} -> {status_code} ({duration_ms:.1f}ms)"
    if error:
        message += f" | Error: {error}"

    extra = {
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": duration_ms
    }

    if request_id:
        extra["request_id"] = request_id
    if user_id:
        extra["user_id"] = user_id

    logger.log(level, message, extra=extra)


def log_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = None,
    tags: Dict[str, str] = None
):
    """
    메트릭 로깅 (Prometheus 수집용)

    Args:
        logger: 로거 인스턴스
        metric_name: 메트릭 이름
        value: 메트릭 값
        unit: 단위
        tags: 태그 딕셔너리
    """
    extra = {
        "metric_name": metric_name,
        "metric_value": value
    }

    if unit:
        extra["metric_unit"] = unit
    if tags:
        extra.update({f"tag_{k}": v for k, v in tags.items()})

    logger.info(f"METRIC {metric_name}={value}", extra=extra)


# 편의 함수들
def create_service_logger(service_name: str) -> logging.Logger:
    """서비스용 로거 빠른 생성"""
    return setup_logging(service_name)


def create_script_logger(script_name: str) -> logging.Logger:
    """스크립트용 로거 빠른 생성 (파일 로깅 비활성화)"""
    return setup_logging(script_name, enable_file_logging=False)


# 예제 사용법
if __name__ == "__main__":
    # 테스트 로거 생성
    test_logger = setup_logging("test-service")

    # 기본 로깅
    test_logger.info("서비스 시작됨")
    test_logger.warning("경고 메시지")

    # 요청 로깅
    req_logger = get_request_logger(test_logger, "req-123")
    req_logger.info("사용자 요청 처리 중")

    # HTTP 요청/응답 로깅
    log_request_response(
        test_logger,
        "POST", "/api/chat",
        200, 150.5,
        request_id="req-123"
    )

    # 메트릭 로깅
    log_metric(
        test_logger,
        "response_time_ms",
        150.5,
        unit="milliseconds",
        tags={"endpoint": "/api/chat", "model": "chat-7b"}
    )

    test_logger.info("테스트 완료")