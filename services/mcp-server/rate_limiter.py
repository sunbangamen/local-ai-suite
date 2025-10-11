#!/usr/bin/env python3
"""
Rate Limiting and Access Control for MCP Tools
"""

import os
import time
from typing import Dict, List, Optional, Set
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum


class ToolSensitivityLevel(Enum):
    """도구 민감도 수준"""

    LOW = "low"  # 읽기 전용 도구 (list_files, read_file)
    MEDIUM = "medium"  # 제한된 쓰기 (write_file)
    HIGH = "high"  # 위험한 작업 (execute_bash, execute_python)
    CRITICAL = "critical"  # 매우 위험 (git 작업, 시스템 명령)


@dataclass
class RateLimit:
    """Rate limit 설정"""

    max_requests: int  # 시간 창 내 최대 요청 수
    time_window: int  # 시간 창 (초)
    burst_size: int = 0  # 버스트 허용 크기 (0 = 버스트 없음)


@dataclass
class AccessControlRule:
    """접근 제어 규칙"""

    allowed_users: Optional[Set[str]] = None  # None = 모든 사용자 허용
    denied_users: Optional[Set[str]] = None
    max_concurrent: int = 10  # 최대 동시 실행 수
    require_approval: bool = False  # 승인 필요 여부


class RateLimiter:
    """Rate limiting 구현"""

    def __init__(self):
        # 도구별 요청 기록: {tool_name: {user_id: deque([timestamp, ...])}}
        self.request_history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(deque)
        )

        # 도구별 rate limit 설정
        self.rate_limits: Dict[str, RateLimit] = self._init_rate_limits()

        # 도구별 동시 실행 카운트
        self.concurrent_executions: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def _init_rate_limits(self) -> Dict[str, RateLimit]:
        """기본 rate limit 설정"""
        return {
            # 읽기 전용 도구 (관대한 제한)
            "list_files": RateLimit(max_requests=60, time_window=60, burst_size=10),
            "read_file": RateLimit(max_requests=100, time_window=60, burst_size=20),
            "rag_search": RateLimit(max_requests=30, time_window=60, burst_size=5),
            "ai_chat": RateLimit(max_requests=30, time_window=60, burst_size=5),
            "git_status": RateLimit(max_requests=30, time_window=60, burst_size=5),
            "git_log": RateLimit(max_requests=30, time_window=60, burst_size=5),
            "git_diff": RateLimit(max_requests=30, time_window=60, burst_size=5),
            # 쓰기 도구 (중간 제한)
            "write_file": RateLimit(max_requests=20, time_window=60, burst_size=5),
            "git_add": RateLimit(max_requests=20, time_window=60, burst_size=3),
            "git_commit": RateLimit(max_requests=10, time_window=60, burst_size=2),
            # 실행 도구 (엄격한 제한)
            "execute_python": RateLimit(max_requests=10, time_window=60, burst_size=2),
            "execute_bash": RateLimit(max_requests=10, time_window=60, burst_size=2),
            # 웹 자동화 (중간 제한)
            "web_screenshot": RateLimit(max_requests=15, time_window=60, burst_size=3),
            "web_scrape": RateLimit(max_requests=15, time_window=60, burst_size=3),
            "web_analyze_ui": RateLimit(max_requests=10, time_window=60, burst_size=2),
            "web_automate": RateLimit(max_requests=5, time_window=60, burst_size=1),
            # Notion 통합 (중간 제한)
            "notion_create_page": RateLimit(
                max_requests=10, time_window=60, burst_size=2
            ),
            "notion_search": RateLimit(max_requests=20, time_window=60, burst_size=5),
            "web_to_notion": RateLimit(max_requests=5, time_window=60, burst_size=1),
            # 모델 관리 (엄격한 제한)
            "switch_model": RateLimit(max_requests=5, time_window=300, burst_size=1),
            "get_current_model": RateLimit(
                max_requests=30, time_window=60, burst_size=5
            ),
        }

    def check_rate_limit(
        self, tool_name: str, user_id: str = "default"
    ) -> tuple[bool, Optional[str]]:
        """
        Rate limit 체크

        Returns:
            (허용 여부, 오류 메시지)
        """
        if tool_name not in self.rate_limits:
            # Rate limit이 설정되지 않은 도구는 허용
            return True, None

        limit = self.rate_limits[tool_name]
        now = time.time()

        # 현재 도구의 사용자 요청 기록 가져오기
        history = self.request_history[tool_name][user_id]

        # 시간 창을 벗어난 요청 제거
        while history and now - history[0] > limit.time_window:
            history.popleft()

        # Rate limit 체크
        current_count = len(history)
        max_allowed = limit.max_requests + limit.burst_size

        if current_count >= max_allowed:
            wait_time = int(limit.time_window - (now - history[0]))
            return (
                False,
                f"Rate limit exceeded for {tool_name}. Try again in {wait_time} seconds.",
            )

        # 요청 기록 추가
        history.append(now)
        return True, None

    def start_execution(
        self,
        tool_name: str,
        user_id: str = "default",
        access_control: Optional["AccessControl"] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        도구 실행 시작 (동시 실행 수 체크 및 강제 적용)

        Returns:
            (허용 여부, 오류 메시지)
        """
        # AccessControl에서 max_concurrent 가져오기
        if access_control:
            tool_info = access_control.get_tool_info(tool_name)
            max_concurrent = tool_info.get("max_concurrent", 10)
        else:
            max_concurrent = 10  # 기본값

        # 현재 동시 실행 수 확인
        current_concurrent = self.concurrent_executions[tool_name][user_id]

        # 제한 초과 확인
        if current_concurrent >= max_concurrent:
            return (
                False,
                f"Concurrent execution limit exceeded for {tool_name} (max: {max_concurrent}, current: {current_concurrent})",
            )

        # 실행 시작
        self.concurrent_executions[tool_name][user_id] += 1
        return True, None

    def end_execution(self, tool_name: str, user_id: str = "default"):
        """도구 실행 종료"""
        count = self.concurrent_executions[tool_name][user_id]
        if count > 0:
            self.concurrent_executions[tool_name][user_id] = count - 1

    def get_current_usage(self, tool_name: str, user_id: str = "default") -> Dict:
        """현재 사용량 조회"""
        if tool_name not in self.rate_limits:
            return {"error": "Tool not found"}

        limit = self.rate_limits[tool_name]
        history = self.request_history[tool_name][user_id]
        now = time.time()

        # 유효한 요청만 카운트
        valid_requests = [ts for ts in history if now - ts <= limit.time_window]

        return {
            "tool_name": tool_name,
            "user_id": user_id,
            "current_count": len(valid_requests),
            "max_requests": limit.max_requests,
            "burst_size": limit.burst_size,
            "time_window": limit.time_window,
            "concurrent_executions": self.concurrent_executions[tool_name][user_id],
            "remaining": max(
                0, limit.max_requests + limit.burst_size - len(valid_requests)
            ),
        }


class AccessControl:
    """접근 제어 구현"""

    def __init__(self):
        self.rules: Dict[str, AccessControlRule] = self._init_rules()
        self.tool_sensitivity: Dict[str, ToolSensitivityLevel] = (
            self._init_sensitivity()
        )

    def _init_sensitivity(self) -> Dict[str, ToolSensitivityLevel]:
        """도구별 민감도 수준 초기화"""
        return {
            # LOW: 읽기 전용
            "list_files": ToolSensitivityLevel.LOW,
            "read_file": ToolSensitivityLevel.LOW,
            "rag_search": ToolSensitivityLevel.LOW,
            "ai_chat": ToolSensitivityLevel.LOW,
            "git_status": ToolSensitivityLevel.LOW,
            "git_log": ToolSensitivityLevel.LOW,
            "git_diff": ToolSensitivityLevel.LOW,
            "get_current_model": ToolSensitivityLevel.LOW,
            # MEDIUM: 제한된 쓰기
            "write_file": ToolSensitivityLevel.MEDIUM,
            "web_screenshot": ToolSensitivityLevel.MEDIUM,
            "web_scrape": ToolSensitivityLevel.MEDIUM,
            "web_analyze_ui": ToolSensitivityLevel.MEDIUM,
            "notion_search": ToolSensitivityLevel.MEDIUM,
            # HIGH: 위험한 작업
            "execute_python": ToolSensitivityLevel.HIGH,
            "execute_bash": ToolSensitivityLevel.HIGH,
            "git_add": ToolSensitivityLevel.HIGH,
            "web_automate": ToolSensitivityLevel.HIGH,
            "notion_create_page": ToolSensitivityLevel.HIGH,
            "web_to_notion": ToolSensitivityLevel.HIGH,
            # CRITICAL: 매우 위험
            "git_commit": ToolSensitivityLevel.CRITICAL,
            "switch_model": ToolSensitivityLevel.CRITICAL,
        }

    def _init_rules(self) -> Dict[str, AccessControlRule]:
        """
        기본 접근 제어 규칙 (민감도별 정책)

        SECURITY_MODE 환경변수:
        - development (기본값): 모든 사용자 허용, HIGH/CRITICAL은 보수적 설정
        - production: 엄격한 정책, CRITICAL은 관리자만
        """
        development_mode = os.getenv("SECURITY_MODE", "development") == "development"

        if development_mode:
            # 개발 모드: 모든 사용자 허용하되 민감도별 제한 적용
            return {
                # 읽기 전용 도구 (관대함)
                "__low__": AccessControlRule(
                    allowed_users=None,  # 모든 사용자
                    denied_users=None,
                    max_concurrent=20,
                    require_approval=False,
                ),
                # 쓰기 도구 (중간)
                "__medium__": AccessControlRule(
                    allowed_users=None,
                    denied_users=None,
                    max_concurrent=10,
                    require_approval=False,
                ),
                # 위험한 도구 (보수적)
                "__high__": AccessControlRule(
                    allowed_users=None,
                    denied_users=None,
                    max_concurrent=5,
                    require_approval=True,  # 개발 모드에서도 승인 필요
                ),
                # 매우 위험한 도구 (매우 보수적)
                "__critical__": AccessControlRule(
                    allowed_users=None,  # 개발 모드: 모든 사용자 허용
                    denied_users=None,
                    max_concurrent=2,
                    require_approval=True,  # 개발 모드에서도 승인 필요
                ),
            }
        else:
            # 프로덕션 모드: 엄격한 규칙
            return {
                # 읽기 전용 도구
                "__low__": AccessControlRule(
                    allowed_users=None, max_concurrent=20, require_approval=False
                ),
                # 쓰기 도구
                "__medium__": AccessControlRule(
                    allowed_users=None, max_concurrent=10, require_approval=False
                ),
                # 위험한 도구
                "__high__": AccessControlRule(
                    allowed_users=None,  # 프로덕션: 모든 인증 사용자
                    max_concurrent=5,
                    require_approval=True,
                ),
                # 매우 위험한 도구
                "__critical__": AccessControlRule(
                    allowed_users={"admin"},  # 프로덕션: 관리자만
                    max_concurrent=2,
                    require_approval=True,
                ),
            }

    def check_access(
        self, tool_name: str, user_id: str = "default"
    ) -> tuple[bool, Optional[str]]:
        """
        접근 권한 체크

        Returns:
            (허용 여부, 오류 메시지)
        """
        # 도구의 민감도 수준 가져오기
        sensitivity = self.tool_sensitivity.get(tool_name, ToolSensitivityLevel.MEDIUM)

        # 해당 민감도 수준의 규칙 가져오기
        rule_key = f"__{sensitivity.value}__"
        rule = self.rules.get(rule_key, self.rules.get("__default__"))

        if not rule:
            # 규칙이 없으면 허용
            return True, None

        # 거부 목록 체크
        if rule.denied_users and user_id in rule.denied_users:
            return False, f"User {user_id} is denied access to {tool_name}"

        # 허용 목록 체크 (설정된 경우)
        if rule.allowed_users and user_id not in rule.allowed_users:
            return False, f"User {user_id} is not allowed to use {tool_name}"

        return True, None

    def requires_approval(self, tool_name: str) -> bool:
        """승인이 필요한 도구인지 확인"""
        sensitivity = self.tool_sensitivity.get(tool_name, ToolSensitivityLevel.MEDIUM)
        rule_key = f"__{sensitivity.value}__"
        rule = self.rules.get(rule_key, self.rules.get("__default__"))

        return rule.require_approval if rule else False

    def get_tool_info(self, tool_name: str) -> Dict:
        """도구 정보 조회"""
        sensitivity = self.tool_sensitivity.get(tool_name, ToolSensitivityLevel.MEDIUM)
        rule_key = f"__{sensitivity.value}__"
        rule = self.rules.get(rule_key, self.rules.get("__default__"))

        return {
            "tool_name": tool_name,
            "sensitivity": sensitivity.value,
            "require_approval": rule.require_approval if rule else False,
            "max_concurrent": rule.max_concurrent if rule else 10,
        }


# 싱글톤 인스턴스
_rate_limiter: Optional[RateLimiter] = None
_access_control: Optional[AccessControl] = None


def get_rate_limiter() -> RateLimiter:
    """Rate limiter 싱글톤 가져오기"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_access_control() -> AccessControl:
    """Access control 싱글톤 가져오기"""
    global _access_control
    if _access_control is None:
        _access_control = AccessControl()
    return _access_control
