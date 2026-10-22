"""Bounded asynchronous event bus with backpressure handling for SOLANA PREDATOR."""

import asyncio
import logging
from typing import Dict, List, Callable, Awaitable, Any, Optional
from backend.models import NormalizedMarketEvent
from backend.config import settings

logger = logging.getLogger("predator.market.event_bus")


class EventBus:
    """Bounded, thread-safe asynchronous event dispatcher with queue monitoring."""

    def __init__(self, maxsize: Optional[int] = None):
        self.maxsize = maxsize or settings.EVENT_QUEUE_MAXSIZE
        self._queue: asyncio.Queue[NormalizedMarketEvent] = asyncio.Queue(maxsize=self.maxsize)
        self._subscribers: List[Callable[[NormalizedMarketEvent], Awaitable[None]]] = []
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._published_count = 0
        self._processed_count = 0
        self._dropped_count = 0
        self._high_water_mark = 0

    async def start(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("EventBus started with queue maxsize=%d", self.maxsize)

    async def stop(self) -> None:
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped.")

    def subscribe(self, callback: Callable[[NormalizedMarketEvent], Awaitable[None]]) -> None:
        """Register an async callback for incoming normalized market events."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    async def publish(self, event: NormalizedMarketEvent) -> bool:
        """Publish an event to the queue with backpressure overflow handling."""
        self._published_count += 1
        q_size = self._queue.qsize()
        if q_size > self._high_water_mark:
            self._high_water_mark = q_size

        if self._queue.full():
            # Drop oldest event to relieve backpressure
            try:
                dropped = self._queue.get_nowait()
                self._dropped_count += 1
                logger.warning("EventBus queue full (%d)! Dropped oldest event %s", self.maxsize, dropped.event_id)
            except asyncio.QueueEmpty:
                pass

        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            logger.error("Failed to enqueue event %s due to persistent queue full", event.event_id)
            return False

    async def _process_queue(self) -> None:
        while self._running:
            try:
                event = await self._queue.get()
                self._processed_count += 1
                for sub in self._subscribers:
                    try:
                        await sub(event)
                    except Exception as e:
                        logger.error("Error in subscriber callback for event %s: %s", event.event_id, e)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in event loop worker: %s", e)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "queue_depth": self._queue.qsize(),
            "queue_maxsize": self.maxsize,
            "high_water_mark": self._high_water_mark,
            "published_total": self._published_count,
            "processed_total": self._processed_count,
            "dropped_total": self._dropped_count,
            "subscriber_count": len(self._subscribers),
        }
