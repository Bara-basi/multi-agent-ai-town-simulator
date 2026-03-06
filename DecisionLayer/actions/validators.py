from __future__ import annotations

"""动作前置校验器：返回 ActionResult 代表失败，返回 None 代表通过。"""

from typing import Optional

from model.state.actionResult import ActionResult


def _normalize_item_id(raw: Optional[str]) -> str:
    item = str(raw or "").strip()
    if not item:
        return ""
    return item if item.startswith("item:") else f"item:{item}"


def _action_type(act) -> str:
    t = getattr(act, "type", None) or getattr(act, "name", None)
    return str(t or "")


def must_be_at(loc_id: str):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        if actor.location != loc_id:
            return ActionResult(
                False,
                code="FORBIDDEN",
                message=f"动作{_action_type(act)}执行失败,你必须在 {ctx.catalog.loc(loc_id).name}",
            )
        return None

    return v


def must_have_item(item_field: str = "item", qty_field: str = "qty", item_id: Optional[str] = None):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        target_item_id = _normalize_item_id(item_id or getattr(act, item_field, ""))
        if not target_item_id:
            return ActionResult(
                False,
                code="INVALID",
                message=f"动作{_action_type(act)}执行失败,非法动作,动作中不包含物品ID",
            )

        qty = int(getattr(act, qty_field, 1) or 1)
        if qty <= 0:
            return ActionResult(False, code="INVALID", message="数量必须大于0")

        if not actor.inventory.has(target_item_id, qty):
            return ActionResult(
                False,
                code="FORBIDDEN",
                message=f"动作{_action_type(act)}执行失败,你没有足够的 `{ctx.world.catalog.item(target_item_id).name}`",
            )
        return None

    return v


def must_have_stock(item_field: str = "item", qty_field: str = "qty"):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        location = ctx.world.loc(actor.location)
        item_id = _normalize_item_id(getattr(act, item_field, ""))
        if not item_id:
            return ActionResult(
                False,
                code="INVALID",
                message=f"动作{_action_type(act)}执行失败,未提供物品ID",
            )

        qty = int(getattr(act, qty_field, 1) or 1)
        if qty <= 0:
            return ActionResult(False, code="INVALID", message="数量必须大于0")

        stock = location.market().stock(item_id)
        if stock < qty:
            return ActionResult(
                False,
                code="FORBIDDEN",
                message=f"动作{_action_type(act)}执行失败,集市库存 `{ctx.world.catalog.item(item_id).name}`不足",
            )
        return None

    return v


def must_have_enough_money(item_field: str = "item", qty_field: str = "qty"):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        item_id = _normalize_item_id(getattr(act, item_field, None))
        if not item_id:
            return ActionResult(
                False,
                code="INVALID",
                message=f"动作{_action_type(act)}执行失败,非法动作,动作中不包含物品ID",
            )

        qty = int(getattr(act, qty_field, 1) or 1)
        if qty <= 0:
            return ActionResult(False, code="INVALID", message="数量必须大于0")

        location = ctx.world.loc(actor.location)
        price = location.market().price(item_id)
        money = float(getattr(actor, "money", 0.0) or 0.0)
        if money < price * qty:
            return ActionResult(
                False,
                code="FORBIDDEN",
                message=f"动作{_action_type(act)}执行失败,你没有足够的钱以购买 `{ctx.world.catalog.item(item_id).name}`",
            )
        return None

    return v
