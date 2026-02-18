from __future__ import annotations
from dataclasses import dataclass,field
from typing import Optional,Dict,Any
from model.definitions.LocationDef import LocationId
from model.definitions.ItemDef import ItemId
from model.definitions.Catalog import Catalog




@dataclass(slots=True)
class MarketComponent:
    stock:Dict[ItemId,int]
    price:Dict[ItemId,float]

    def init_stock(self, catalog:Catalog):
        self.stock = {item_id:0 for item_id in catalog.item_ids}
        self.price = {item_id:catalog.item(item_id).price for item_id in catalog.item_ids}

    def observe(self) -> Dict[str,Any]:
        return {"stock":self.stock, "price":self.price}
    
    @property
    def stock(self,ItemId) -> int:
        return self.stock.get(ItemId,0)
    @property
    def price(self,ItemId) -> float:
        return self.price.get(ItemId,0.0)
    def add_stock(self,ItemId,qty):
        self.stock[ItemId] = self.stock.get(ItemId,0) + qty

    def remove_stock(self,ItemId,qty):
        self.stock[ItemId] = self.stock.get(ItemId,0) - qty
    @classmethod
    def get_instance(cls)->MarketComponent:
        market_component = MarketComponent()
        return market_component


component_mapping = {
    "market":MarketComponent
}
@dataclass(slots=True)
class LocationState:
    id:LocationId

    component:Dict[str,Any] = field(default_factory=dict)

    
    def market(self) -> MarketComponent:
        return self.component["market"]
    
    
    def observe(self) -> Dict[str,Any]:
        obs = {"id":self.id, "desp":self.desp}
        for name,c in self.component.items():
            obs[name] = c.observe()
        return obs
