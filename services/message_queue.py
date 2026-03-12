"""
RabbitMQ Message Queue Manager
────────────────────────────────
Handles:
  • Persistent connection / channel management
  • Publishing argument messages to `arguments_queue`
  • Publishing judgment-trigger messages to `judgment_queue`
  • Health-check

Queue architecture:
  ┌─────────────────────┐        ┌──────────────────────┐
  │  FastAPI route      │──────▶│  arguments_queue     │
  │  (per argument)     │        │  (durable, RabbitMQ) │
  └─────────────────────┘        └─────────┬────────────┘
                                            │ consumed by
                                  ┌─────────▼────────────┐
                                  │  JudgmentWorker      │
                                  │  (counts & buffers)  │
                                  └─────────┬────────────┘
                                            │ when ≥10/side
                                  ┌─────────▼────────────┐
                                  │  judgment_queue      │
                                  │  (durable, RabbitMQ) │
                                  └─────────┬────────────┘
                                            │ consumed by
                                  ┌─────────▼────────────┐
                                  │  JudgmentWorker      │
                                  │  (Mistral inference) │
                                  └──────────────────────┘
"""

from __future__ import annotations
import json
import logging
from typing import Any, Optional

import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractRobustConnection, AbstractChannel

from config.settings import settings

logger = logging.getLogger(__name__)


class RabbitMQManager:
    """Manages a single async RabbitMQ connection with automatic reconnect."""

    def __init__(self):
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None

    async def connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=1)

            # Declare both queues (idempotent)
            await self._channel.declare_queue(
                settings.ARGUMENTS_QUEUE, durable=True
            )
            await self._channel.declare_queue(
                settings.JUDGMENT_QUEUE, durable=True
            )
            logger.info("RabbitMQ connected ✓  queues: %s, %s",
                        settings.ARGUMENTS_QUEUE, settings.JUDGMENT_QUEUE)

        except Exception as exc:
            logger.warning(
                "RabbitMQ unavailable (%s). Queuing will use in-memory fallback.", exc
            )
            self._connection = None
            self._channel = None

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ disconnected")

    async def health(self) -> str:
        if self._connection and not self._connection.is_closed:
            return "connected"
        return "unavailable (in-memory fallback active)"

    async def publish_argument(self, payload: dict) -> None:
        """Publish a single argument event to the arguments queue."""
        await self._publish(settings.ARGUMENTS_QUEUE, payload)

    async def publish_judgment_trigger(self, payload: dict) -> None:
        """Publish a judgment-trigger event (sent once min threshold is met)."""
        await self._publish(settings.JUDGMENT_QUEUE, payload)

    async def _publish(self, queue_name: str, payload: dict) -> None:
        if self._channel is None:
            # Graceful degradation – log and continue (worker uses in-memory)
            logger.debug("RabbitMQ unavailable; skipping publish to %s", queue_name)
            return
        try:
            body = json.dumps(payload, default=str).encode()
            message = Message(
                body=body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await self._channel.default_exchange.publish(
                message, routing_key=queue_name
            )
            logger.debug("Published to %s: %s", queue_name, payload.get("type", ""))
        except Exception as exc:
            logger.error("Failed to publish to %s: %s", queue_name, exc)

    async def get_argument_queue(self):
        """Return the arguments queue object for consumer use."""
        if self._channel is None:
            return None
        return await self._channel.get_queue(settings.ARGUMENTS_QUEUE)

    async def get_judgment_queue(self):
        """Return the judgment queue object for consumer use."""
        if self._channel is None:
            return None
        return await self._channel.get_queue(settings.JUDGMENT_QUEUE)


# ── Singleton ─────────────────────────────────────────────────────────────────
rabbitmq_manager = RabbitMQManager()
