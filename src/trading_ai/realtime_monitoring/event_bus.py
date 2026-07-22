from __future__ import annotations
import asyncio
from collections import deque
from .models import RealtimeEvent

class EventBus:
    def __init__(self, history_size: int = 1000):
        self._subscribers: set[asyncio.Queue[RealtimeEvent]] = set()
        self._history: deque[RealtimeEvent] = deque(maxlen=history_size)
        self.published = 0

    def subscribe(self) -> asyncio.Queue[RealtimeEvent]:
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=250)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RealtimeEvent]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: RealtimeEvent) -> None:
        self._history.append(event); self.published += 1
        for queue in tuple(self._subscribers):
            if queue.full():
                try: queue.get_nowait()
                except asyncio.QueueEmpty: pass
            queue.put_nowait(event)

    def history(self, limit: int = 100) -> list[RealtimeEvent]:
        return list(self._history)[-max(1, min(limit, 1000)):]

    @property
    def connected_clients(self) -> int: return len(self._subscribers)
