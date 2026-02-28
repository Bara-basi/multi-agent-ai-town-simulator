"""世界级动态状态容器：负责观察快照和日期推进。"""

from dataclasses import dataclass, field
from typing import Any, Dict

from actions.hooks import ON_DAILY_SETTLE
from model.definitions.ActorDef import ActorId
from model.definitions.Catalog import Catalog
from model.definitions.LocationDef import LocationId
from model.state.ActorState import ActorState
from model.state.LocationState import LocationState
import logging
logger = logging.getLogger(__name__)

@dataclass(slots=True)
class WorldState:
    catalog: Catalog
    day: int = 1
    actors: Dict[ActorId, ActorState] = field(default_factory=dict)
    locations: Dict[LocationId, LocationState] = field(default_factory=dict)

    def actor(self, actor_id: ActorId) -> ActorState:
        return self.actors[actor_id]

    def loc(self, loc_id: LocationId) -> LocationState:
        return self.locations[loc_id]

    def update_day(self) -> None:
        """
        尝试进入下一回合，如果有任何Actor仍在执行，则不推进。
        """
        for actor in self.actors.values():
            if actor.running:
                return
        # 顺序：day+1 -> 地点刷新 -> 角色刷新 -> 日结算 hook。
        
        self.day += 1
        for location in self.locations.values():
            update_fn = getattr(location, "update_day", None)
            if callable(update_fn):
                update_fn(self.catalog)
        for actor in self.actors.values():
            actor.update_day()
        ON_DAILY_SETTLE(self)
        logger.info(f"回合结算成功,进入回合{self.day}")

    def observe(self, actor_id: ActorId) -> Dict[str, Any]:
        # 输出统一观察视图，供 PromptBuilder 构造提示词。
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
            "inventory": actor.inventory.snapshot(self.catalog),
            # 结构化库存，便于提示词构造可执行性边界检查。
            "inventory_map": dict(getattr(actor.inventory, "qty", {}) or {}),
            "identity": f"你叫{name}，{gender}，{age}岁。{info}",
            "skill": getattr(actor_def, "skill", None),
        }

        location_snapshot: Dict[str, Any] = {}
        for loc_id, location in self.locations.items():
            location_snapshot[loc_id] = location.observe()

        catalog_snapshot = self.catalog.snapshot()
        raw_events = getattr(actor, "working_events", [])
        working_events = [getattr(e, "name", str(e)) for e in raw_events]
        memory_obj = actor.memory
        memory_text = memory_obj.observe() if hasattr(memory_obj, "observe") else ""
        memory_current_plan = (
            memory_obj.observe_current_plan() if hasattr(memory_obj, "observe_current_plan") else memory_text
        )
        memory_previous_plans = (
            memory_obj.observe_previous_plans() if hasattr(memory_obj, "observe_previous_plans") else ""
        )

        return {
            "actor_snapshot": actor_snapshot,
            "day": self.day,
            "location_snapshot": location_snapshot,
            "catalog_snapshot": catalog_snapshot,
            "working_events": working_events,
            "memory": memory_text,
            "memory_current_plan": memory_current_plan,
            "memory_previous_plans": memory_previous_plans,
        }
