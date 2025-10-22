#!/usr/bin/env python3
"""
MCP Server Security Module - AST 기반 코드 보안 검증기
"""

import ast
import os
from typing import Any, Dict


class SecurityError(Exception):
    """보안 검증 실패 시 발생하는 예외"""

    pass


class SecurityValidator:
    """AST 기반 코드 보안 검증기"""

    # 기본 허용 모듈 (기본 파이썬 모듈들 포함)
    ALLOWED_MODULES = {
        # 기본 시스템 모듈 (안전한 것들)
        "os",
        "sys",
        "pathlib",
        "platform",
        "tempfile",
        "warnings",
        # 기본 내장 모듈
        "json",
        "datetime",
        "math",
        "random",
        "string",
        "collections",
        "itertools",
        "functools",
        "re",
        "time",
        "uuid",
        "base64",
        "hashlib",
        "decimal",
        "fractions",
        "statistics",
        "typing",
        "enum",
        "dataclasses",
        # 데이터 처리
        "csv",
        "xml",
        "html",
        "urllib.parse",
        "urllib.request",
        "http",
        "email",
        "mimetypes",
        "encodings",
        "codecs",
        # 파일/경로 처리 (SafeFileAPI와 함께 사용)
        "glob",
        "fnmatch",
        "linecache",
        "filecmp",
        # 허용된 외부 모듈 (설치된 경우에만)
        "requests",
        "aiofiles",
        "httpx",
        "asyncio",
    }

    # 위험한 모듈 거부 목록 (deny-list)
    DENY_MODULES = {
        # 프로세스 실행
        "subprocess",
        "multiprocessing",
        "threading",
        "concurrent.futures",
        # 시스템 접근
        "ctypes",
        "winreg",
        "mmap",
        "fcntl",
        "termios",
        "tty",
        "pty",
        # 네트워크 (제한적 허용 - requests는 OK)
        "socket",
        "ssl",
        "ftplib",
        "telnetlib",
        "smtplib",
        "poplib",
        "imaplib",
        # 파일 시스템 조작
        "shutil",
        "zipfile",
        "tarfile",
        "gzip",
        "bz2",
        "lzma",
        # 코드 실행/수정
        "imp",
        "importlib",
        "pkgutil",
        "runpy",
        "code",
        "codeop",
        # 시스템 정보/제어
        "resource",
        "signal",
        "syslog",
        "logging.handlers",
    }

    # 위험한 내장 함수들 (동적 import 우회 차단 강화)
    DANGEROUS_FUNCTIONS = {
        "__import__",
        "exec",
        "eval",
        "compile",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "open",  # 파일 접근은 SafeFileAPI를 통해서만
        # 동적 import 우회 방지
        "import_module",  # importlib.import_module 차단
        "reload",  # importlib.reload 차단
    }

    # 위험한 속성 접근 (동적 import 우회 차단 강화)
    DANGEROUS_ATTRIBUTES = {
        "__builtins__",
        "__globals__",
        "__locals__",
        "__dict__",
        "__class__",
        "__bases__",
        "__mro__",
        # importlib 모듈 우회 방지
        "import_module",  # importlib.import_module 접근
        "reload",  # importlib.reload 접근
        "__import_module__",  # 대체 이름으로 우회 시도
    }

    def __init__(self, security_level: str = "normal"):
        """
        보안 검증기 초기화

        Args:
            security_level: 보안 수준 (strict|normal|legacy)
        """
        self.security_level = security_level

        # 보안 수준에 따른 설정 조정
        if security_level == "strict":
            # 엄격한 모드: 최소한의 모듈만 허용 (화이트리스트)
            self.allowed_modules = {
                "pathlib",
                "json",
                "datetime",
                "math",
                "string",
                "re",
                "time",
                "os",
                "sys",  # 기본 모듈 추가
            }
        elif security_level == "legacy":
            # 레거시 모드: 기존 키워드 필터 사용
            self.allowed_modules = None
        else:
            # 일반 모드: deny-list 방식 (기본 모듈들 허용)
            self.allowed_modules = self.ALLOWED_MODULES.copy()

    def validate_code(self, code: str) -> bool:
        """
        코드 보안성 검증

        Args:
            code: 검증할 Python 코드

        Returns:
            bool: 코드가 안전하면 True

        Raises:
            SecurityError: 보안 위험이 발견된 경우
        """
        if self.security_level == "legacy":
            return self._legacy_validation(code)

        try:
            tree = ast.parse(code)
            return self._check_ast_nodes(tree)
        except SyntaxError as e:
            raise SecurityError(f"Syntax error in code: {str(e)}")

    def _legacy_validation(self, code: str) -> bool:
        """기존 키워드 기반 검증 (레거시 모드) - deny-list 기반"""
        # 레거시 모드에서도 위험한 모듈만 차단
        dangerous_modules = ["subprocess", "shutil", "ctypes", "socket", "importlib"]

        for module in dangerous_modules:
            if f"import {module}" in code or f"from {module}" in code:
                raise SecurityError(f"Dangerous module import blocked (legacy mode): {module}")

        # 동적 import 우회 시도도 레거시 모드에서 차단
        dangerous_patterns = [
            "import_module",
            "__import__",
            "importlib.import_module",
            "importlib.reload",
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                raise SecurityError(f"Dynamic import bypass blocked (legacy mode): {pattern}")

        return True

    def _check_ast_nodes(self, tree: ast.AST) -> bool:
        """화이트리스트 기반 AST 노드 검사"""
        for node in ast.walk(tree):
            # Import 문 검사
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._check_imports(node)

            # 함수 호출 검사
            elif isinstance(node, ast.Call):
                self._check_function_call(node)

            # 속성 접근 검사 (동적 import 우회 차단 포함)
            elif isinstance(node, ast.Attribute):
                self._check_attribute_access(node)
                self._check_dynamic_import_bypass(node)

            # 이름 접근 검사
            elif isinstance(node, ast.Name):
                self._check_name_access(node)

        return True


def detect_dangerous_patterns(code: str, security_level: str = "normal") -> Dict[str, Any]:
    """
    Helper function that returns a user-friendly report about potential security issues.

    Args:
        code: The Python code to inspect.
        security_level: Security profile used by SecurityValidator.

    Returns:
        Dictionary with `is_safe` flag and list of `issues`.
    """
    validator = SecurityValidator(security_level=security_level)
    try:
        validator.validate_code(code)
        return {"is_safe": True, "issues": []}
    except SecurityError as exc:
        return {"is_safe": False, "issues": [str(exc)]}

    def _check_imports(self, node):
        """Import 문 보안성 검사 (deny-list 우선 방식)"""
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules = [node.module.split(".")[0]]
            else:
                modules = []  # relative import
        else:
            return

        # 1단계: 위험 모듈 차단 (deny-list 우선)
        for module in modules:
            if module in self.DENY_MODULES:
                raise SecurityError(f"Dangerous module import blocked: {module}")

        # 2단계: strict 모드에서만 허용 목록 검사
        if self.security_level == "strict":
            for module in modules:
                if module not in self.allowed_modules:
                    raise SecurityError(f"Module not in strict whitelist: {module}")

    def _check_function_call(self, node: ast.Call):
        """함수 호출 보안성 검사"""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.DANGEROUS_FUNCTIONS:
                raise SecurityError(f"Dangerous function call blocked: {func_name}")

        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in self.DANGEROUS_FUNCTIONS:
                raise SecurityError(f"Dangerous method call blocked: {attr_name}")

    def _check_attribute_access(self, node: ast.Attribute):
        """속성 접근 보안성 검사"""
        if node.attr in self.DANGEROUS_ATTRIBUTES:
            raise SecurityError(f"Dangerous attribute access blocked: {node.attr}")

    def _check_name_access(self, node: ast.Name):
        """이름 접근 보안성 검사"""
        if node.id in self.DANGEROUS_FUNCTIONS:
            # 함수 이름 자체에 대한 참조도 차단
            if isinstance(node.ctx, ast.Load):
                raise SecurityError(f"Access to dangerous function blocked: {node.id}")

    def _check_dynamic_import_bypass(self, node: ast.Attribute):
        """동적 import 우회 시도 검사 (importlib.import_module 등)"""
        # importlib.import_module() 패턴 검사
        if (
            node.attr == "import_module"
            and isinstance(node.value, ast.Name)
            and node.value.id == "importlib"
        ):
            raise SecurityError("Dynamic import bypass blocked: importlib.import_module")

        # importlib.reload() 패턴 검사
        if (
            node.attr == "reload"
            and isinstance(node.value, ast.Name)
            and node.value.id == "importlib"
        ):
            raise SecurityError("Dynamic import bypass blocked: importlib.reload")

        # __import__ 속성 접근 검사
        if node.attr == "__import__":
            raise SecurityError("Dynamic import bypass blocked: __import__ attribute access")

        # 기타 알려진 우회 패턴들
        dangerous_import_patterns = {
            "util": "importlib.util",
            "machinery": "importlib.machinery",
            "find_spec": "importlib.util.find_spec",
            "spec_from_loader": "importlib.util.spec_from_loader",
        }

        if node.attr in dangerous_import_patterns:
            raise SecurityError(
                f"Dynamic import bypass blocked: {dangerous_import_patterns[node.attr]}"
            )


class SecureExecutionEnvironment:
    """보안이 강화된 코드 실행 환경 (Deprecated - EnhancedSandbox 사용 권장)"""

    def __init__(self, validator: SecurityValidator):
        self.validator = validator
        self._use_enhanced_sandbox = os.getenv("USE_ENHANCED_SANDBOX", "true").lower() == "true"

    def execute_python_code(self, code: str, timeout: int = 30) -> dict:
        """
        보안 검증 후 Python 코드 실행

        Args:
            code: 실행할 Python 코드
            timeout: 타임아웃 (초)

        Returns:
            dict: 실행 결과 (stdout, stderr, returncode, success)
        """
        # Enhanced Sandbox 사용 권장
        if self._use_enhanced_sandbox:
            try:
                from .sandbox import get_enhanced_sandbox
                import asyncio

                # 비동기 실행을 위한 래퍼
                async def _async_execute():
                    sandbox = get_enhanced_sandbox()
                    return await sandbox.execute_code(code, session_id="legacy_api")

                # 새 이벤트 루프에서 실행
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 이미 루프가 실행 중인 경우 새 스레드에서 실행
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, _async_execute())
                            result = future.result(timeout=timeout)
                    else:
                        result = loop.run_until_complete(_async_execute())
                except RuntimeError:
                    # 루프 없는 경우 새로 생성
                    result = asyncio.run(_async_execute())

                return result
            except ImportError:
                # sandbox 모듈이 없으면 레거시 실행
                pass

        # 레거시 실행 방식 (폴백)
        # 1단계: AST 보안 검증
        try:
            self.validator.validate_code(code)
        except SecurityError as e:
            return {
                "stdout": "",
                "stderr": f"Security validation failed: {str(e)}",
                "returncode": 1,
                "success": False,
            }

        # 2단계: 기본 subprocess 실행
        import subprocess
        import sys

        try:
            # 동기 subprocess 실행 (루프 충돌 없음)
            proc = subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getenv("PROJECT_ROOT", "/mnt/workspace"),
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=timeout)

            return {
                "stdout": stdout or "",
                "stderr": stderr or "",
                "returncode": proc.returncode or 0,
                "success": proc.returncode == 0,
                "sandbox_type": "legacy",
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            return {
                "stdout": "",
                "stderr": f"Timeout ({timeout}초)",
                "returncode": 124,
                "success": False,
                "sandbox_type": "legacy",
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "returncode": 1,
                "success": False,
                "sandbox_type": "legacy",
            }

    async def execute_python_code_async(self, code: str, timeout: int = 30) -> dict:
        """
        비동기 보안 검증 후 Python 코드 실행 (이미 루프가 실행 중인 경우)

        Args:
            code: 실행할 Python 코드
            timeout: 타임아웃 (초)

        Returns:
            dict: 실행 결과 (stdout, stderr, returncode, success)
        """
        # 1단계: AST 보안 검증
        try:
            self.validator.validate_code(code)
        except SecurityError as e:
            return {
                "stdout": "",
                "stderr": f"Security validation failed: {str(e)}",
                "returncode": 1,
                "success": False,
            }

        # 2단계: 비동기 subprocess 실행
        return await self._execute_subprocess(code, timeout)

    async def _execute_subprocess(self, code: str, timeout: int):
        """실제 비동기 subprocess 실행"""
        import sys
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getenv("PROJECT_ROOT", "/mnt/workspace"),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            return {
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "returncode": proc.returncode or 0,
                "success": proc.returncode == 0,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "stdout": "",
                "stderr": f"Timeout ({timeout}초)",
                "returncode": 124,
                "success": False,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "returncode": 1,
                "success": False,
            }


def get_security_validator() -> SecurityValidator:
    """환경변수 기반 보안 검증기 인스턴스 생성"""
    security_level = os.getenv("MCP_SECURITY_LEVEL", "normal")
    return SecurityValidator(security_level)


def get_secure_executor() -> SecureExecutionEnvironment:
    """보안 실행 환경 인스턴스 생성"""
    validator = get_security_validator()
    return SecureExecutionEnvironment(validator)
