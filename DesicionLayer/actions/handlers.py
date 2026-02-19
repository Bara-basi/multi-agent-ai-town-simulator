from __future__ import annotations

from typing import Any, Callable, Dict

from actions.action_registry import register
from actions.validators import must_be_at, must_have_enough_money, must_have_item, must_have_stock
from model.state.actionResult import ActionResult


SkillHandler = Callable[[Any, Any], ActionResult]
_SKILL_REGISTRY: Dict[str, SkillHandler] = {}


def register_skill(skill_name: str):
    def deco(fn: SkillHandler) -> SkillHandler:
        if skill_name in _SKILL_REGISTRY:
            raise ValueError(f"Skill {skill_name} already registered")
        _SKILL_REGISTRY[skill_name] = fn
        return fn

    return deco


def _invoke_skill(skill_name: str, ctx: Any, act: Any) -> ActionResult:
    fn = _SKILL_REGISTRY.get(skill_name)
    if fn is None:
        return ActionResult(
            status=False,
            code="SKILL_NOT_FOUND",
            message=f"Skill '{skill_name}' is not registered",
        )
    return fn(ctx, act)


@register("consume", validators=[must_have_item(item_field="item")])
def handle_consume(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = getattr(act, "item", None) or getattr(act, "item_id", None) or getattr(act, "target", None)
    if not item_id:
        return ActionResult(status=False, code="INVALID", message="consume requires item")

    qty = int(getattr(act, "qty", 1) or 1)
    actor.inventory.remove(item_id, qty)

    item_def = ctx.catalog.item(item_id)
    for k, v in (item_def.effects or {}).items():
        if k in actor.attrs:
            actor.attrs[k].current = min(
                actor.attrs[k].max_value,
                actor.attrs[k].current + float(v) * qty,
            )
    return ActionResult(status=True, message=f"consume {item_id} x {qty}")


@register("move")
def handle_move(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    target = getattr(act, "target", None)
    if not target:
        return ActionResult(status=False, code="INVALID", message="move requires target")

    if target == actor.location:
        return ActionResult(status=True, message=f"already at {target}")

    actor.location = target
    return ActionResult(status=True, message=f"move to {target}")


@register("sleep", validators=[must_be_at(loc_id="location:home")])
def handle_sleep(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    fatigue = actor.attrs.get("fatigue")
    if fatigue is not None:
        fatigue.current = min(fatigue.max_value, fatigue.current + 20.0)
    return ActionResult(status=True, message="sleep")


@register("finish")
def handle_finish(ctx, act) -> ActionResult:
    _ = act
    return ActionResult(status=True, message="finish all actions", finish=True)


@register("wait")
def handle_wait(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    actor.status = "waiting"
    return ActionResult(status=True, message="wait for next turn")


@register(
    "buy",
    validators=[must_be_at(loc_id="location:market"), must_have_stock(), must_have_enough_money()],
)
def handle_buy(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = getattr(act, "item", None)
    if not item_id:
        return ActionResult(status=False, code="INVALID", message="buy requires item")

    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id)
    total = unit_price * qty

    actor.inventory.add(item_id, qty)
    actor.money -= total
    market.remove_stock(item_id, qty)
    return ActionResult(status=True, message=f"buy {item_id} x {qty}")


@register("sell", validators=[must_be_at(loc_id="location:market"), must_have_item(item_field="item", qty_field="qty")])
def handle_sell(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = getattr(act, "item", None)
    if not item_id:
        return ActionResult(status=False, code="INVALID", message="sell requires item")

    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id)

    actor.inventory.remove(item_id, qty)
    actor.money += unit_price * qty
    market.add_stock(item_id, qty)
    return ActionResult(status=True, message=f"sell {item_id} x {qty}")


@register_skill("example")
def example_skill(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    actor.status = "used-skill:example"
    return ActionResult(status=True, message=f"{actor.id} used skill example")


@register("skill")
def handle_skill(ctx, act) -> ActionResult:
    actor_id = getattr(act, "actor_id", None)
    if not actor_id:
        return ActionResult(status=False, code="INVALID", message="skill action requires actor_id")

    skill_name = getattr(act, "skill_name", None) or getattr(act, "skill", None)
    if not skill_name and ctx.catalog and hasattr(ctx.catalog, "actor"):
        try:
            actor_def = ctx.catalog.actor(actor_id)
            actor_skill = getattr(actor_def, "skill", None)
            if callable(actor_skill):
                return actor_skill(ctx, act)
            if isinstance(actor_skill, str) and actor_skill:
                skill_name = actor_skill
        except Exception:
            skill_name = None

    if not skill_name:
        return ActionResult(status=False, code="SKILL_EMPTY", message="No skill specified")

    return _invoke_skill(skill_name, ctx, act)
