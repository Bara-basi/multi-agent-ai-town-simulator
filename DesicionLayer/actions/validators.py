from __future__ import annotations

from typing import Optional

from model.state.actionResult import ActionResult


def must_be_at(loc_id: str):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        if actor.location != loc_id:
            return ActionResult(False, code="FORBIDDEN", message=f"must be at {loc_id}")
        return None

    return v


def must_have_item(item_field: str = "item", qty_field: str = "qty", item_id: Optional[str] = None):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        target_item_id = item_id or getattr(act, item_field, None)
        if not target_item_id:
            return ActionResult(False, code="INVALID", message="missing item id")

        qty = int(getattr(act, qty_field, 1) or 1)
        if not actor.inventory.has(target_item_id, qty):
            return ActionResult(False, code="FORBIDDEN", message=f"not enough item: {target_item_id}")
        return None

    return v


def must_have_stock(item_field: str = "item", qty_field: str = "qty"):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        location = ctx.world.loc(actor.location)
        item_id = getattr(act, item_field, None)
        if not item_id:
            return ActionResult(False, code="INVALID", message="missing item id")

        qty = int(getattr(act, qty_field, 1) or 1)
        stock = location.market().stock(item_id)
        if stock < qty:
            return ActionResult(False, code="FORBIDDEN", message=f"stock not enough: {item_id}")
        return None

    return v


def must_have_enough_money(item_field: str = "item", qty_field: str = "qty"):
    def v(ctx, act):
        actor = ctx.world.actor(act.actor_id)
        item_id = getattr(act, item_field, None)
        if not item_id:
            return ActionResult(False, code="INVALID", message="missing item id")

        qty = int(getattr(act, qty_field, 1) or 1)
        location = ctx.world.loc(actor.location)
        price = location.market().price(item_id)
        money = float(getattr(actor, "money", 0.0) or 0.0)
        if money < price * qty:
            return ActionResult(False, code="FORBIDDEN", message=f"money not enough: {item_id}")
        return None

    return v
