"""
Asynchronous event queue for approval notifications (Phase 6.4)

Handles notification events with background worker processing,
batch optimization, and retry logic.
"""

import asyncio
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ApprovalEventType(str, Enum):
    """승인 이벤트 타입"""

    REQUESTED = "approval_requested"
    TIMEOUT = "approval_timeout"
    APPROVED = "approval_approved"
    REJECTED = "approval_rejected"


class ApprovalEvent:
    """승인 이벤트"""

    def __init__(self, event_type: ApprovalEventType, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now()
        self.retry_count = 0
        self.max_retries = 3

    def __repr__(self):
        request_id = self.data.get("request_id", "unknown")[:8]
        return f"ApprovalEvent({self.event_type.value}, {request_id})"


class ApprovalEventQueue:
    """비동기 승인 이벤트 큐 (싱글톤)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.queue = asyncio.Queue()
            self.running = False
            self.worker_task = None
            self._initialized = True

    async def enqueue(self, event_type: str, data: Dict[str, Any]):
        """이벤트 큐에 추가"""
        try:
            event_type_enum = ApprovalEventType(event_type)
            event = ApprovalEvent(event_type_enum, data)
            await self.queue.put(event)
            logger.info(f"Event enqueued: {event}")
        except ValueError:
            logger.error(f"Invalid event type: {event_type}")

    async def start_worker(self):
        """백그라운드 워커 시작"""
        if self.running:
            logger.warning("Worker already running")
            return
        self.running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Approval event queue worker started")

    async def stop_worker(self):
        """워커 정지"""
        if not self.running:
            return
        self.running = False
        if self.worker_task:
            try:
                await asyncio.wait_for(self.worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.worker_task.cancel()
        logger.info("Approval event queue worker stopped")

    async def _worker_loop(self):
        """워커 메인 루프 (배치 처리)"""
        from .email import EmailNotifier

        notifier = EmailNotifier()
        batch_size = int(os.getenv("NOTIFICATION_BATCH_SIZE", "10"))
        batch_timeout = float(os.getenv("NOTIFICATION_BATCH_TIMEOUT", "5"))

        while self.running:
            try:
                batch = []
                # 배치 채우기
                while len(batch) < batch_size and self.running:
                    try:
                        remaining_slots = batch_size - len(batch)
                        timeout = batch_timeout / max(1, remaining_slots)
                        event = await asyncio.wait_for(
                            self.queue.get(), timeout=timeout
                        )
                        batch.append(event)
                    except asyncio.TimeoutError:
                        # 타임아웃이 되면 현재 배치 처리
                        break

                # 배치 처리
                if batch:
                    await self._process_batch(batch, notifier)

            except Exception as e:
                logger.error(f"Worker loop error: {str(e)}")
                await asyncio.sleep(1)  # 에러 후 재시작 대기

    async def _process_batch(self, events: List[ApprovalEvent], notifier):
        """배치 처리로 성능 최적화"""
        tasks = [self._process_event(event, notifier) for event in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 로깅
        for event, result in zip(events, results):
            if isinstance(result, Exception):
                error_msg = f"Event processing failed for {event}: {str(result)}"
                logger.error(error_msg)

    async def _process_event(self, event: ApprovalEvent, notifier):
        """이벤트 처리"""
        try:
            # 템플릿 이름 결정
            template_map = {
                ApprovalEventType.REQUESTED: "approval_requested",
                ApprovalEventType.TIMEOUT: "approval_timeout",
                ApprovalEventType.APPROVED: "approval_approved",
                ApprovalEventType.REJECTED: "approval_rejected",
            }
            template_name = template_map.get(event.event_type)

            if not template_name:
                logger.warning(f"Unknown event type: {event.event_type}")
                return

            # Email 발송
            await notifier.send_notification(
                template_name=template_name, context=event.data
            )
            logger.info(f"Notification sent for {event}")

        except Exception as e:
            # 재시도 가능 여부 확인
            if event.retry_count < event.max_retries:
                event.retry_count += 1
                await self.queue.put(event)
                retry_msg = (
                    f"Retrying event {event} "
                    f"(attempt {event.retry_count}/{event.max_retries})"
                )
                logger.warning(retry_msg)
            else:
                error_msg = (
                    f"Event processing failed after {event.max_retries} "
                    f"retries: {str(e)}"
                )
                logger.error(error_msg)


def get_approval_event_queue() -> ApprovalEventQueue:
    """싱글톤 패턴: 이벤트 큐 반환"""
    return ApprovalEventQueue()
