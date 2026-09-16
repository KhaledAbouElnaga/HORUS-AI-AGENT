from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    kind: str
    payload: str
    event_id: str | None = None
