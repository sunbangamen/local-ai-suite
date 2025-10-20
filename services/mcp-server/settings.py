#!/usr/bin/env python3
"""
Security Settings Module
환경 변수 기반 보안 설정 관리
"""

import os
from pathlib import Path


class SecuritySettings:
    """보안 관련 설정을 관리하는 클래스"""

    # RBAC Settings
    RBAC_ENABLED: bool = os.getenv("RBAC_ENABLED", "false").lower() == "true"

    # Database Settings
    SECURITY_DB_PATH: str = os.getenv(
        "SECURITY_DB_PATH", "/mnt/e/ai-data/sqlite/security.db"
    )

    # Logging Settings
    SECURITY_QUEUE_SIZE: int = int(os.getenv("SECURITY_QUEUE_SIZE", "1000"))
    SECURITY_LOG_LEVEL: str = os.getenv("SECURITY_LOG_LEVEL", "INFO")

    # Security Mode
    SECURITY_MODE: str = os.getenv("SECURITY_MODE", "normal")  # strict, normal, legacy

    # Feature Flags
    SANDBOX_ENABLED: bool = os.getenv("SANDBOX_ENABLED", "true").lower() == "true"
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    APPROVAL_WORKFLOW_ENABLED: bool = (
        os.getenv("APPROVAL_WORKFLOW_ENABLED", "false").lower() == "true"
    )

    # Approval Workflow Settings (Issue #16)
    APPROVAL_TIMEOUT: int = int(os.getenv("APPROVAL_TIMEOUT", "300"))  # 5 minutes
    APPROVAL_POLLING_INTERVAL: int = int(
        os.getenv("APPROVAL_POLLING_INTERVAL", "1")
    )  # 1 second
    APPROVAL_MAX_PENDING: int = int(os.getenv("APPROVAL_MAX_PENDING", "50"))

    # Paths
    DATA_DIR: str = os.getenv("DATA_DIR", "/mnt/e/ai-data")

    @classmethod
    def get_db_path(cls) -> Path:
        """보안 DB 경로 반환 (Path 객체)"""
        db_path = Path(cls.SECURITY_DB_PATH)
        # 디렉터리 존재 확인 및 생성
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    @classmethod
    def is_rbac_enabled(cls) -> bool:
        """RBAC 활성화 여부"""
        return cls.RBAC_ENABLED

    @classmethod
    def is_sandbox_enabled(cls) -> bool:
        """샌드박스 활성화 여부"""
        return cls.SANDBOX_ENABLED

    @classmethod
    def is_rate_limit_enabled(cls) -> bool:
        """Rate Limiting 활성화 여부"""
        return cls.RATE_LIMIT_ENABLED

    @classmethod
    def is_approval_enabled(cls) -> bool:
        """승인 워크플로우 활성화 여부"""
        return cls.APPROVAL_WORKFLOW_ENABLED

    @classmethod
    def is_approval_workflow_enabled(cls) -> bool:
        """
        승인을 요구하는 워크플로우가 활성화되어 있는지 반환.
        기존 메서드(is_approval_enabled)와 동치이지만, 테스트 및 외부 코드에서
        사용 중인 이름을 그대로 지원한다.
        """
        return cls.APPROVAL_WORKFLOW_ENABLED

    @classmethod
    def get_approval_timeout(cls) -> int:
        """승인 요청 타임아웃 (초)"""
        return cls.APPROVAL_TIMEOUT

    @classmethod
    def get_approval_polling_interval(cls) -> int:
        """승인 폴링 간격 (초)"""
        return cls.APPROVAL_POLLING_INTERVAL

    @classmethod
    def get_approval_max_pending(cls) -> int:
        """최대 대기 승인 요청 수"""
        return cls.APPROVAL_MAX_PENDING

    @classmethod
    def get_security_mode(cls) -> str:
        """보안 모드 반환"""
        return cls.SECURITY_MODE

    @classmethod
    def validate_config(cls) -> list[str]:
        """
        설정 검증 및 경고 메시지 반환

        Returns:
            경고 메시지 리스트
        """
        warnings = []

        # RBAC 활성화 시 DB 경로 검증
        if cls.RBAC_ENABLED:
            try:
                db_path = cls.get_db_path()
                if not db_path.parent.exists():
                    warnings.append(
                        f"RBAC DB 디렉터리가 존재하지 않습니다: {db_path.parent}"
                    )
            except Exception as e:
                warnings.append(f"RBAC DB 경로 검증 실패: {e}")

        # 보안 모드 검증
        valid_modes = ["strict", "normal", "legacy"]
        if cls.SECURITY_MODE not in valid_modes:
            warnings.append(
                f"유효하지 않은 보안 모드: {cls.SECURITY_MODE} (허용: {valid_modes})"
            )

        # Production 환경 검증
        if cls.RBAC_ENABLED and cls.SECURITY_MODE == "legacy":
            warnings.append(
                "RBAC가 활성화되었지만 보안 모드가 'legacy'입니다. 'normal' 또는 'strict' 권장"
            )

        return warnings


# 싱글톤 인스턴스
settings = SecuritySettings()


def get_security_settings() -> SecuritySettings:
    """보안 설정 인스턴스 반환"""
    return settings
