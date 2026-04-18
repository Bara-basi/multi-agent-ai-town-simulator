"""Actor runtime state definition."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    decision_point: int = 3
    decision_point_max: int = 3

    # Per-day decision point context for prompt rendering.
    decision_last_result: Dict[str, Any] = field(default_factory=dict)
    decision_intel: List[Dict[str, Any]] = field(default_factory=list)
    decision_locked_item: Optional[str] = None

    def can_go(self, loc: LocationId) -> bool:
        return loc in self.unlocked_locations

    def _normalize_item_id(self, item_id: str) -> str:
        if isinstance(item_id, str) and item_id.startswith("item:"):
            return item_id
        return f"item:{item_id}"

    def _short_item_id(self, item_id: str) -> str:
        if isinstance(item_id, str) and item_id.startswith("item:"):
            return item_id.split(":", 1)[1]
        return str(item_id)

    @staticmethod
    def _trend_text(cur_price: float, next_price: float) -> str:
        if cur_price <= 0:
            return "明日趋势未知"
        drift = next_price / cur_price
        if drift >= 1.3:
            return "明日大涨,推荐入手"
        if drift >= 1.1:
            return "明日小涨"
        if drift <= 0.7:
            return "明日大跌，推荐出手"
        if drift <= 0.9:
            return "明日小跌"
        return "明日平稳"

    def _base_decision_result(self, decision: str, reason: str) -> Dict[str, Any]:
        return {
            "decision": decision,
            "reason": reason,
            "dp_cost": 0,
            "cash_delta": 0.0,
            "intel": [],
            "locked_item": None,
            "private_note": "",
            "public_note": "",
            "lock_hidden": False,
        }

    def apply_decision_point(self, decision_payload: Dict[str, Any], *, catalog: Any, market: Any) -> Dict[str, Any]:
        decision = str((decision_payload or {}).get("decision") or "skip").strip().lower()
        reason = str((decision_payload or {}).get("reason") or "")
        raw_item = str((decision_payload or {}).get("item") or "").strip()

        valid_decisions = {"skip", "exchange_cash", "get_intel", "lock_price"}
        if decision not in valid_decisions:
            decision = "skip"
            reason = reason or "invalid_decision_fallback"

        result = self._base_decision_result(decision=decision, reason=reason)
        self.decision_intel = []
        self.decision_locked_item = None

        if decision == "skip":
            result["private_note"] = "本回合未使用决策点。"
            result["public_note"] = f"{self.id} 本回合未使用决策点。"
            self.decision_last_result = result
            return result

        if self.decision_point <= 0:
            result["decision"] = "skip"
            result["reason"] = reason or "decision_point_insufficient"
            result["private_note"] = "决策点不足，自动改为不使用。"
            result["public_note"] = f"{self.id} 决策点不足，未使用决策点。"
            self.decision_last_result = result
            return result

        if decision == "exchange_cash":
            self.decision_point = max(0, self.decision_point - 1)
            self.money += 40.0
            result["dp_cost"] = 1
            result["cash_delta"] = 40.0
            result["private_note"] = "消耗1点决策点，兑换40元现金。"
            result["public_note"] = f"{self.id} 使用决策点兑换了现金。"
            self.decision_last_result = result
            return result

        if decision == "lock_price":
            if not raw_item:
                result["decision"] = "skip"
                result["reason"] = reason or "lock_price_missing_item"
                result["private_note"] = "锁价失败：未指定商品，自动改为不使用。"
                result["public_note"] = f"{self.id} 本回合未使用决策点。"
                self.decision_last_result = result
                return result

            item_id = self._normalize_item_id(raw_item)
            if item_id not in (catalog.items or {}):
                result["decision"] = "skip"
                result["reason"] = reason or "lock_price_invalid_item"
                result["private_note"] = f"锁价失败：商品 {raw_item} 不存在，自动改为不使用。"
                result["public_note"] = f"{self.id} 本回合未使用决策点。"
                self.decision_last_result = result
                return result

            ok = bool(market.lock_price_for_next_day(item_id))
            if not ok:
                result["decision"] = "skip"
                result["reason"] = reason or "lock_price_failed"
                result["private_note"] = f"锁价失败：商品 {self._short_item_id(item_id)} 无法锁定。"
                result["public_note"] = f"{self.id} 本回合未使用决策点。"
                self.decision_last_result = result
                return result

            self.decision_point = max(0, self.decision_point - 1)
            result["dp_cost"] = 1
            result["locked_item"] = self._short_item_id(item_id)
            result["private_note"] = (
                f"消耗1点决策点，已锁定 {self._short_item_id(item_id)} 的明日价格1回合。"
                "锁价优先于情报：若其它Agent拿到该商品情报，情报会自动失效。"
            )
            # Lock decision is not visible to other agents.
            result["public_note"] = ""
            result["lock_hidden"] = True
            self.decision_locked_item = self._short_item_id(item_id)
            self.decision_last_result = result
            return result

        # get_intel
        self.decision_point = max(0, self.decision_point - 1)
        result["dp_cost"] = 1

        item_pool = list((market._stock or {}).keys()) if getattr(market, "_stock", None) else list((catalog.items or {}).keys())
        if not item_pool:
            result["private_note"] = "消耗1点决策点，但当前无可用商品情报。"
            result["public_note"] = f"{self.id} 使用了决策点获取情报。"
            self.decision_last_result = result
            return result

        pick_n = min(3, len(item_pool))
        picked = random.sample(item_pool, pick_n)

        intel_rows: List[Dict[str, Any]] = []
        for item_id in picked:
            cur_price = float(market.price(item_id))
            true_next_price, base_acc = market.next_price_info(item_id)
            declared_accuracy = round(float(base_acc), 2)

            # Lock precedence: lock invalidates intel immediately.
            if market.is_price_locked_for_next_day(item_id):
                intel_rows.append(
                    {
                        "item": self._short_item_id(item_id),
                        "current_price": round(cur_price, 2),
                        "intel_price": None,
                        "trend": "情报失效",
                        "accuracy": declared_accuracy,
                        "valid": False,
                        "invalid_reason": "该商品已被锁价，锁价优先于情报，情报自动失效。",
                    }
                )
                continue

            is_correct = random.random() <= declared_accuracy
            if is_correct:
                shown_next = float(true_next_price)
            else:
                shown_next = float(market.simulate_next_price_for_item(catalog, item_id, current_price=cur_price))

            intel_rows.append(
                {
                    "item": self._short_item_id(item_id),
                    "current_price": round(cur_price, 2),
                    "intel_price": round(shown_next, 2),
                    "trend": self._trend_text(cur_price, shown_next),
                    "accuracy": declared_accuracy,
                    "valid": bool(is_correct),
                    "invalid_reason": "",
                }
            )

        self.decision_intel = intel_rows
        result["intel"] = intel_rows
        result["private_note"] = "消耗1点决策点，获得3个商品的明日价格情报（含情报正确率）。"
        # 情报属于私有信息：对其它 Agent 完全不可见。
        result["public_note"] = ""
        self.decision_last_result = result
        return result

    def update_day(self) -> None:
        self.running = True
        self.memory.act_records.append([])
        self.decision_point = min(self.decision_point_max, int(self.decision_point) + 1)

        # Clear previous-day decision point effect context.
        self.decision_last_result = {}
        self.decision_intel = []
        self.decision_locked_item = None

        for attr in self.attrs.values():
            attr.current = min(attr.current - attr.decay_per_day, 100)
