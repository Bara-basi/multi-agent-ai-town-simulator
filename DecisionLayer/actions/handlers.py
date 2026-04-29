from __future__ import annotations

"""Built-in action handlers registered by action name."""

import inspect
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
from runtime.load_data import HUMAN_SHOP_ASSISTANT_ACTOR_ID

SkillHandler = Callable[[Any, Any], ActionResult]
_SKILL_REGISTRY: Dict[str, SkillHandler] = {}


def _norm_item_id(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s if s.startswith("item:") else f"item:{s}"


def _shop_assistant_actor(ctx: Any):
    return ctx.world.actors.get(HUMAN_SHOP_ASSISTANT_ACTOR_ID)


async def _broadcast_market_information(ctx: Any) -> None:
    client = getattr(ctx.world, "client", None)
    if client is None:
        return
    market_information = getattr(client, "market_information", None)
    send_information = getattr(client, "send_information", None)
    if not callable(market_information) or not callable(send_information):
        return

    result = send_information(target="market", info=market_information())
    if inspect.isawaitable(result):
        await result


async def _broadcast_agent_information(ctx: Any) -> None:
    client = getattr(ctx.world, "client", None)
    if client is None:
        return

    broadcast = getattr(client, "broadcast_agent_information", None)
    if callable(broadcast):
        result = broadcast()
        if inspect.isawaitable(result):
            await result
        return

    agent_information = getattr(client, "agent_information", None)
    send_information = getattr(client, "send_information", None)
    if not callable(agent_information) or not callable(send_information):
        return

    result = send_information(target="agents", info=agent_information())
    if inspect.isawaitable(result):
        await result


def _actor_name(ctx: Any, actor_id: str) -> str:
    try:
        actor_def = ctx.world.catalog.actor(actor_id)
        return str(getattr(actor_def, "name", "") or actor_id)
    except Exception:
        return str(actor_id)


async def _broadcast_message(ctx: Any, source: str, message: str) -> None:
    client = getattr(ctx.world, "client", None)
    broadcast_message = getattr(client, "broadcast_message", None) if client is not None else None
    if not callable(broadcast_message):
        return
    result = broadcast_message(source, message)
    if inspect.isawaitable(result):
        await result


def _change_attr(actor: Any, attr_name: str, delta: float) -> None:
    attr = (getattr(actor, "attrs", None) or {}).get(attr_name)
    if attr is None:
        return

    current = float(getattr(attr, "current", 0.0) or 0.0)
    max_value = float(getattr(attr, "max_value", 100.0) or 100.0)
    attr.current = max(0.0, min(max_value, current + float(delta)))


async def _apply_action_fatigue(ctx: Any, actor: Any, *, animate: bool = False) -> None:
    if animate:
        client = getattr(ctx.world, "client", None)
        show_animation = getattr(client, "show_animation", None) if client is not None else None
        if callable(show_animation):
            result = show_animation(actor.id, "fatigue", -FATIGUE_DECAY_PER_ACTION)
            if inspect.isawaitable(result):
                await result

    _change_attr(actor, "fatigue", -FATIGUE_DECAY_PER_ACTION)


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
    await _apply_action_fatigue(ctx, actor)

    for k, v in (item.effects or {}).items():
        _change_attr(actor, k, float(v) * qty)

    await _broadcast_message(ctx, _actor_name(ctx, actor.id), f"使用了{item.name} x {qty}")
    await _broadcast_agent_information(ctx)
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
    await _apply_action_fatigue(ctx, actor)
    ON_ACTION_RESOLVE("on_move", ctx, act)
    await _broadcast_message(ctx, _actor_name(ctx, actor.id), f"来到了{ctx.catalog.loc(target).name}")
    await _broadcast_agent_information(ctx)
    return ActionResult(status=True, message=f"你来到了{ctx.catalog.loc(target).name}")


@register("sleep", validators=[must_be_at(loc_id="location:home")])
async def handle_sleep(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    result = await ctx.world.client.sleep(act.actor_id, ctx.world.catalog.loc(actor.location).name)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 睡觉")

    _change_attr(actor, "fatigue", -FATIGUE_DECAY_PER_DAY)
    _change_attr(actor, "hunger", -HUNGER_DECAY_PER_DAY)
    _change_attr(actor, "thirst", -THIRST_DECAY_PER_DAY)
    await _broadcast_agent_information(ctx)
    return ActionResult(status=True, message="你睡了一觉，感觉神清气爽")


@register("finish")
def handle_finish(ctx, act) -> ActionResult:
    _ = ctx, act
    return ActionResult(status=True, message="finished", finish=True)


@register("wait")
async def handle_wait(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    result = await ctx.world.client.move(act.actor_id, ctx.world.catalog.loc(actor.location).name, ctx.world.catalog.loc("location:home").name)
    result &= await ctx.world.client.sleep(act.actor_id, ctx.world.catalog.loc(actor.location).name)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 等待")
    actor.location = actor.home
    actor.running = False
    await ctx.world.update_day()
    return ActionResult(status=True, message="你结束了上个回合")


@register("buy", validators=[must_be_at(loc_id="location:market"), must_have_stock(), must_have_enough_money()])
async def handle_buy(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = _norm_item_id(getattr(act, "item", None))
    if not item_id:
        return ActionResult(status=False, code="INVALID", message="buy 缺少 item 字段")
    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id)
    total = unit_price * qty

    result = await ctx.world.client.buy(actor.id, qty, total, ctx.catalog.loc(actor.location).name, item_id=item_id)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 购买{ctx.world.catalog.item(item_id).name}")

    actor.update_inventory_buy_price_on_buy(item_id=item_id, qty=qty, unit_price=unit_price)
    actor.inventory.add(item_id, qty)
    actor.money -= total
    market.remove_stock(item_id, qty)
    shop_assistant = _shop_assistant_actor(ctx)
    if shop_assistant is not None:
        shop_assistant.money += total
    await _broadcast_market_information(ctx)
    await _apply_action_fatigue(ctx, actor)
    await _broadcast_message(ctx, _actor_name(ctx, actor.id), f"购买了{ctx.world.catalog.item(item_id).name} x {qty}")
    if market.stock(item_id) <= 0:
        await _broadcast_message(ctx, "商店", f"物品{ctx.world.catalog.item(item_id).name}已售罄")
    await _broadcast_agent_information(ctx)
    return ActionResult(status=True, message=f"你购买了 {ctx.world.catalog.item(item_id).name} x {qty}，单价 {unit_price:.2f}元/件")


@register("sell", validators=[must_be_at(loc_id="location:market"), must_have_item(item_field="item", qty_field="qty")])
async def handle_sell(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    item_id = _norm_item_id(getattr(act, "item", None))
    if not item_id:
        return ActionResult(status=False, code="INVALID", message="sell 缺少 item 字段")
    qty = int(getattr(act, "qty", 1) or 1)
    market = ctx.world.locations["location:market"].market()
    unit_price = market.price(item_id) * ctx.world.catalog.item(item_id).sell_ratio
    total = unit_price * qty
    shop_assistant = _shop_assistant_actor(ctx)
    if shop_assistant is not None and float(getattr(shop_assistant, "money", 0.0) or 0.0) < total:
        return ActionResult(
            status=False,
            code="FORBIDDEN",
            message=f"动作sell执行失败,商店资金不足，无法收购 `{ctx.world.catalog.item(item_id).name}` x {qty}",
        )

    result = await ctx.world.client.sell(actor.id, qty, total, ctx.catalog.loc(actor.location).name, item_id=item_id)
    if not result:
        return ActionResult(status=False, code="INVALID", message=f"Unity 动画出错: 出售{ctx.world.catalog.item(item_id).name}")

    actor.inventory.remove(item_id, qty)
    actor.money += total
    market.add_stock(item_id, qty)
    if shop_assistant is not None:
        shop_assistant.money -= total
    await _broadcast_market_information(ctx)
    await _apply_action_fatigue(ctx, actor)
    await _broadcast_message(ctx, _actor_name(ctx, actor.id), f"出售了{ctx.world.catalog.item(item_id).name} x {qty}")
    await _broadcast_agent_information(ctx)
    return ActionResult(status=True, message=f"你出售了 {ctx.world.catalog.item(item_id).name} x {qty}，单价 {unit_price:.2f}元/件")


@register_skill("example")
def example_skill(ctx, act) -> ActionResult:
    actor = ctx.world.actor(act.actor_id)
    actor.status = "used-skill:example"
    return ActionResult(status=True, message=f"{actor.id} used skill example")


@register("skill")
async def handle_skill(ctx, act) -> ActionResult:
    actor_id = getattr(act, "actor_id", None)
    if not actor_id:
        return ActionResult(status=False, code="INVALID", message="skill action requires actor_id")

    actor = ctx.world.actor(actor_id)
    skill_name = getattr(act, "skill_name", None) or getattr(act, "skill", None)
    if not skill_name and ctx.catalog and hasattr(ctx.catalog, "actor"):
        try:
            actor_def = ctx.catalog.actor(actor_id)
            actor_skill = getattr(actor_def, "skill", None)
            if callable(actor_skill):
                result = actor_skill(ctx, act)
                if inspect.isawaitable(result):
                    result = await result
                if getattr(result, "status", False):
                    await _apply_action_fatigue(ctx, actor, animate=True)
                    await _broadcast_agent_information(ctx)
                return result
            if isinstance(actor_skill, str) and actor_skill:
                skill_name = actor_skill
        except Exception:
            skill_name = None

    if not skill_name:
        return ActionResult(status=False, code="SKILL_EMPTY", message="No skill specified")

    result = _invoke_skill(skill_name, ctx, act)
    if inspect.isawaitable(result):
        result = await result
    if getattr(result, "status", False):
        await _apply_action_fatigue(ctx, actor, animate=True)
        await _broadcast_agent_information(ctx)
    return result
