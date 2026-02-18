from __future__ import annotations
from typing import Any, Optional
from model.state.actionResult import ActionResult

def must_be_at(loc_id:str):
    def v(ctx,act):
        actor = ctx.world.actor(act.actor_id)
        if actor.location != loc_id:
            return ActionResult(False,code="FORBIDDEN",message="你必须处于 {} 才能执行对应的动作".format(loc_id))
        return None
    return v

def must_have_item(item_field:str = "item",qty_field:str = "qty",item_id:Optional[str]=None):
    def v(ctx,act):
        actor = ctx.world.actor(act.actor_id)
        if item_id is None:
            item_id = getattr(act,item_field)
        qty = int(getattr(act,qty_field,1) or 1)
        if not actor.inventory.has(item_id,qty):
            return ActionResult(False,code="FORBIDDEN",message="你没有足够的物品: {}".format(item_id))
        return None
    return v


def must_have_stock(item_field:str="item",qty_field:str="qty"):
    def v(ctx,act):
        location = ctx.world.location(act.location_id)
        item_id = getattr(act,item_field)
        qty = int(getattr(act,qty_field,1) or 1)
        stock = location.market().stock(item_id)
        if stock < qty:
            return ActionResult(False,code="FORBIDDEN",message="库存不足: {}".format(item_id))
        return None
    return v

def must_have_enough_money(item_field:str="item",qty_field:str="qty"):
    def v(ctx,act):
        actor = ctx.world.actor(act.actor_id)
        item_id = getattr(act,item_field)
        qty = int(getattr(act,qty_field,1) or 1)
        price = ctx.world.locations['market'].market().price(item_id)
        money = actor.inventory.count("money")
        if money < price * qty:
            return ActionResult(False,code="FORBIDDEN",message="金钱不足: {}".format(item_id))
        return None
    return v