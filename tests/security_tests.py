#!/usr/bin/env python3
"""
MCP Security Test Suite - 보안 검증 및 침투 테스트
"""

import pytest
import sys
import os
import json
import asyncio
from pathlib import Path

# 테스트를 위한 상대 임포트 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'mcp-server'))

from security import SecurityValidator, SecurityError, SecureExecutionEnvironment
from safe_api import SafeFileAPI, SafeCommandExecutor, SecurePathValidator


class TestSecurityValidator:
    """AST 검증기 보안 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.validator = SecurityValidator("normal")
        self.strict_validator = SecurityValidator("strict")
        self.legacy_validator = SecurityValidator("legacy")

    def test_safe_code_execution(self):
        """안전한 코드 실행 테스트"""
        safe_codes = [
            "print('Hello World')",
            "import pathlib; p = pathlib.Path('.')",
            "import json; data = json.dumps({'key': 'value'})",
            "import math; result = math.sqrt(16)",
            "x = 1 + 2; print(x)"
        ]

        for code in safe_codes:
            assert self.validator.validate_code(code) == True, f"Safe code should pass: {code}"

    def test_dangerous_imports_blocked(self):
        """위험한 모듈 임포트 차단 테스트 (deny-list 방식)"""
        dangerous_codes = [
            "import subprocess",
            "from subprocess import call",
            "import shutil",
            "import ctypes",
            "import socket",
            "import multiprocessing",
            "from ctypes import windll"
        ]

        for code in dangerous_codes:
            with pytest.raises(SecurityError):
                self.validator.validate_code(code)

    def test_safe_basic_modules_allowed(self):
        """기본 파이썬 모듈 허용 테스트 (새로운 deny-list 방식)"""
        safe_codes = [
            "import os",
            "import sys",
            "from os import path",
            "from sys import version",
            "import pathlib",
            "import platform"
        ]

        for code in safe_codes:
            assert self.validator.validate_code(code) == True, f"Safe basic module should pass: {code}"

    def test_dangerous_functions_blocked(self):
        """위험한 함수 호출 차단 테스트"""
        dangerous_codes = [
            "exec('print(1)')",
            "eval('1+1')",
            "__import__('os')",
            "compile('print(1)', '<string>', 'exec')",
            "getattr(__builtins__, 'exec')",
            "globals()['__builtins__']",
        ]

        for code in dangerous_codes:
            with pytest.raises(SecurityError):
                self.validator.validate_code(code)

    def test_attribute_access_blocked(self):
        """위험한 속성 접근 차단 테스트"""
        dangerous_codes = [
            "print.__globals__",
            "[].__class__.__bases__",
            "().__class__.__mro__",
        ]

        for code in dangerous_codes:
            with pytest.raises(SecurityError):
                self.validator.validate_code(code)

    def test_import_bypass_attempts(self):
        """동적 import 우회 시도 차단 테스트"""
        bypass_codes = [
            "importlib.import_module('os')",
            "__import__('subprocess')",
            "globals()['__import__']('os')",
            "getattr(__builtins__, '__import__')('os')",
        ]

        for code in bypass_codes:
            with pytest.raises(SecurityError):
                self.validator.validate_code(code)

    def test_strict_mode_restrictions(self):
        """엄격 모드 제한사항 테스트"""
        # requests는 normal 모드에서는 허용되지만 strict 모드에서는 차단
        code = "import requests"

        # Normal 모드에서는 허용 (requests가 ALLOWED_MODULES에 있음)
        assert self.validator.validate_code(code) == True

        # Strict 모드에서는 차단 (제한된 모듈 목록)
        with pytest.raises(SecurityError):
            self.strict_validator.validate_code(code)

    def test_deny_list_priority(self):
        """거부 목록 우선순위 테스트 - deny-list가 우선 적용되는지 확인"""
        # subprocess는 DENY_MODULES에 있으므로 normal 모드에서도 차단되어야 함
        dangerous_codes = [
            "import subprocess",
            "import ctypes",
            "import socket",
            "from multiprocessing import Process"
        ]

        for code in dangerous_codes:
            with pytest.raises(SecurityError) as exc_info:
                self.validator.validate_code(code)
            assert "Dangerous module import blocked" in str(exc_info.value)

    def test_legacy_mode_compatibility(self):
        """레거시 모드 호환성 테스트 (업데이트된 deny-list 기반)"""
        # 레거시 모드에서는 기본 키워드 필터만 적용 (위험한 모듈만 차단)
        legacy_blocked_codes = [
            "import subprocess",
            "from shutil import rmtree",
            "import ctypes",
            "import socket"
        ]

        for code in legacy_blocked_codes:
            with pytest.raises(SecurityError):
                self.legacy_validator.validate_code(code)

        # 기본 모듈들은 레거시 모드에서도 허용
        legacy_allowed_codes = [
            "import os",
            "import sys",
            "import pathlib",
            "import json"
        ]

        for code in legacy_allowed_codes:
            assert self.legacy_validator.validate_code(code) == True, f"Legacy mode should allow: {code}"


class TestSecurePathValidator:
    """경로 검증기 보안 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.validator = SecurePathValidator()

    def test_path_traversal_blocked(self):
        """경로 탈출 시도 차단 테스트"""
        traversal_paths = [
            "../../../etc/passwd",
            "../../root/.ssh/id_rsa",
            "../../../../../bin/bash",
            "..\\..\\..\\windows\\system32\\config\\sam",  # Windows 경로
        ]

        for path in traversal_paths:
            with pytest.raises(SecurityError):
                self.validator.validate_and_resolve_path(path)

    def test_absolute_system_paths_blocked(self):
        """절대 시스템 경로 접근 차단 테스트"""
        system_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/.ssh/id_rsa",
            "/bin/bash",
            "/sbin/init",
            "/usr/bin/sudo"
        ]

        for path in system_paths:
            with pytest.raises(SecurityError):
                self.validator.validate_and_resolve_path(path)

    def test_sensitive_files_blocked(self):
        """민감한 파일 접근 차단 테스트"""
        sensitive_files = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/.bash_history",
            "/root/.ssh/id_rsa"
        ]

        for path in sensitive_files:
            with pytest.raises(SecurityError):
                self.validator.validate_and_resolve_path(path)

    def test_safe_paths_allowed(self):
        """안전한 경로 허용 테스트"""
        # 주의: 이 테스트는 실제 파일 시스템 구조에 의존할 수 있음
        safe_paths = [
            "test.txt",
            "./documents/readme.md",
            "data/config.json"
        ]

        for path in safe_paths:
            try:
                # 경로 검증만 테스트 (파일이 실제로 존재하지 않을 수 있음)
                resolved = self.validator.validate_and_resolve_path(path)
                assert isinstance(resolved, Path)
            except (FileNotFoundError, OSError):
                # 파일이 존재하지 않는 것은 OK, 보안 에러가 아니면 됨
                pass

    def test_working_dir_handling(self):
        """작업 디렉토리 처리 테스트"""
        # 상대경로 + 작업디렉토리
        try:
            resolved = self.validator.validate_and_resolve_path("test.txt", "/mnt/workspace")
            assert str(resolved).startswith("/mnt/workspace") or str(resolved).startswith("/mnt/host")
        except SecurityError:
            # 보안 에러가 아닌 다른 에러라면 OK
            pass

    def test_windows_slash_paths_blocked(self):
        """Windows 슬래시 표기 경로 차단 테스트 (코덱스 요청사항)"""
        windows_slash_paths = [
            # Windows 시스템 경로 (슬래시 표기)
            "C:/Windows/System32/config/SAM",
            "C:/Users/Administrator/NTUSER.DAT",
            "C:/Windows/System32/config/SECURITY",
            "C:/Program Files/malicious.exe",
            "C:/ProgramData/Microsoft/Crypto/RSA",
            # Windows 시스템 경로 (백슬래시 표기)
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Users\\Administrator\\NTUSER.DAT",
            # 혼합 경로 (슬래시 + 백슬래시)
            "C:/Windows\\System32/config",
            "C:\\Users/Administrator",
            # 특수 Windows 경로 패턴
            "\\\\?\\C:/Windows/System32",
            "\\\\.\\pipe/malicious"
        ]

        for path in windows_slash_paths:
            with pytest.raises(SecurityError) as exc_info:
                self.validator.validate_and_resolve_path(path)
            # 에러 메시지에 적절한 차단 내용 포함 확인
            error_msg = str(exc_info.value).lower()
            assert ('system' in error_msg or 'blocked' in error_msg or 'windows' in error_msg or 'sensitive' in error_msg), f"Expected path blocking error for: {path}"


