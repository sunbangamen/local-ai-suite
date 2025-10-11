#!/usr/bin/env python3
"""
Enhanced Sandbox Environment - 컨테이너 기반 코드 실행 격리
"""

import os
import tempfile
import subprocess
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from .security import SecurityValidator, SecurityError
    from .safe_api import SecurePathValidator
except ImportError:
    from security import SecurityValidator, SecurityError
    from safe_api import SecurePathValidator


class ResourceLimits:
    """리소스 제한 설정"""

    def __init__(self):
        # 기본 제한값들 (환경변수로 오버라이드 가능)
        self.max_memory_mb = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "512"))  # 512MB
        self.max_cpu_time_sec = int(os.getenv("SANDBOX_MAX_CPU_TIME", "30"))  # 30초
        self.max_output_size = int(os.getenv("SANDBOX_MAX_OUTPUT_SIZE", "1048576"))  # 1MB
        self.max_file_size = int(os.getenv("SANDBOX_MAX_FILE_SIZE", "10485760"))  # 10MB
        self.max_processes = int(os.getenv("SANDBOX_MAX_PROCESSES", "10"))
        self.network_access = os.getenv("SANDBOX_NETWORK_ACCESS", "false").lower() == "true"


class SandboxLogger:
    """샌드박스 감사 로깅"""

    def __init__(self):
        self.log_dir = Path(os.getenv("MCP_LOG_DIR", "/tmp/mcp-logs"))
        self.log_dir.mkdir(exist_ok=True)
        self.audit_log = self.log_dir / "security_audit.log"

    def log_security_event(self, event_type: str, details: Dict[str, Any], severity: str = "INFO"):
        """보안 이벤트 로깅"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        session_id = details.get("session_id", "unknown")

        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "severity": severity,
            "session_id": session_id,
            "details": details,
        }

        try:
            with open(self.audit_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except IOError:
            # 로깅 실패해도 메인 동작은 계속
            pass

    def log_code_execution(self, code: str, result: Dict[str, Any], session_id: str):
        """코드 실행 로깅"""
        self.log_security_event(
            "CODE_EXECUTION",
            {
                "session_id": session_id,
                "code_hash": hash(code) % 100000,  # 코드 내용 직접 저장 안함 (프라이버시)
                "code_length": len(code),
                "success": result.get("success", False),
                "execution_time": result.get("execution_time", 0),
                "memory_used": result.get("memory_used", 0),
                "returncode": result.get("returncode", -1),
            },
        )

    def log_security_violation(self, violation_type: str, details: Dict[str, Any], session_id: str):
        """보안 위반 로깅"""
        self.log_security_event(
            "SECURITY_VIOLATION",
            {"session_id": session_id, "violation_type": violation_type, **details},
            "WARNING",
        )


class ContainerSandbox:
    """컨테이너 기반 샌드박스 실행 환경"""

    def __init__(self, limits: ResourceLimits, logger: SandboxLogger):
        self.limits = limits
        self.logger = logger
        self.validator = SecurityValidator()
        self.path_validator = SecurePathValidator()

    async def execute_python_code(
        self, code: str, session_id: str = "default", working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        샌드박스에서 Python 코드 실행

        Args:
            code: 실행할 Python 코드
            session_id: 세션 ID (로깅용)
            working_dir: 작업 디렉토리

        Returns:
            Dict: 실행 결과
        """
        start_time = time.time()

        try:
            # 1단계: 코드 보안 검증
            self.validator.validate_code(code)

            # 2단계: 샌드박스 환경에서 실행
            if self._is_docker_available():
                result = await self._execute_in_docker(code, session_id, working_dir)
            else:
                # Docker가 없으면 프로세스 격리로 폴백
                result = await self._execute_in_process(code, session_id, working_dir)

            # 3단계: 실행 시간 기록
            execution_time = time.time() - start_time
            result["execution_time"] = execution_time

            # 4단계: 감사 로깅
            self.logger.log_code_execution(code, result, session_id)

            return result

        except SecurityError as e:
            # 보안 위반 로깅
            self.logger.log_security_violation(
                "CODE_VALIDATION_FAILED",
                {"error": str(e), "code_length": len(code)},
                session_id,
            )
            return {
                "stdout": "",
                "stderr": f"Security validation failed: {str(e)}",
                "returncode": 1,
                "success": False,
                "execution_time": time.time() - start_time,
            }
        except Exception as e:
            # 일반 오류 로깅
            self.logger.log_security_event(
                "EXECUTION_ERROR", {"error": str(e), "session_id": session_id}, "ERROR"
            )
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "returncode": 1,
                "success": False,
                "execution_time": time.time() - start_time,
            }

    def _is_docker_available(self) -> bool:
        """Docker 사용 가능 여부 확인"""
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def _execute_in_docker(
        self, code: str, session_id: str, working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Docker 컨테이너에서 코드 실행"""

        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            code_file = temp_path / "user_code.py"

            # 코드 파일 작성
            code_file.write_text(code, encoding="utf-8")

            # Docker 실행 명령어 구성
            docker_cmd = [
                "docker",
                "run",
                "--rm",  # 실행 후 컨테이너 자동 삭제
                "--read-only",  # 읽기 전용 파일시스템
                "--tmpfs",
                "/tmp:noexec,nosuid,size=100m",  # 임시 디렉토리 제한
                f"--memory={self.limits.max_memory_mb}m",  # 메모리 제한
                f"--cpus={self.limits.max_cpu_time_sec / 60:.2f}",  # CPU 제한
                "--pids-limit",
                str(self.limits.max_processes),  # 프로세스 수 제한
                "--ulimit",
                f"fsize={self.limits.max_file_size}",  # 파일 크기 제한
                "--security-opt",
                "no-new-privileges",  # 권한 상승 차단
                "--cap-drop",
                "ALL",  # 모든 capability 제거
                "-v",
                f"{code_file}:/code.py:ro",  # 코드 파일 마운트 (읽기 전용)
                "--user",
                "1000:1000",  # 비특권 사용자로 실행
                "--workdir",
                "/tmp",
                "python:3.11-alpine",  # 최소한의 Python 이미지
                "python",
                "/code.py",
            ]

            # 네트워크 접근 제한
            if not self.limits.network_access:
                docker_cmd.extend(["--network", "none"])

            try:
                proc = await asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # 타임아웃 적용
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.limits.max_cpu_time_sec
                )

                # 출력 크기 제한
                stdout_str = self._limit_output_size(stdout.decode())
                stderr_str = self._limit_output_size(stderr.decode())

                return {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": proc.returncode or 0,
                    "success": proc.returncode == 0,
                    "sandbox_type": "docker",
                }

            except asyncio.TimeoutError:
                # 프로세스 강제 종료
                try:
                    proc.kill()
                    await proc.wait()
                except:
                    pass

                return {
                    "stdout": "",
                    "stderr": f"Execution timed out ({self.limits.max_cpu_time_sec}s)",
                    "returncode": 124,
                    "success": False,
                    "sandbox_type": "docker",
                }

    async def _execute_in_process(
        self, code: str, session_id: str, working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """프로세스 격리에서 코드 실행 (Docker 폴백)"""

        # 임시 디렉토리에서 실행
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python",
                    "-c",
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir,
                    # 환경 변수 최소화
                    env={
                        "PATH": "/usr/bin:/bin",
                        "PYTHONPATH": "",
                        "HOME": temp_dir,
                        "USER": "sandbox",
                    },
                )

                # 타임아웃 적용
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.limits.max_cpu_time_sec
                )

                # 출력 크기 제한
                stdout_str = self._limit_output_size(stdout.decode())
                stderr_str = self._limit_output_size(stderr.decode())

                return {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "returncode": proc.returncode or 0,
                    "success": proc.returncode == 0,
                    "sandbox_type": "process",
                }

            except asyncio.TimeoutError:
                # 프로세스 강제 종료
                try:
                    proc.kill()
                    await proc.wait()
                except:
                    pass

                return {
                    "stdout": "",
                    "stderr": f"Execution timed out ({self.limits.max_cpu_time_sec}s)",
                    "returncode": 124,
                    "success": False,
                    "sandbox_type": "process",
                }

    def _limit_output_size(self, output: str) -> str:
        """출력 크기 제한"""
        if len(output) > self.limits.max_output_size:
            truncated = output[: self.limits.max_output_size]
            truncated += f"\n... (output truncated, max {self.limits.max_output_size} bytes)"
            return truncated
        return output


class SessionManager:
    """세션별 접근 제어 관리"""

    def __init__(self, logger: SandboxLogger):
        self.sessions = {}  # session_id -> session_info
        self.logger = logger
        self.max_sessions = int(os.getenv("MCP_MAX_SESSIONS", "10"))
        self.session_timeout = int(os.getenv("MCP_SESSION_TIMEOUT", "3600"))  # 1시간

    def create_session(self, session_id: str, client_info: Dict[str, Any]) -> bool:
        """새 세션 생성"""
        if len(self.sessions) >= self.max_sessions:
            self.logger.log_security_event(
                "SESSION_LIMIT_EXCEEDED",
                {"session_id": session_id, "max_sessions": self.max_sessions},
                "WARNING",
            )
            return False

        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_activity": time.time(),
            "client_info": client_info,
            "execution_count": 0,
            "security_violations": 0,
        }

        self.logger.log_security_event(
            "SESSION_CREATED", {"session_id": session_id, "client_info": client_info}
        )
        return True

    def validate_session(self, session_id: str) -> bool:
        """세션 유효성 검증"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        current_time = time.time()

        # 세션 타임아웃 확인
        if current_time - session["last_activity"] > self.session_timeout:
            self.cleanup_session(session_id)
            return False

        # 마지막 활동 시간 업데이트
        session["last_activity"] = current_time
        return True

    def record_execution(self, session_id: str):
        """실행 횟수 기록"""
        if session_id in self.sessions:
            self.sessions[session_id]["execution_count"] += 1

    def record_security_violation(self, session_id: str):
        """보안 위반 기록"""
        if session_id in self.sessions:
            self.sessions[session_id]["security_violations"] += 1

            # 위반 횟수가 너무 많으면 세션 종료
            if self.sessions[session_id]["security_violations"] >= 5:
                self.logger.log_security_event(
                    "SESSION_BLOCKED",
                    {"session_id": session_id, "violations": 5},
                    "ERROR",
                )
                self.cleanup_session(session_id)
                return False
        return True

    def cleanup_session(self, session_id: str):
        """세션 정리"""
        if session_id in self.sessions:
            self.logger.log_security_event("SESSION_CLEANUP", {"session_id": session_id})
            del self.sessions[session_id]

    def cleanup_expired_sessions(self):
        """만료된 세션들 정리"""
        current_time = time.time()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if current_time - session["last_activity"] > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self.cleanup_session(session_id)


class EnhancedSandbox:
    """강화된 샌드박스 시스템"""

    def __init__(self):
        self.limits = ResourceLimits()
        self.logger = SandboxLogger()
        self.container_sandbox = ContainerSandbox(self.limits, self.logger)
        self.session_manager = SessionManager(self.logger)

    async def execute_code(
        self,
        code: str,
        session_id: str = "default",
        client_info: Optional[Dict[str, Any]] = None,
        working_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        코드 실행 (세션 관리 포함)

        Args:
            code: 실행할 코드
            session_id: 세션 ID
            client_info: 클라이언트 정보
            working_dir: 작업 디렉토리

        Returns:
            Dict: 실행 결과
        """

        # 세션 검증 또는 생성
        if not self.session_manager.validate_session(session_id):
            if client_info:
                if not self.session_manager.create_session(session_id, client_info):
                    return {
                        "stdout": "",
                        "stderr": "Session limit exceeded",
                        "returncode": 1,
                        "success": False,
                    }
            else:
                return {
                    "stdout": "",
                    "stderr": "Invalid session",
                    "returncode": 1,
                    "success": False,
                }

        # 실행 횟수 기록
        self.session_manager.record_execution(session_id)

        # 코드 실행
        result = await self.container_sandbox.execute_python_code(code, session_id, working_dir)

        # 보안 위반 시 세션에 기록
        if not result.get("success", False) and "Security" in result.get("stderr", ""):
            self.session_manager.record_security_violation(session_id)

        return result

    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 통계 조회"""
        if session_id in self.session_manager.sessions:
            session = self.session_manager.sessions[session_id]
            return {
                "session_id": session_id,
                "created_at": session["created_at"],
                "last_activity": session["last_activity"],
                "execution_count": session["execution_count"],
                "security_violations": session["security_violations"],
                "is_active": True,
            }
        return None

    def cleanup_sessions(self):
        """만료된 세션들 정리"""
        self.session_manager.cleanup_expired_sessions()


# 글로벌 인스턴스
_enhanced_sandbox = None


def get_enhanced_sandbox() -> EnhancedSandbox:
    """Enhanced Sandbox 싱글톤 인스턴스 반환"""
    global _enhanced_sandbox
    if _enhanced_sandbox is None:
        _enhanced_sandbox = EnhancedSandbox()
    return _enhanced_sandbox
