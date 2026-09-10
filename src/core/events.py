from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True)
class PipelineEvent:
    """Immutable event emitted during ETL execution."""
    
    # The name or type of the event (e.g., "ETL_STARTED", "FILE_PROCESSED")
    name: str
    
    # A dictionary containing dynamic data associated with the event
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Automatically set the timestamp to the current UTC time when the event is created
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventObserver(Protocol):
    """Observer interface for ETL pipeline events."""

    # Any class implementing this protocol must define an 'on_event' method
    def on_event(self, event: PipelineEvent) -> None:
        ...


class EventBus:
    """Simple in-memory event dispatcher implementing the Observer pattern."""

    def __init__(self) -> None:
        # Initialize an empty list to keep track of all subscribed observers
        self._observers: List[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        # Prevent duplicate subscriptions by checking if the observer is already in the list
        if observer not in self._observers:
            self._observers.append(observer)

    def publish(self, name: str, **payload: Any) -> None:
        # Create a new immutable PipelineEvent instance with the provided name and payload
        event = PipelineEvent(name=name, payload=payload)
        
        # Iterate over a copy of the observers list (using list()) to safely handle 
        # cases where an observer might unsubscribe while the loop is running
        for observer in list(self._observers):
            # Notify each subscribed observer by passing the event object
            observer.on_event(event)