from __future__ import annotations

"""Built-in action handlers registered by action name."""

from typing import Any, Callable, Dict

from actions.action_registry import register
from actions.hooks import ON_ACTION_RESOLVE
from actions.validators import must_be_at, must_have_enough_money, must_have_item, must_have_stock
from config.config import (
    FATIGUE_DECAY_PER_ACTION,
    FATIGUE_DECAY_PER_DAY,
    HUNGER_DECAY_PER_DAY,
    THIRST_DECAY_PER_DAY,
)
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
async def handle_consume(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = getattr(act, "item", None) or getattr(act, "item_id", None) or getattr(act, "target", None)
    if ":" not in item_id:
        item_id = "item:" + item_id

    item = ctx.catalog.item(item_id)
    qty = int(getattr(act, "qty", 1) or 1)
    result = await ctx.world.client.consume(actor.id, item, qty)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 消耗 {item.name}")

    actor.inventory.remove(item_id, qty)
    fatigue = actor.attrs.get("fatigue")
    fatigue.current -= FATIGUE_DECAY_PER_ACTION

    for k, v in (item.effects or {}).items():
        if k in actor.attrs:
            actor.attrs[k].current = min(
                actor.attrs[k].max_value,
                actor.attrs[k].current + float(v) * qty,
            )

    return ActionResult(status=True, message=f"你使用了 {ctx.world.catalog.item(item_id).name} x {qty}")


@register("move")
async def handle_move(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    target = getattr(act, "target", None)

    if target == actor.location:
        return ActionResult(status=False, code="INVALID", message=f"移动失败，你已经在 {ctx.catalog.loc(target).name} 了")

    result = await ctx.world.client.move(
        act.actor_id,
        ctx.world.catalog.loc(actor.location).name,
        ctx.world.catalog.loc(target).name,
    )
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 移动到{ctx.catalog.loc(target).name}")

    actor.location = target
    fatigue = actor.attrs.get("fatigue")
    fatigue.current -= FATIGUE_DECAY_PER_ACTION
    ON_ACTION_RESOLVE("on_move", ctx, act)
    return ActionResult(status=True, message=f"你来到了{ctx.catalog.loc(target).name}")


@register("sleep", validators=[must_be_at(loc_id="location:home")])
async def handle_sleep(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    result = await ctx.world.client.sleep(act.actor_id)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 睡觉")

    fatigue = actor.attrs.get("fatigue")
    fatigue.current = min(fatigue.max_value, fatigue.current - FATIGUE_DECAY_PER_DAY)
    hunger = actor.attrs.get("hunger")
    thirst = actor.attrs.get("thirst")
    hunger.current = min(hunger.max_value, hunger.current - HUNGER_DECAY_PER_DAY)
    thirst.current = min(thirst.max_value, thirst.current - THIRST_DECAY_PER_DAY)
    return ActionResult(status=True, message="你睡了一觉，感觉神清气爽")


@register("finish")
def handle_finish(ctx, act) -> ActionResult:
    _ = ctx, act
    return ActionResult(status=True, message="finished", finish=True)


@register("wait")
async def handle_wait(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    actor.running = False
    await ctx.world.update_day()
    return ActionResult(status=True, message="你结束了上个回合")


@register("buy", validators=[must_be_at(loc_id="location:market"), must_have_stock(), must_have_enough_money()])
async def handle_buy(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = "item:" + act.item
    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id)
    total = unit_price * qty

    result = await ctx.world.client.buy(actor.id, qty, total)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 购买{ctx.world.catalog.item(item_id).name}")

    actor.inventory.add(item_id, qty)
    actor.money -= total
    market.remove_stock(item_id, qty)
    fatigue = actor.attrs.get("fatigue")
    fatigue.current -= FATIGUE_DECAY_PER_ACTION
    return ActionResult(status=True, message=f"你购买了 {ctx.world.catalog.item(item_id).name} x {qty}，单价 {unit_price:.2f}元/件")


@register("sell", validators=[must_be_at(loc_id="location:market"), must_have_item(item_field="item", qty_field="qty")])
async def handle_sell(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = "item:" + act.item
    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id) * ctx.world.catalog.item(item_id).sell_ratio

    result = await ctx.world.client.sell(actor.id, qty, unit_price * qty)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 出售{ctx.world.catalog.item(item_id).name}")

    actor.inventory.remove(item_id, qty)
    actor.money += unit_price * qty
    market.add_stock(item_id, qty)
    fatigue = actor.attrs.get("fatigue")
    fatigue.current -= FATIGUE_DECAY_PER_ACTION
    return ActionResult(status=True, message=f"你出售了 {ctx.world.catalog.item(item_id).name} x {qty}，单价 {unit_price:.2f}元/件")


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

