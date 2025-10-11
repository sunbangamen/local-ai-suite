"""
MCP Server Package - 보안이 강화된 Model Context Protocol 서버

이 패키지는 다음과 같은 보안 개선사항을 포함합니다:
- AST 기반 코드 보안 검증
- 경로 탈출 방지가 강화된 파일 시스템 API
- UTF-8 한국어 처리 개선
"""

from .security import SecurityValidator, SecurityError, SecureExecutionEnvironment
from .safe_api import (
    SafeFileAPI,
    SafeCommandExecutor,
    SecurePathValidator,
    secure_resolve_path,
)

__version__ = "1.1.0"
__all__ = [
    "SecurityValidator",
    "SecurityError",
    "SecureExecutionEnvironment",
    "SafeFileAPI",
    "SafeCommandExecutor",
    "SecurePathValidator",
    "secure_resolve_path",
]
