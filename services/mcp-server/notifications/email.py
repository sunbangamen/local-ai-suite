"""
SMTP-based email notification sender (Phase 6.4)

Handles email sending with template rendering, retry logic,
and async execution using tenacity for exponential backoff.
"""

import smtplib
import os
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pathlib import Path
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class EmailNotifier:
    """SMTP 기반 Email 발송"""

    def __init__(self):
        """SMTP 설정 초기화"""
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.email_from = os.getenv("EMAIL_FROM", "admin@localhost")
        self.email_to = os.getenv("EMAIL_TO", "operator@localhost")

        # Jinja2 템플릿 로더
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        try:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)), autoescape=True
            )
            logger.info(f"Template directory loaded: {template_dir}")
        except Exception as e:
            logger.error(f"Failed to load template directory: {str(e)}")
            self.jinja_env = None

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Jinja2 템플릿 렌더링"""
        if not self.jinja_env:
            logger.error("Template environment not initialized")
            return ""

        try:
            # 타임스탐프 추가
            context["timestamp"] = (
                context.get("timestamp") or self._format_timestamp()
            )

            template = self.jinja_env.get_template(f"{template_name}.html")
            return template.render(**context)
        except TemplateNotFound:
            logger.error(f"Template not found: {template_name}.html")
            return ""
        except Exception as e:
            logger.error(f"Template rendering error: {str(e)}")
            return ""

    async def send_notification(
        self, template_name: str, context: Dict[str, Any]
    ) -> bool:
        """비동기 방식의 알림 발송 (smtplib 동기 호출을 executor에서 실행)"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._send_sync, template_name, context
            )
        except Exception as e:
            logger.error(f"Async notification failed: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _send_sync(self, template_name: str, context: Dict[str, Any]) -> bool:
        """동기 방식의 실제 Email 발송 (tenacity 재시도 포함)"""
        try:
            # 템플릿 렌더링
            html_content = self.render_template(template_name, context)

            if not html_content:
                raise ValueError(f"Failed to render template: {template_name}")

            # 제목 결정
            subject_map = {
                "approval_requested": f"[승인 필요] {context.get('tool_name', 'Unknown')} 도구",
                "approval_timeout": f"[타임아웃] {context.get('tool_name', 'Unknown')} 승인 요청",
                "approval_approved": f"[승인됨] {context.get('tool_name', 'Unknown')} 도구",
                "approval_rejected": f"[거부됨] {context.get('tool_name', 'Unknown')} 도구",
            }
            subject = subject_map.get(template_name, "승인 알림")

            # Email 메시지 구성
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = self.email_to

            # HTML 파트
            html_part = MIMEText(html_content, "html", _charset="utf-8")
            msg.attach(html_part)

            # SMTP 발송
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent: {subject} to {self.email_to}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            raise  # tenacity가 잡아서 재시도

    @staticmethod
    def _format_timestamp() -> str:
        """현재 시간을 포맷팅"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 싱글톤 인스턴스
_email_notifier_instance: Optional[EmailNotifier] = None


def get_email_notifier() -> EmailNotifier:
    """Email 발송기 싱글톤"""
    global _email_notifier_instance
    if _email_notifier_instance is None:
        _email_notifier_instance = EmailNotifier()
    return _email_notifier_instance
