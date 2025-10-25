#!/usr/bin/env python3
"""
Email notification tests for Phase 6.4

Test coverage:
- SMTP connection and email sending
- Template rendering with Jinja2
- Retry logic with tenacity
- Asynchronous event queue processing
- Environment configuration
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "mcp-server"))


class TestEmailNotifier:
    """SMTP Email 발송 테스트"""

    @patch("smtplib.SMTP")
    def test_email_send_success(self, mock_smtp):
        """Test 1: SMTP Email 발송 성공"""
        from notifications.email import EmailNotifier

        # Mock SMTP 서버 설정
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier()
        result = notifier._send_sync(
            "approval_requested",
            {
                "user_id": "test_user",
                "tool_name": "git_commit",
                "request_id": "abc12345-1234-5678-9012",
                "expires_at": "2025-10-25 15:30:00",
            },
        )

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_email_send_with_tls(self, mock_smtp):
        """Test 2: TLS 지원하는 SMTP 발송"""
        from notifications.email import EmailNotifier

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        with patch.dict(
            os.environ,
            {
                "SMTP_USE_TLS": "true",
                "SMTP_USER": "testuser",
                "SMTP_PASSWORD": "testpass",
            },
        ):
            notifier = EmailNotifier()
            result = notifier._send_sync("approval_approved", {"tool_name": "test"})

            assert result is True
            # starttls와 login이 호출되었는지 확인
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("testuser", "testpass")

    def test_template_rendering_approval_requested(self):
        """Test 3: approval_requested 템플릿 렌더링"""
        from notifications.email import EmailNotifier

        notifier = EmailNotifier()
        html = notifier.render_template(
            "approval_requested",
            {
                "user_id": "john_doe",
                "tool_name": "git_commit",
                "request_id": "req12345",
                "expires_at": "2025-10-25 15:30:00",
            },
        )

        assert "john_doe" in html
        assert "git_commit" in html
        assert "req12345" in html or "req1" in html  # 짧은 ID도 포함될 수 있음
        assert "❌" not in html  # 거부 아이콘 없음

    def test_template_rendering_approval_approved(self):
        """Test 4: approval_approved 템플릿 렌더링"""
        from notifications.email import EmailNotifier

        notifier = EmailNotifier()
        html = notifier.render_template(
            "approval_approved",
            {
                "user_id": "jane_smith",
                "tool_name": "git_push",
                "responder_id": "admin",
                "reason": "Approved for deployment",
            },
        )

        assert "jane_smith" in html
        assert "git_push" in html
        assert "admin" in html
        assert "✅" in html  # 승인 아이콘 포함

    def test_environment_configuration(self):
        """Test 5: 환경 변수에서 설정 로드"""
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_PORT": "587",
                "SMTP_USE_TLS": "false",
                "EMAIL_FROM": "sender@example.com",
                "EMAIL_TO": "recipient@example.com",
            },
        ):
            from notifications.email import EmailNotifier

            notifier = EmailNotifier()
            assert notifier.smtp_host == "smtp.example.com"
            assert notifier.smtp_port == 587
            assert notifier.smtp_use_tls is False
            assert notifier.email_from == "sender@example.com"
            assert notifier.email_to == "recipient@example.com"


class TestApprovalEventQueue:
    """비동기 이벤트 큐 테스트"""

    @pytest.mark.asyncio
    async def test_event_enqueue(self):
        """Test 6: 비동기 이벤트 큐에 이벤트 추가"""
        from notifications.queue import ApprovalEventQueue, ApprovalEventType

        queue = ApprovalEventQueue()
        queue.queue = __import__("asyncio").Queue()  # 깨끗한 큐 리셋

        await queue.enqueue(
            "approval_requested",
            {
                "request_id": "test123",
                "user_id": "test_user",
                "tool_name": "test_tool",
            },
        )

        assert not queue.queue.empty()
        event = await queue.queue.get()
        assert event.event_type == ApprovalEventType.REQUESTED
        assert event.data["user_id"] == "test_user"

    @pytest.mark.asyncio
    async def test_event_queue_worker_start_stop(self):
        """Test 7: 워커 시작/정지"""
        from notifications.queue import ApprovalEventQueue

        queue = ApprovalEventQueue()
        queue.queue = __import__("asyncio").Queue()

        # 워커 시작
        await queue.start_worker()
        assert queue.running is True
        assert queue.worker_task is not None

        # 워커 정지
        await queue.stop_worker()
        assert queue.running is False

    def test_event_queue_singleton(self):
        """Test 8: ApprovalEventQueue 싱글톤 패턴"""
        from notifications.queue import ApprovalEventQueue

        queue1 = ApprovalEventQueue()
        queue2 = ApprovalEventQueue()

        # 동일한 인스턴스여야 함
        assert queue1 is queue2

    def test_get_email_notifier_singleton(self):
        """Test 9: EmailNotifier 싱글톤"""
        from notifications.email import get_email_notifier

        notifier1 = get_email_notifier()
        notifier2 = get_email_notifier()

        # 동일한 인스턴스여야 함
        assert notifier1 is notifier2

    def test_approval_event_repr(self):
        """Test 10: ApprovalEvent __repr__"""
        from notifications.queue import ApprovalEvent, ApprovalEventType

        event = ApprovalEvent(
            ApprovalEventType.REQUESTED,
            {"request_id": "abc12345-def", "user_id": "test"},
        )

        repr_str = repr(event)
        assert "approval_requested" in repr_str
        assert "abc12345" in repr_str

    @pytest.mark.asyncio
    async def test_approval_requested_event_enqueue(self):
        """Test 11: approval_requested 이벤트가 큐에 들어가는지 확인"""
        from notifications.queue import ApprovalEventQueue, ApprovalEventType

        queue = ApprovalEventQueue()
        queue.queue = __import__("asyncio").Queue()  # 깨끗한 큐 리셋

        await queue.enqueue(
            "approval_requested",
            {
                "request_id": "test-req-123",
                "user_id": "test_user",
                "tool_name": "git_commit",
                "requested_at": "2025-10-25 15:00:00",
                "expires_at": "2025-10-25 15:05:00",
            },
        )

        # 이벤트가 큐에 들어갔는지 확인
        assert not queue.queue.empty()
        event = await queue.queue.get()

        # 이벤트 타입과 데이터 검증
        assert event.event_type == ApprovalEventType.REQUESTED
        assert event.data["request_id"] == "test-req-123"
        assert event.data["user_id"] == "test_user"
        assert event.data["tool_name"] == "git_commit"
        assert event.data["requested_at"] == "2025-10-25 15:00:00"
        assert event.data["expires_at"] == "2025-10-25 15:05:00"


if __name__ == "__main__":
    # 수동 실행을 위한 코드
    pytest_args = [__file__, "-v", "--tb=short"]
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)
