"""WebSocket connection manager with bounded client queues and heartbeats."""

import asyncio
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("predator.api.websockets")


class WebSocketManager:
    """Manages active WebSocket client connections with bounded outgoing queues."""

    def __init__(self, max_queue_size: int = 100):
        self.max_queue_size = max_queue_size
        self._active_connections: Set[WebSocket] = set()
        self._client_queues: Dict[WebSocket, asyncio.Queue] = {}
        self._client_tasks: Dict[WebSocket, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
            self._active_connections.add(websocket)
            self._client_queues[websocket] = queue
            task = asyncio.create_task(self._client_sender_loop(websocket, queue))
            self._client_tasks[websocket] = task
        logger.info("WebSocket client connected. Total clients: %d", len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active_connections.discard(websocket)
            task = self._client_tasks.pop(websocket, None)
            if task and not task.done():
                task.cancel()
            self._client_queues.pop(websocket, None)
        logger.info("WebSocket client disconnected. Total clients: %d", len(self._active_connections))

    async def _client_sender_loop(self, websocket: WebSocket, queue: asyncio.Queue) -> None:
        try:
            while True:
                msg = await queue.get()
                await websocket.send_text(json.dumps(msg))
                queue.task_done()
        except (asyncio.CancelledError, WebSocketDisconnect):
            pass
        except Exception as e:
            logger.debug("Client sender loop terminated: %s", e)
        finally:
            await self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients, dropping oldest if queue full."""
        async with self._lock:
            sockets = list(self._active_connections)

        for ws in sockets:
            q = self._client_queues.get(ws)
            if q:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    q.put_nowait(message)
                except asyncio.QueueFull:
                    pass

    def get_connected_count(self) -> int:
        return len(self._active_connections)
