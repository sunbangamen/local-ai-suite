#!/usr/bin/env python3
"""
Safe API Wrappers - 경로 탈출 방지가 강화된 안전한 파일 시스템 API
"""

import os
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import List, Optional, Dict, Any
import asyncio

try:
    from .security import SecurityError
except ImportError:
    from security import SecurityError


class SecurePathValidator:
    """보안이 강화된 경로 검증기"""

    def __init__(self):
        self.project_root = Path(os.getenv("PROJECT_ROOT", "/mnt/workspace"))
        self.host_root = Path(os.getenv("HOST_ROOT", "/mnt/host"))

        # 위험한 시스템 경로들 (멀티플랫폼 지원)
        self.dangerous_system_paths = {
            # Linux/Unix 시스템 경로
            "/etc", "/root", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
            "/boot", "/sys", "/proc", "/dev", "/var/log", "/var/lib",
            # Windows 시스템 경로
            "C:\\Windows", "C:\\Windows\\System32", "C:\\Windows\\SysWOW64",
            "C:\\Users\\Administrator", "C:\\ProgramData", "C:\\Program Files",
            "C:\\Program Files (x86)", "\\\\.\\pipe", "\\\\.\\mailslot",
            # Windows 특수 경로 패턴
            "\\\\?\\"
        }

        # 민감한 파일들 (멀티플랫폼 지원)
        self.sensitive_files = {
            # Linux/Unix 중요 파일
            "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/sudoers",
            "/root/.ssh", "/root/.bash_history", "/root/.bash_profile",
            "/etc/hosts", "/etc/fstab", "/etc/crontab", "/etc/ssl",
            # Windows 중요 파일
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Windows\\System32\\config\\SYSTEM",
            "C:\\Windows\\System32\\config\\SECURITY",
            "C:\\Users\\Administrator\\NTUSER.DAT",
            "C:\\ProgramData\\Microsoft\\Crypto"
        }

    def validate_and_resolve_path(self, path: str, working_dir: Optional[str] = None) -> Path:
        """
        경로 검증 및 안전한 해석

        Args:
            path: 검증할 경로
            working_dir: 작업 디렉토리 (상대경로의 기준)

        Returns:
            Path: 검증된 절대 경로

        Raises:
            SecurityError: 경로가 안전하지 않은 경우
        """
        # 1단계: 기본 경로 해석
        resolved_path = self._resolve_base_path(path, working_dir)

        # 2단계: 실제 경로 해석 (심볼릭 링크 등 해결)
        try:
            real_path = resolved_path.resolve(strict=False)
        except (OSError, RuntimeError) as e:
            raise SecurityError(f"Path resolution failed: {str(e)}")

        # 3단계: 작업공간 경계 검증
        self._validate_workspace_boundary(real_path, path)

        # 4단계: 시스템 경로 접근 차단 (원본과 해석된 경로 모두 검사)
        self._validate_system_path_access(real_path, path)

        # 5단계: 민감한 파일 접근 차단 (원본과 해석된 경로 모두 검사)
        self._validate_sensitive_file_access(real_path, path)

        # 6단계: 최종 작업공간 경계 재검증 (is_relative_to 활용)
        if hasattr(real_path, 'is_relative_to'):
            workspace_roots = [self.project_root.resolve(), self.host_root.resolve()]
            is_safe = False
            for root in workspace_roots:
                try:
                    if real_path.is_relative_to(root):
                        is_safe = True
                        break
                except (ValueError, OSError):
                    continue
            if not is_safe:
                raise SecurityError(f"Final boundary check failed: {path} -> {real_path}")

        return real_path

    def _resolve_base_path(self, path: str, working_dir: Optional[str] = None) -> Path:
        """기본 경로 해석"""
        if working_dir and not os.path.isabs(path):
            # 상대경로 + 작업디렉토리
            base_path = Path(working_dir) / path
        elif os.path.isabs(path):
            # 절대경로 처리
            if path.startswith(str(self.host_root)):
                # 이미 HOST_ROOT 기준 경로
                base_path = Path(path)
            else:
                # HOST_ROOT에 매핑
                base_path = self.host_root / path.lstrip('/')
        else:
            # 기본: PROJECT_ROOT 기준
            base_path = self.project_root / path

        return base_path

    def _validate_workspace_boundary(self, resolved_path: Path, original_path: str):
        """작업공간 경계 검증"""
        # PROJECT_ROOT와 HOST_ROOT 모두에 대해 검증
        workspace_roots = [
            self.project_root.resolve(),
            self.host_root.resolve()
        ]

        is_within_workspace = False
        for workspace_root in workspace_roots:
            try:
                # Python 3.9+ 방식
                if hasattr(resolved_path, 'is_relative_to'):
                    if resolved_path.is_relative_to(workspace_root):
                        is_within_workspace = True
                        break
                else:
                    # 이전 버전 호환성
                    if str(resolved_path).startswith(str(workspace_root)):
                        is_within_workspace = True
                        break
            except (ValueError, OSError):
                continue

        if not is_within_workspace:
            raise SecurityError(f"Path traversal blocked: {original_path} -> {resolved_path}")

    def _validate_system_path_access(self, resolved_path: Path, original_path: str):
        """시스템 경로 접근 검증 (경로 구분자 정규화 지원)"""
        resolved_str = str(resolved_path)
        original_normalized = os.path.normpath(original_path)

        # 기본 경로 목록
        paths_to_check = [resolved_str, original_path, original_normalized]

        # PureWindowsPath를 사용한 혼합 경로 커버리지
        try:
            # Windows 스타일 정규화 (\\)
            for path in [resolved_str, original_path, original_normalized]:
                if '/' in path or '\\' in path:
                    try:
                        # Windows 경로로 정규화 시도
                        win_path = PureWindowsPath(path)
                        paths_to_check.append(str(win_path.as_posix()))  # POSIX 스타일 (/)
                        paths_to_check.append(str(win_path))  # Windows 스타일 (\\)

                        # POSIX 경로로 정규화 시도
                        posix_path = PurePosixPath(path)
                        paths_to_check.append(str(posix_path))
                    except (ValueError, OSError):
                        # 잘못된 경로 형식이면 무시
                        pass
        except ImportError:
            # PurePath 모듈을 사용할 수 없는 경우 기본 정규화만
            pass

        # 중복 제거
        paths_to_check = list(set(paths_to_check))

        for check_path in paths_to_check:
            # 경로 구분자 정규화 (양방향 대체)
            normalized_check = check_path.replace('\\', '/').replace('//', '/')
            check_path_lower = normalized_check.lower()

            for dangerous_path in self.dangerous_system_paths:
                # 위험 경로도 양방향 정규화
                normalized_dangerous = dangerous_path.replace('\\', '/').replace('//', '/')
                dangerous_lower = normalized_dangerous.lower()

                # 정확한 매치 또는 하위 경로 검사
                if (check_path_lower == dangerous_lower or
                    check_path_lower.startswith(dangerous_lower + "/") or
                    check_path_lower.startswith(dangerous_lower.rstrip('/') + "/")):
                    raise SecurityError(f"System path access blocked: {original_path} -> {resolved_path}")

                # 원본 경로도 추가 검사 (정규화 전)
                original_check_lower = check_path.lower()
                original_dangerous_lower = dangerous_path.lower()
                if (original_check_lower == original_dangerous_lower or
                    original_check_lower.startswith(original_dangerous_lower + "/") or
                    original_check_lower.startswith(original_dangerous_lower + "\\") or
                    original_check_lower.startswith(original_dangerous_lower + os.sep)):
                    raise SecurityError(f"System path access blocked: {original_path} -> {resolved_path}")

        # 추가: Windows 특수 패턴 검사
        for check_path in paths_to_check:
            if ("\\\\.\\" in check_path or
                "\\\\?\\" in check_path or
                "//." in check_path or
                "//?" in check_path or
                check_path.lower().replace('\\', '/').startswith("c:/windows") or
                "administrator" in check_path.lower()):
                raise SecurityError(f"Windows system path blocked: {original_path} -> {resolved_path}")

    def _validate_sensitive_file_access(self, resolved_path: Path, original_path: str):
        """민감한 파일 접근 검증 (경로 구분자 정규화 지원)"""
        resolved_str = str(resolved_path)
        original_normalized = os.path.normpath(original_path)

        # 기본 경로 목록
        paths_to_check = [resolved_str, original_path, original_normalized]

        # PureWindowsPath를 사용한 혼합 경로 커버리지
        try:
            # Windows 스타일 정규화 (\\)
            for path in [resolved_str, original_path, original_normalized]:
                if '/' in path or '\\' in path:
                    try:
                        # Windows 경로로 정규화 시도
                        win_path = PureWindowsPath(path)
                        paths_to_check.append(str(win_path.as_posix()))  # POSIX 스타일 (/)
                        paths_to_check.append(str(win_path))  # Windows 스타일 (\\)

                        # POSIX 경로로 정규화 시도
                        posix_path = PurePosixPath(path)
                        paths_to_check.append(str(posix_path))
                    except (ValueError, OSError):
                        # 잘못된 경로 형식이면 무시
                        pass
        except ImportError:
            # PurePath 모듈을 사용할 수 없는 경우 기본 정규화만
            pass

        # 중복 제거
        paths_to_check = list(set(paths_to_check))

        for check_path in paths_to_check:
            # 경로 구분자 정규화 (양방향 대체)
            normalized_check = check_path.replace('\\', '/').replace('//', '/')
            check_path_lower = normalized_check.lower()

            for sensitive_file in self.sensitive_files:
                # 민감 파일 경로도 양방향 정규화
                normalized_sensitive = sensitive_file.replace('\\', '/').replace('//', '/')
                sensitive_lower = normalized_sensitive.lower()

                # 정확한 매치 또는 하위 경로 검사
                if (check_path_lower == sensitive_lower or
                    check_path_lower.startswith(sensitive_lower + "/") or
                    check_path_lower.startswith(sensitive_lower.rstrip('/') + "/") or
                    sensitive_lower in check_path_lower):  # 파일명이 포함된 경우도 검사
                    raise SecurityError(f"Sensitive file access blocked: {original_path} -> {resolved_path}")

                # 원본 경로도 추가 검사 (정규화 전)
                original_check_lower = check_path.lower()
                original_sensitive_lower = sensitive_file.lower()
                if (original_check_lower == original_sensitive_lower or
                    original_check_lower.startswith(original_sensitive_lower + "/") or
                    original_check_lower.startswith(original_sensitive_lower + "\\") or
                    original_check_lower.startswith(original_sensitive_lower + os.sep) or
                    original_sensitive_lower in original_check_lower):
                    raise SecurityError(f"Sensitive file access blocked: {original_path} -> {resolved_path}")


