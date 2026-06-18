"""ALTEREGO OS — Event Bus (V1: in-process asyncio).

V2 will swap to NATS JetStream without changing the EventBus protocol.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Awaitable, Callable

from loguru import logger

from alterego.kernel.base import Event


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Abstract event bus protocol. Same interface for V1 (asyncio) and V2 (NATS)."""

    async def publish(self, subject: str, payload: dict[str, Any], source: str = "") -> None:
        raise NotImplementedError

    def subscribe(self, subject: str, handler: EventHandler) -> str:
        """Subscribe to a subject. Returns a subscription id.

        Subject supports wildcards:
          - `mission.*` matches `mission.created`, `mission.completed`, etc.
          - `*` matches everything
        """
        raise NotImplementedError

    def unsubscribe(self, sub_id: str) -> None:
        raise NotImplementedError


class InProcessEventBus(EventBus):
    """V1 in-process event bus.

    - All subscribers run in the same process (asyncio)
    - Subjects support `*` wildcard for single segment
    - Handlers are awaited sequentially per event (V1: simple; V2: concurrent)
    """

    def __init__(self) -> None:
        self._subs: dict[str, tuple[str, str, EventHandler]] = {}  # sub_id -> (pattern, subject, handler)
        self._counter = 0
        self._lock = asyncio.Lock()

    async def publish(self, subject: str, payload: dict[str, Any], source: str = "") -> None:
        event = Event(subject=subject, payload=payload, source=source, timestamp=datetime.utcnow())
        logger.debug(f"event → {subject} from {source} :: {payload}")

        # Find matching subscribers
        matched = []
        async with self._lock:
            for sub_id, (pattern, _, handler) in self._subs.items():
                if self._matches(pattern, subject):
                    matched.append((sub_id, handler))

        # Invoke handlers sequentially
        for sub_id, handler in matched:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"event handler {sub_id} failed for {subject}: {e}")

    def subscribe(self, subject_pattern: str, handler: EventHandler) -> str:
        self._counter += 1
        sub_id = f"sub-{self._counter}"
        self._subs[sub_id] = (subject_pattern, subject_pattern, handler)
        logger.debug(f"subscribed {sub_id} to pattern '{subject_pattern}'")
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        if sub_id in self._subs:
            del self._subs[sub_id]
            logger.debug(f"unsubscribed {sub_id}")

    @staticmethod
    def _matches(pattern: str, subject: str) -> bool:
        """Match a pattern like 'mission.*' against 'mission.created'."""
        if pattern == "*":
            return True
        pattern_parts = pattern.split(".")
        subject_parts = subject.split(".")
        if len(pattern_parts) != len(subject_parts):
            return False
        for p, s in zip(pattern_parts, subject_parts):
            if p != "*" and p != s:
                return False
        return True