class TestSafeFileAPI:
    """안전한 파일 API 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.api = SafeFileAPI()

    def test_read_nonexistent_file(self):
        """존재하지 않는 파일 읽기 테스트"""
        with pytest.raises(FileNotFoundError):
            self.api.read_text("nonexistent_file_12345.txt")

    def test_read_system_file_blocked(self):
        """시스템 파일 읽기 차단 테스트"""
        system_files = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/.ssh/id_rsa"
        ]

        for path in system_files:
            with pytest.raises(SecurityError):
                self.api.read_text(path)

    def test_write_system_path_blocked(self):
        """시스템 경로 쓰기 차단 테스트"""
        system_paths = [
            "/etc/malicious.txt",
            "/bin/trojan",
            "/root/backdoor.sh"
        ]

        for path in system_paths:
            with pytest.raises(SecurityError):
                self.api.write_text(path, "malicious content")

    def test_list_system_directory_blocked(self):
        """시스템 디렉토리 목록 차단 테스트"""
        system_dirs = [
            "/etc",
            "/root",
            "/bin"
        ]

        for path in system_dirs:
            with pytest.raises(SecurityError):
                self.api.list_directory(path)


class TestSafeCommandExecutor:
    """안전한 명령어 실행기 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        path_validator = SecurePathValidator()
        self.executor = SafeCommandExecutor(path_validator)

    @pytest.mark.asyncio
    async def test_dangerous_commands_blocked(self):
        """위험한 명령어 차단 테스트"""
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf /var",
            "chmod 777 /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
            "shutdown -h now",
            "kill -9 1"
        ]

        for command in dangerous_commands:
            with pytest.raises(SecurityError):
                await self.executor.execute_command(command)

    @pytest.mark.asyncio
    async def test_safe_commands_allowed(self):
        """안전한 명령어 허용 테스트"""
        safe_commands = [
            "echo 'hello world'",
            "pwd",
            "ls -la",
            "python --version"
        ]

        for command in safe_commands:
            try:
                result = await self.executor.execute_command(command)
                # 명령어 실행 결과 구조 확인
                assert "command" in result
                assert "stdout" in result
                assert "stderr" in result
                assert "returncode" in result
                assert "success" in result
            except Exception as e:
                # 명령어가 시스템에 없을 수 있지만, 보안 에러는 아니어야 함
                assert not isinstance(e, SecurityError)