class SafeFileAPI:
    """안전한 파일 시스템 API 래퍼"""

    def __init__(self):
        self.path_validator = SecurePathValidator()

    def read_text(self, path: str, working_dir: Optional[str] = None, encoding: str = 'utf-8') -> str:
        """
        안전한 파일 읽기

        Args:
            path: 파일 경로
            working_dir: 작업 디렉토리
            encoding: 파일 인코딩

        Returns:
            str: 파일 내용
        """
        safe_path = self.path_validator.validate_and_resolve_path(path, working_dir)

        if not safe_path.exists():
            raise FileNotFoundError(f"File not found: {safe_path}")

        if not safe_path.is_file():
            raise ValueError(f"Path is not a file: {safe_path}")

        try:
            return safe_path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError) as e:
            raise IOError(f"Failed to read file: {str(e)}")

    def write_text(self, path: str, content: str, working_dir: Optional[str] = None, encoding: str = 'utf-8') -> None:
        """
        안전한 파일 쓰기

        Args:
            path: 파일 경로
            content: 파일 내용
            working_dir: 작업 디렉토리
            encoding: 파일 인코딩
        """
        safe_path = self.path_validator.validate_and_resolve_path(path, working_dir)

        # 디렉토리 생성
        try:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise IOError(f"Failed to create directory: {str(e)}")

        try:
            safe_path.write_text(content, encoding=encoding)
        except (OSError, PermissionError) as e:
            raise IOError(f"Failed to write file: {str(e)}")

    def list_directory(self, path: str, working_dir: Optional[str] = None) -> List[str]:
        """
        안전한 디렉토리 목록 조회

        Args:
            path: 디렉토리 경로
            working_dir: 작업 디렉토리

        Returns:
            List[str]: 파일/디렉토리 목록
        """
        safe_path = self.path_validator.validate_and_resolve_path(path, working_dir)

        if not safe_path.exists():
            raise FileNotFoundError(f"Directory not found: {safe_path}")

        if not safe_path.is_dir():
            raise ValueError(f"Path is not a directory: {safe_path}")

        try:
            return [item.name for item in safe_path.iterdir()]
        except (OSError, PermissionError) as e:
            raise IOError(f"Failed to list directory: {str(e)}")

    def get_file_info(self, path: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        안전한 파일 정보 조회

        Args:
            path: 파일 경로
            working_dir: 작업 디렉토리

        Returns:
            Dict[str, Any]: 파일 정보
        """
        safe_path = self.path_validator.validate_and_resolve_path(path, working_dir)

        if not safe_path.exists():
            raise FileNotFoundError(f"Path not found: {safe_path}")

        try:
            stat = safe_path.stat()
            return {
                "path": str(safe_path),
                "name": safe_path.name,
                "is_file": safe_path.is_file(),
                "is_directory": safe_path.is_dir(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "permissions": oct(stat.st_mode)[-3:]
            }
        except (OSError, PermissionError) as e:
            raise IOError(f"Failed to get file info: {str(e)}")


class SafeCommandExecutor:
    """안전한 명령어 실행기"""

    # 허용된 명령어 화이트리스트
    ALLOWED_COMMANDS = {
        'git', 'ls', 'pwd', 'cat', 'head', 'tail', 'grep', 'find',
        'python', 'python3', 'pip', 'npm', 'node'
    }

    # 위험한 명령어 블랙리스트
    DANGEROUS_COMMANDS = {
        'rm', 'rmdir', 'sudo', 'su', 'chmod', 'chown', 'kill', 'killall',
        'shutdown', 'reboot', 'halt', 'init', 'service', 'systemctl',
        'dd', 'fdisk', 'mount', 'umount', 'format'
    }

    def __init__(self, path_validator: SecurePathValidator):
        self.path_validator = path_validator

    async def execute_command(self, command: str, working_dir: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        안전한 명령어 실행

        Args:
            command: 실행할 명령어
            working_dir: 작업 디렉토리
            timeout: 타임아웃 (초)

        Returns:
            Dict[str, Any]: 실행 결과
        """
        # 명령어 보안 검증
        self._validate_command(command)

        # 작업 디렉토리 검증
        if working_dir:
            safe_cwd = str(self.path_validator.validate_and_resolve_path(".", working_dir))
        else:
            safe_cwd = os.getenv("PROJECT_ROOT", "/mnt/workspace")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=safe_cwd
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            return {
                "command": command,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "returncode": proc.returncode or 0,
                "success": proc.returncode == 0
            }
        except asyncio.TimeoutError:
            return {
                "command": command,
                "stdout": "",
                "stderr": f"Command timed out ({timeout}s)",
                "returncode": 124,
                "success": False
            }
        except Exception as e:
            return {
                "command": command,
                "stdout": "",
                "stderr": f"Command execution error: {str(e)}",
                "returncode": 1,
                "success": False
            }

    def _validate_command(self, command: str):
        """명령어 보안성 검증"""
        command_parts = command.split()
        if not command_parts:
            raise SecurityError("Empty command")

        main_command = command_parts[0]

        # 위험한 명령어 차단
        if main_command in self.DANGEROUS_COMMANDS:
            raise SecurityError(f"Dangerous command blocked: {main_command}")

        # 화이트리스트 검증 (선택적)
        security_level = os.getenv("MCP_SECURITY_LEVEL", "normal")
        if security_level == "strict" and main_command not in self.ALLOWED_COMMANDS:
            raise SecurityError(f"Command not in whitelist: {main_command}")


# 전역 인스턴스들
_safe_file_api = None
_safe_command_executor = None


def get_safe_file_api() -> SafeFileAPI:
    """Safe File API 싱글톤 인스턴스 반환"""
    global _safe_file_api
    if _safe_file_api is None:
        _safe_file_api = SafeFileAPI()
    return _safe_file_api


def get_safe_command_executor() -> SafeCommandExecutor:
    """Safe Command Executor 싱글톤 인스턴스 반환"""
    global _safe_command_executor
    if _safe_command_executor is None:
        path_validator = SecurePathValidator()
        _safe_command_executor = SafeCommandExecutor(path_validator)
    return _safe_command_executor


# 편의 함수들
def secure_resolve_path(path: str, working_dir: Optional[str] = None) -> Path:
    """경로 검증 및 해석 편의 함수"""
    validator = SecurePathValidator()
    return validator.validate_and_resolve_path(path, working_dir)