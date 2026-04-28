"""世界级动态状态容器：负责观察快照和日期推进。"""

import copy
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

from actions.hooks import ON_DAILY_SETTLE
from config.config import RANDOM_EVENT_PORB,WIN_CONDITION
from model.definitions.ActorDef import ActorId
from model.definitions.Catalog import Catalog
from model.definitions.LocationDef import LocationId
from model.state.ActorState import ActorState
from model.state.LocationState import LocationState
from runtime.load_data import HUMAN_SHOP_ASSISTANT_ACTOR_ID

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WorldState:
    catalog: Catalog
    day: int = 1
    events: Dict[str, List[Any]] = field(default_factory=dict)
    actors: Dict[ActorId, ActorState] = field(default_factory=dict)
    locations: Dict[LocationId, LocationState] = field(default_factory=dict)
    client: Any = None
    shop_assistant_last_money: float = 1000.0

    def actor(self, actor_id: ActorId) -> ActorState:
        return self.actors[actor_id]

    def loc(self, loc_id: LocationId) -> LocationState:
        return self.locations[loc_id]


    def is_game_over(self,actor_id) -> bool:
        for attr in self.actor(actor_id=actor_id).attrs.values():
            if attr.current <= 0:
                return True
        return False

    def is_victory(self, actor_id) -> bool:
        return self.actor(actor_id=actor_id).money >= WIN_CONDITION
    async def update_day(self) -> None:
        """尝试进入下一回合，如果有任何 Actor 仍在执行，则不推进。"""
        for actor_id, actor in self.actors.items():
            if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
                continue
            if actor.running:
                return

        human_actor = self.actors.get(HUMAN_SHOP_ASSISTANT_ACTOR_ID)
        if human_actor is not None and self.client is not None:
            today_income = int(round(float(human_actor.money) - float(self.shop_assistant_last_money)))
            round_end = getattr(self.client, "round_end", None)
            if callable(round_end):
                result = round_end(HUMAN_SHOP_ASSISTANT_ACTOR_ID, today_income)
                if inspect.isawaitable(result):
                    await result
            self.shop_assistant_last_money = float(human_actor.money)

        # 顺序：回合结束动画 -> day+1 -> 玩家商店阶段 -> 角色刷新 -> 随机事件判定 -> 日结算 hook。
        self.day += 1
        await self.run_player_market_phase(advance_prices=True)
        for actor in self.actors.values():
            actor.update_day()

        self.determine_random_event()

        for actor_id in self.actors.keys():
            ON_DAILY_SETTLE("on_end_of_round", event=self.events, actor=self.actor(actor_id))

        if self.client is not None:
            broadcast_agent_information = getattr(self.client, "broadcast_agent_information", None)
            if callable(broadcast_agent_information):
                result = broadcast_agent_information()
                if inspect.isawaitable(result):
                    await result

        logger.info("回合结算成功,进入回合%s", self.day)

    async def run_player_market_phase(self, *, advance_prices: bool) -> None:
        human_actor = self.actors.get(HUMAN_SHOP_ASSISTANT_ACTOR_ID)
        for location in self.locations.values():
            update_fn = getattr(location, "update_day", None)
            if callable(update_fn):
                result = update_fn(
                    self.catalog,
                    client=self.client,
                    day=self.day,
                    human_actor=human_actor,
                    actors=self.actors.values(),
                    advance_prices=advance_prices,
                )
                if inspect.isawaitable(result):
                    await result
        if human_actor is not None:
            self.shop_assistant_last_money = float(human_actor.money)

    def invalidate_intel_for_locked_item(self, item_short_id: str) -> None:
        target = str(item_short_id or "").strip()
        if not target:
            return
        for actor in self.actors.values():
            intel_rows = list(getattr(actor, "decision_intel", []) or [])
            changed = False
            for row in intel_rows:
                if str(row.get("item", "")).strip() != target:
                    continue
                row["valid"] = False
                row["intel_price"] = None
                row["trend"] = "情报失效"
                row["invalid_reason"] = "该商品已被锁价，锁价优先于情报，情报自动失效。"
                changed = True
            if changed:
                actor.decision_intel = intel_rows

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
            "decision_point": int(getattr(actor, "decision_point", 0) or 0),
            "decision_point_max": int(getattr(actor, "decision_point_max", 3) or 3),
            "thirst": actor.attrs.get("thirst").current if actor.attrs.get("thirst") else 0.0,
            "hunger": actor.attrs.get("hunger").current if actor.attrs.get("hunger") else 0.0,
            "fatigue": actor.attrs.get("fatigue").current if actor.attrs.get("fatigue") else 0.0,
            "inventory": actor.inventory.snapshot(self.catalog),
            "inventory_map": dict(getattr(actor.inventory, "qty", {}) or {}),
            "inventory_buy_price_map": dict(getattr(actor.inventory, "buy_price", {}) or {}),
            "identity": f"你叫{name}，{gender}，{age}岁。{info}",
            "skill": getattr(actor_def, "skill", None),
        }

        decision_private_context = {
            "decision": (getattr(actor, "decision_last_result", {}) or {}).get("decision", "skip"),
            "reason": (getattr(actor, "decision_last_result", {}) or {}).get("reason", ""),
            "dp_cost": int((getattr(actor, "decision_last_result", {}) or {}).get("dp_cost", 0) or 0),
            "cash_delta": float((getattr(actor, "decision_last_result", {}) or {}).get("cash_delta", 0.0) or 0.0),
            "private_note": (getattr(actor, "decision_last_result", {}) or {}).get("private_note", ""),
            "locked_item": (getattr(actor, "decision_last_result", {}) or {}).get("locked_item"),
            "locked_items": list((getattr(actor, "decision_last_result", {}) or {}).get("locked_items", []) or []),
            "intel": list(getattr(actor, "decision_intel", []) or []),
            "executed_actions": list(getattr(actor, "decision_action_log", []) or []),
        }

        location_snapshot: Dict[str, Any] = {}
        for loc_id, location in self.locations.items():
            location_snapshot[loc_id] = location.observe()

        catalog_snapshot = self.catalog.snapshot()
        raw_events = getattr(actor, "working_events", [])
        working_events = [getattr(e, "name", str(e)) for e in raw_events]
        world_events: List[str] = []
        for hook_name, events in (self.events or {}).items():
            for event in events or []:
                desp = event['desp']
                duration = (event or {}).get("duration", -1)
                if isinstance(duration, (int, float)) and duration != -1:
                    world_events.append(f"{desp} , 剩余{int(duration)}回合]")
                else:
                    world_events.append(f"{name} [{hook_name}]")

        actor_buffs: List[str] = []
        for hook_name, events in (getattr(actor, "events", {}) or {}).items():
            for event in events or []:
                name = str((event or {}).get("name") or (event or {}).get("id") or "unknown")
                duration = (event or {}).get("duration", -1)
                if isinstance(duration, (int, float)) and duration != -1:
                    actor_buffs.append(f"{name} [{hook_name}, 剩余{int(duration)}回合]")
                else:
                    actor_buffs.append(f"{name} [{hook_name}]")

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
            "world_events": world_events,
            "actor_buffs": actor_buffs,
            "memory": memory_text,
            "memory_current_plan": memory_current_plan,
            "memory_previous_plans": memory_previous_plans,
            "decision_private_context": decision_private_context,
        }

    def determine_random_event(self) -> None:
        # 1) 更新当前事件持续时间
        for hook, events in list(self.events.items()):
            alive: List[Dict[str, Any]] = []
            for event in events:
                duration = (event or {}).get("duration", -1)
                if isinstance(duration, (int, float)) and duration != -1:
                    duration -= 1
                    if duration <= 0:
                        continue
                    event["duration"] = duration
                alive.append(event)

            if alive:
                self.events[hook] = alive
            else:
                self.events.pop(hook, None)

        # 2) 判定是否触发新随机事件
        random_event_pool = list((self.catalog.random_events or {}).values())
        if not random_event_pool:
            return

        if np.random.rand() < RANDOM_EVENT_PORB:
            template = np.random.choice(random_event_pool)
            event = copy.deepcopy(template)
            hooks = list((event or {}).get("hooks", []) or [])
            for hook in hooks:
                self.events.setdefault(hook, []).append(event)
            logger.info("随机事件触发：%s", event.get("name", "<unknown>"))