class TestIntegrationScenarios:
    """통합 시나리오 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.validator = SecurityValidator("normal")
        self.executor = SecureExecutionEnvironment(self.validator)

    def test_code_execution_with_safe_modules(self):
        """안전한 모듈을 사용한 코드 실행 테스트 (동기 실행으로 변경)"""
        safe_code = """
import json
import pathlib
import math
import os
import sys

data = {'result': math.sqrt(16), 'platform': sys.platform}
print(json.dumps(data, indent=2))
"""
        result = self.executor.execute_python_code(safe_code)
        assert result["success"] == True
        assert "4.0" in result["stdout"] or "4" in result["stdout"]

    @pytest.mark.asyncio
    async def test_async_code_execution_with_safe_modules(self):
        """비동기 안전한 모듈 코드 실행 테스트"""
        safe_code = """
import json
import pathlib
import math

data = {'result': math.sqrt(16)}
print(json.dumps(data, indent=2))
"""
        result = await self.executor.execute_python_code_async(safe_code)
        assert result["success"] == True
        assert "4.0" in result["stdout"] or "4" in result["stdout"]

    def test_malicious_code_blocked(self):
        """악성 코드 실행 차단 테스트 (업데이트된 deny-list 기반)"""
        malicious_codes = [
            "import subprocess; subprocess.call(['rm', '-rf', '/'])",
            "__import__('subprocess').call(['rm', '-rf', '/'])",
            "exec(\"import subprocess; subprocess.call(['malicious'])\")",
            "import ctypes; ctypes.windll.kernel32.ExitProcess(0)",
            "import socket; socket.socket().connect(('evil.com', 80))"
        ]

        for code in malicious_codes:
            result = self.executor.execute_python_code(code)
            assert result["success"] == False
            assert "Security validation failed" in result["stderr"] or "Security" in result["stderr"]

    def test_os_module_safe_usage(self):
        """os 모듈의 안전한 사용 테스트 (새 deny-list 방식에서 허용)"""
        safe_os_code = """
