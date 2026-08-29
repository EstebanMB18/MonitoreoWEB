from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from threading import RLock
from typing import Callable
from uuid import uuid4


@dataclass
class MonitorEvent:
    event_id: str
    timestamp: datetime
    run_id: str
    monitor: str
    level: str
    event_type: str
    message: str
    progress: int | None = None
    data: dict | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


class EventBus:
    def __init__(self) -> None:
        self._lock = RLock()
        self._events: dict[str, list[MonitorEvent]] = {}
        self._subscribers: dict[str, list[Callable[[MonitorEvent], None]]] = {}

    def publish(
        self,
        *,
        run_id: str,
        monitor: str,
        message: str,
        level: str = "INFO",
        event_type: str = "LOG",
        progress: int | None = None,
        data: dict | None = None,
    ) -> MonitorEvent:

        event = MonitorEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(),
            run_id=run_id,
            monitor=monitor.upper(),
            level=level.upper(),
            event_type=event_type.upper(),
            message=message,
            progress=progress,
            data=data,
        )

        with self._lock:
            self._events.setdefault(run_id, []).append(event)
            subscribers = list(self._subscribers.get(run_id, []))

        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                # Un subscriber nunca debe romper la ejecución principal.
                pass

        return event

    def get_events(
        self,
        run_id: str,
        after_event_id: str | None = None,
    ) -> list[MonitorEvent]:

        with self._lock:
            events = list(self._events.get(run_id, []))

        if not after_event_id:
            return events

        for index, event in enumerate(events):
            if event.event_id == after_event_id:
                return events[index + 1 :]

        return events

    def subscribe(
        self,
        run_id: str,
        callback: Callable[[MonitorEvent], None],
    ) -> None:
        with self._lock:
            self._subscribers.setdefault(run_id, []).append(callback)

    def unsubscribe(
        self,
        run_id: str,
        callback: Callable[[MonitorEvent], None],
    ) -> None:
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])

            if callback in subscribers:
                subscribers.remove(callback)

            if not subscribers:
                self._subscribers.pop(run_id, None)

    def clear(self, run_id: str) -> None:
        with self._lock:
            self._events.pop(run_id, None)
            self._subscribers.pop(run_id, None)
