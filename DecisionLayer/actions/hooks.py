from __future__ import annotations

"""全局 hooks：将事件 mods 应用到 actor 状态。"""

from math import inf
from typing import Any, Dict, Iterable, List


def _collect_hook_events(hook_name: str, world_events: Dict[str, List[Dict[str, Any]]], actor) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    events.extend((world_events or {}).get(hook_name, []) or [])
    actor_events = getattr(actor, "events", {}) or {}
    events.extend(actor_events.get(hook_name, []) or [])
    return events


def _apply_single_mod(actor, mod: Dict[str, Any]) -> None:
    target = str(mod.get("target") or "").strip()
    op = str(mod.get("op") or "").strip().upper()

    if target.startswith("actor.attr."):
        attr_name = target.split(".")[-1]
        attr = actor.attrs.get(attr_name)
        if attr is None:
            return
        cur = float(getattr(attr, "current", 0.0))
        if op == "ADD":
            cur += float(mod.get("value", 0.0))
        elif op == "MUL":
            cur *= float(mod.get("value", 1.0))
        elif op == "OVERRIDE":
            cur = float(mod.get("value", cur))
        elif op == "CLAMP":
            cur = max(min(cur, float(mod.get("max", inf))), float(mod.get("min", -inf)))
        attr.current = cur
        return

    if target == "actor.money":
        cur_money = float(getattr(actor, "money", 0.0) or 0.0)
        if op == "ADD":
            cur_money += float(mod.get("value", 0.0))
        elif op == "MUL":
            cur_money *= float(mod.get("value", 1.0))
        elif op == "OVERRIDE":
            cur_money = float(mod.get("value", cur_money))
        elif op == "CLAMP":
            cur_money = max(min(cur_money, float(mod.get("max", inf))), float(mod.get("min", -inf)))
        actor.money = cur_money


def _apply_events(actor, events: Iterable[Dict[str, Any]]) -> None:
    for event in events:
        for mod in (event or {}).get("mods", []) or []:
            _apply_single_mod(actor, mod)


def ON_ACTION_RESOLVE(hook_name, ctx, act):
    """动作结算后触发。"""
    actor = ctx.world.actor(act.actor_id)
    events = _collect_hook_events(hook_name, getattr(ctx.world, "events", {}) or {}, actor)
    _apply_events(actor, events)


def ON_LOOT_ROLL():
    """战利品抽取时触发。"""


def ON_DAILY_SETTLE(hook_name, event, actor):
    """每日结算时触发。"""
    events = _collect_hook_events(hook_name, event or {}, actor)
    _apply_events(actor, events)


def ON_ENTER_LOCATION():
    """进入地点时触发。"""
    pass


