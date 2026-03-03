"""Actor runtime state definition."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from model.definitions.ActorDef import ActorId
from model.definitions.Inventory import Inventory
from model.definitions.LocationDef import LocationId
from model.definitions.MemoryStore import MemoryStore


@dataclass(slots=True)
class Attribute:
    name: str
    current: float
    decay_per_day: float = 0.0
    max_value: float = 100.0


@dataclass(slots=True)
class ActorState:
    id: ActorId
    money: float
    location: LocationId
    home: LocationId
    memory: MemoryStore = field(default_factory=MemoryStore)
    attrs: Dict[str, Attribute] = field(default_factory=dict)
    inventory: Inventory = field(default_factory=Inventory)
    known_locations: set[LocationId] = field(default_factory=set)
    unlocked_locations: set[LocationId] = field(default_factory=set)
    events: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    running: bool = True

    def can_go(self, loc: LocationId) -> bool:
        return loc in self.unlocked_locations

    def update_day(self) -> None:
        self.running = True
        self.memory.act_records.append([])
        for attr in self.attrs.values():
            attr.current = min(attr.current - attr.decay_per_day, 100)
