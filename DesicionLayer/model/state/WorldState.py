from typing import Dict, Any
from dataclasses import dataclass, field

from actions.hooks import ON_DAILY_SETTLE
from model.definitions.ActorDef import ActorId
from model.definitions.Catalog import Catalog
from model.definitions.LocationDef import LocationId
from model.state.ActorState import ActorState
from model.state.LocationState import LocationState


@dataclass(slots=True)
class WorldState:
    catalog: Catalog
    day: int = 0
    actors: Dict[ActorId, ActorState] = field(default_factory=dict)
    locations: Dict[LocationId, LocationState] = field(default_factory=dict)

    def actor(self, actor_id: ActorId) -> ActorState:
        return self.actors[actor_id]

    def loc(self, loc_id: LocationId) -> LocationState:
        return self.locations[loc_id]

    def update_day(self) -> None:
        self.day += 1
        for location in self.locations.values():
            update_fn = getattr(location, "update_day", None)
            if callable(update_fn):
                update_fn()
        ON_DAILY_SETTLE(self)

    def observe(self, actor_id: ActorId) -> Dict[str, Any]:
        actor = self.actor(actor_id)

        actor_def = None
        try:
            actor_def = self.catalog.actor(actor_id)
        except Exception:
            actor_def = None

        name = getattr(actor_def, "name", "")
        gender = getattr(actor_def, "gender", "")
        age = getattr(actor_def, "age", 0)
        info = getattr(actor_def, "info", "") or ""

        actor_snapshot = {
            "id": actor.id,
            "name": name,
            "home": actor.home,
            "cur_location": actor.location,
            "money": actor.money,
            "thirst": actor.attrs.get("thirst").current if actor.attrs.get("thirst") else 0.0,
            "hunger": actor.attrs.get("hunger").current if actor.attrs.get("hunger") else 0.0,
            "fatigue": actor.attrs.get("fatigue").current if actor.attrs.get("fatigue") else 0.0,
            "inventory": actor.inventory.snapshot(),
            "identity": f"你叫{name}，{gender}，{age}岁。{info}",
            "skill": getattr(actor_def, "skill", None),
        }

        location_snapshot: Dict[str, Any] = {}
        for loc_id, location in self.locations.items():
            location_snapshot[loc_id] = location.observe()

        catalog_snapshot = self.catalog.snapshot()
        raw_events = getattr(actor, "working_events", [])
        working_events = [getattr(e, "name", str(e)) for e in raw_events]

        return {
            "actor_snapshot": actor_snapshot,
            "day": self.day,
            "location_snapshot": location_snapshot,
            "catalog_snapshot": catalog_snapshot,
            "working_events": working_events,
        }
