#!/usr/bin/env python3
"""
Tests for Rate Limiter and Access Control
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rate_limiter import RateLimiter, AccessControl, ToolSensitivityLevel, RateLimit


def test_rate_limiter_basic():
    """기본 rate limiting 테스트"""
    limiter = RateLimiter()

    # read_file 도구 테스트 (100 req/60s + 20 burst)
    for i in range(120):
        allowed, msg = limiter.check_rate_limit("read_file", "test_user")
        assert allowed, f"Request {i+1} should be allowed"

    # 121번째 요청은 거부되어야 함
    allowed, msg = limiter.check_rate_limit("read_file", "test_user")
    assert not allowed, "Request 121 should be denied"
    assert "Rate limit exceeded" in msg

    print("✓ Basic rate limiting test passed")


def test_rate_limiter_time_window():
    """시간 창 테스트"""
    limiter = RateLimiter()

    # 작은 rate limit 설정 (테스트용)
    limiter.rate_limits["test_tool"] = RateLimit(max_requests=2, time_window=2, burst_size=0)

    # 2개 요청 허용
    for i in range(2):
        allowed, msg = limiter.check_rate_limit("test_tool", "test_user")
        assert allowed, f"Request {i+1} should be allowed"

    # 3번째 요청 거부
    allowed, msg = limiter.check_rate_limit("test_tool", "test_user")
    assert not allowed, "Request 3 should be denied"

    # 2초 대기
    print("  Waiting 2 seconds for time window reset...")
    time.sleep(2.5)

    # 다시 요청 허용
    allowed, msg = limiter.check_rate_limit("test_tool", "test_user")
    assert allowed, "Request should be allowed after time window reset"

    print("✓ Time window test passed")


def test_rate_limiter_multiple_users():
    """다중 사용자 테스트"""
    limiter = RateLimiter()
    limiter.rate_limits["test_tool"] = RateLimit(max_requests=2, time_window=60, burst_size=0)

    # 사용자 1
    for i in range(2):
        allowed, _ = limiter.check_rate_limit("test_tool", "user1")
        assert allowed

    # 사용자 1의 3번째 요청 거부
    allowed, _ = limiter.check_rate_limit("test_tool", "user1")
    assert not allowed

    # 사용자 2는 독립적으로 허용
    for i in range(2):
        allowed, _ = limiter.check_rate_limit("test_tool", "user2")
        assert allowed

    print("✓ Multiple users test passed")


def test_rate_limiter_concurrent_execution():
    """동시 실행 추적 테스트"""
    limiter = RateLimiter()

    # read_file 도구 사용 (rate_limits에 등록된 도구)
    allowed, _ = limiter.start_execution("read_file", "user1")
    assert allowed
    allowed, _ = limiter.start_execution("read_file", "user1")
    assert allowed

    usage = limiter.get_current_usage("read_file", "user1")
    assert usage["concurrent_executions"] == 2

    # 실행 종료
    limiter.end_execution("read_file", "user1")
    usage = limiter.get_current_usage("read_file", "user1")
    assert usage["concurrent_executions"] == 1

    print("✓ Concurrent execution test passed")


def test_access_control_sensitivity_levels():
    """도구 민감도 수준 테스트"""
    ac = AccessControl()

    # LOW sensitivity tools
    assert ac.tool_sensitivity["read_file"] == ToolSensitivityLevel.LOW
    assert ac.tool_sensitivity["list_files"] == ToolSensitivityLevel.LOW

    # MEDIUM sensitivity tools
    assert ac.tool_sensitivity["write_file"] == ToolSensitivityLevel.MEDIUM

    # HIGH sensitivity tools
    assert ac.tool_sensitivity["execute_python"] == ToolSensitivityLevel.HIGH
    assert ac.tool_sensitivity["execute_bash"] == ToolSensitivityLevel.HIGH

    # CRITICAL sensitivity tools
    assert ac.tool_sensitivity["git_commit"] == ToolSensitivityLevel.CRITICAL
    assert ac.tool_sensitivity["switch_model"] == ToolSensitivityLevel.CRITICAL

    print("✓ Sensitivity levels test passed")


def test_access_control_basic():
    """기본 접근 제어 테스트"""
    ac = AccessControl()

    # Development mode에서는 모든 사용자 허용
    allowed, _ = ac.check_access("read_file", "any_user")
    assert allowed

    allowed, _ = ac.check_access("execute_bash", "any_user")
    assert allowed

    print("✓ Basic access control test passed")


def test_access_control_approval_required():
    """승인 필요 여부 테스트"""
    ac = AccessControl()

    # Development mode에서 민감도별 승인 정책
    # LOW/MEDIUM: 승인 불필요
    assert not ac.requires_approval("read_file")
    assert not ac.requires_approval("write_file")

    # HIGH/CRITICAL: 승인 필요 (개발 모드에서도)
    assert ac.requires_approval("execute_bash")
    assert ac.requires_approval("git_commit")

    print("✓ Approval required test passed")


def test_rate_limiter_get_usage():
    """사용량 조회 테스트"""
    limiter = RateLimiter()

    # 초기 상태
    usage = limiter.get_current_usage("read_file", "test_user")
    assert usage["current_count"] == 0
    assert usage["remaining"] == 120  # 100 + 20 burst

    # 몇 개 요청 후
    for _ in range(5):
        limiter.check_rate_limit("read_file", "test_user")

    usage = limiter.get_current_usage("read_file", "test_user")
    assert usage["current_count"] == 5
    assert usage["remaining"] == 115

    print("✓ Usage query test passed")


def test_access_control_tool_info():
    """도구 정보 조회 테스트"""
    ac = AccessControl()

    info = ac.get_tool_info("execute_bash")
    assert info["tool_name"] == "execute_bash"
    assert info["sensitivity"] == "high"
    assert "require_approval" in info
    assert "max_concurrent" in info

    print("✓ Tool info test passed")


def test_concurrent_execution_limit_enforcement():
    """동시 실행 제한 강제 적용 테스트"""
    limiter = RateLimiter()
    ac = AccessControl()

    # execute_bash는 HIGH 민감도 (max_concurrent=5)
    tool_name = "execute_bash"

    # 5개 실행 시작 (제한까지)
    for i in range(5):
        allowed, msg = limiter.start_execution(tool_name, "test_user", ac)
        assert allowed, f"Request {i+1} should be allowed"

    # 6번째 실행은 거부되어야 함
    allowed, msg = limiter.start_execution(tool_name, "test_user", ac)
    assert not allowed, "Request 6 should be denied (max_concurrent=5)"
    assert "Concurrent execution limit exceeded" in msg

    # 하나 종료 후 다시 허용
    limiter.end_execution(tool_name, "test_user")
    allowed, msg = limiter.start_execution(tool_name, "test_user", ac)
    assert allowed, "Request should be allowed after one execution ended"

    print("✓ Concurrent execution limit enforcement test passed")


def test_development_mode_security():
    """개발 모드 보안 정책 테스트"""
    import os

    # 개발 모드 확인 (기본값)
    mode = os.getenv("SECURITY_MODE", "development")
    assert mode == "development"

    ac = AccessControl()

    # LOW 민감도: 승인 불필요
    assert not ac.requires_approval("read_file")

    # MEDIUM 민감도: 승인 불필요
    assert not ac.requires_approval("write_file")

    # HIGH 민감도: 승인 필요 (개발 모드에서도)
    assert ac.requires_approval("execute_bash")

    # CRITICAL 민감도: 승인 필요 (개발 모드에서도)
    assert ac.requires_approval("git_commit")

    # 동시 실행 제한 확인
    info_low = ac.get_tool_info("read_file")
    assert info_low["max_concurrent"] == 20

    info_high = ac.get_tool_info("execute_bash")
    assert info_high["max_concurrent"] == 5

    info_critical = ac.get_tool_info("git_commit")
    assert info_critical["max_concurrent"] == 2

    print("✓ Development mode security test passed")


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 60)
    print("Running MCP Rate Limiter and Access Control Tests")
    print("=" * 60)

    tests = [
        test_rate_limiter_basic,
        test_rate_limiter_time_window,
        test_rate_limiter_multiple_users,
        test_rate_limiter_concurrent_execution,
        test_access_control_sensitivity_levels,
        test_access_control_basic,
        test_access_control_approval_required,
        test_rate_limiter_get_usage,
        test_access_control_tool_info,
        test_concurrent_execution_limit_enforcement,
        test_development_mode_security,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning {test.__name__}...")
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