import os
print(f"Current directory: {os.getcwd()}")
print(f"Environment PATH exists: {'PATH' in os.environ}")
"""
        result = self.executor.execute_python_code(safe_os_code)
        assert result["success"] == True
        assert "Current directory:" in result["stdout"]

    def test_sys_module_safe_usage(self):
        """sys 모듈의 안전한 사용 테스트 (새 deny-list 방식에서 허용)"""
        safe_sys_code = """
import sys
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")
"""
        result = self.executor.execute_python_code(safe_sys_code)
        assert result["success"] == True
        assert "Python version:" in result["stdout"]

    def test_json_korean_handling(self):
        """JSON 한국어 처리 테스트"""
        korean_data = {
            "message": "안녕하세요 🌍",
            "description": "한국어 테스트 데이터입니다",
            "emoji": "🚀🔒✅"
        }

        # ensure_ascii=False로 JSON 직렬화
        json_str = json.dumps(korean_data, ensure_ascii=False)
        assert "안녕하세요" in json_str
        assert "🌍" in json_str

        # UTF-8 인코딩/디코딩 테스트
        utf8_bytes = json_str.encode('utf-8')
        decoded_str = utf8_bytes.decode('utf-8')
        restored_data = json.loads(decoded_str)

        assert restored_data["message"] == korean_data["message"]
        assert restored_data["emoji"] == korean_data["emoji"]


if __name__ == "__main__":
    # 직접 실행 시 기본 테스트 수행
    print("🔒 Running MCP Security Tests...")

    # 기본적인 보안 테스트 실행
    validator = SecurityValidator("normal")

    # 1. 안전한 코드 테스트
    try:
        validator.validate_code("import pathlib; print('safe')")
        print("✅ Safe code validation passed")
    except Exception as e:
        print(f"❌ Safe code validation failed: {e}")

    # 2. 위험한 코드 테스트 (deny-list 방식)
    try:
        validator.validate_code("import subprocess; subprocess.call(['rm', '-rf', '/'])")
        print("❌ Dangerous code was allowed (SECURITY ISSUE!)")
    except SecurityError:
        print("✅ Dangerous code blocked successfully")

    # 2-1. 기본 모듈 안전 사용 테스트 (새로운 허용 방식)
    try:
        validator.validate_code("import os; print(os.getcwd())")
        print("✅ Safe os module usage allowed")
    except Exception as e:
        print(f"❌ Safe os module usage failed: {e}")

    # 3. 경로 보안 테스트
    path_validator = SecurePathValidator()
    try:
        path_validator.validate_and_resolve_path("../../../etc/passwd")
        print("❌ Path traversal was allowed (SECURITY ISSUE!)")
    except SecurityError:
        print("✅ Path traversal blocked successfully")

    # 4. JSON UTF-8 테스트
    korean_text = "안녕하세요 🌍"
    json_str = json.dumps({"message": korean_text}, ensure_ascii=False)
    restored = json.loads(json_str)
    if restored["message"] == korean_text:
        print("✅ Korean JSON processing works correctly")
    else:
        print("❌ Korean JSON processing failed")

    print("\n🎯 Basic security tests completed!")
    print("📊 Security approach: Deny-list based (dangerous modules blocked, safe modules allowed)")
    print("💡 Run 'python -m pytest tests/security_tests.py -v' for full test suite")