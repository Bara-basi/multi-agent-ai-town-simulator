from __future__ import annotations

"""动作前置校验器：返回 ActionResult 代表失败，返回 None 代表通过。"""

from typing import Optional

from model.state.actionResult import ActionResult


def must_be_at(loc_id: str):
    # 校验 actor 是否在指定地点。
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        if actor.location != loc_id:
            return ActionResult(False, code="FORBIDDEN", message=f"must be at {loc_id}")
        return None

    return v


def must_have_item(item_field: str = "item", qty_field: str = "qty", item_id: Optional[str] = None):
    # 校验背包物品数量，可从动作里读 item/qty，或固定 item_id。
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        target_item_id = item_id or "item:"+ getattr(act, item_field, "")
        if not target_item_id:
            return ActionResult(False, code="INVALID", message="非法动作，动作中不包含物品ID")

        qty = int(getattr(act, qty_field, 1) or 1)
        if not actor.inventory.has(target_item_id, qty):
            return ActionResult(False, code="FORBIDDEN", message=f"你没有足够的 `{target_item_id}`")
        return None

    return v


def must_have_stock(item_field: str = "item", qty_field: str = "qty"):
    # 校验当前地点市场库存。
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        location = ctx.world.loc(actor.location)
        item_id = 'item:'+ getattr(act, item_field, "")
        if not item_id:
            return ActionResult(False, code="INVALID", message="购买动作未提供物品ID")

        qty = int(getattr(act, qty_field, 1) or 1)
        stock = location.market().stock(item_id)
        if stock < qty:
            return ActionResult(False, code="FORBIDDEN", message=f"库存货物 `{item_id}`不足")
        return None

    return v


def must_have_enough_money(item_field: str = "item", qty_field: str = "qty"):
    # 校验现金余额。
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        item_id = "item:"+getattr(act, item_field, None)
        if not item_id:
            return ActionResult(False, code="INVALID", message="非法动作，动作中不包含物品ID")

        qty = int(getattr(act, qty_field, 1) or 1)
        location = ctx.world.loc(actor.location)
        price = location.market().price(item_id)
        money = float(getattr(actor, "money", 0.0) or 0.0)
        if money < price * qty:
            return ActionResult(False, code="FORBIDDEN", message=f"你没有足够的钱以购买 `{item_id}`")
        return None

    return v
