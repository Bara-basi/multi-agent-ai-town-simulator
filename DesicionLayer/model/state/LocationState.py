from __future__ import annotations

"""地点运行时状态及动态组件（当前重点是 market）。"""

from dataclasses import dataclass, field
from typing import Any, Dict
import numpy as np
from model.definitions.Catalog import Catalog
from model.definitions.ItemDef import ItemId
from model.definitions.LocationDef import LocationId
from config.config import DEFAULT_MARKET_STOCK,DEFAULT_MARKET_STOCK_INCREASE,KAPPA,SIGMA

rng = np.random.default_rng(42)

@dataclass(slots=True)
class MarketComponent:
    _stock: Dict[ItemId, int] = field(default_factory=dict)
    _price: Dict[ItemId, float] = field(default_factory=dict)
    _next_price: Dict[ItemId, float] = field(default_factory=dict)

    def init_stock(self, catalog: Catalog) -> None:
        # 初始化为“全品类可交易”，价格先使用物品基准价。
        self._stock = {item_id: item_def.default_quantity for item_id,item_def in catalog.items.items()}
        self._price = {
            item_id: float(catalog.item(item_id).base_price)
            for item_id in catalog.items.keys()
        }
        self.generate_price(catalog)

    def observe(self) -> Dict[str, Any]:
        return {"stock": self._stock, "price": self._price,"next_price": self._next_price}

    def stock(self, item_id: ItemId) -> int:
        return int(self._stock.get(item_id, 0))

    def price(self, item_id: ItemId) -> float:
        return float(self._price.get(item_id, 0.0))

    def add_stock(self, item_id: ItemId, qty: int) -> None:
        q = max(int(qty), 0)
        self._stock[item_id] = self.stock(item_id) + q

    def remove_stock(self, item_id: ItemId, qty: int) -> None:
        q = max(int(qty), 0)
        left = self.stock(item_id) - q
        self._stock[item_id] = max(left, 0)

    def generate_price(self,catalog: Catalog) -> None:
        item_ids = np.array(list(self._stock.keys()), dtype=object)
        if item_ids.size == 0:
            self._next_price = {}
            return

        current_prices = np.fromiter(
            (self._price[item_id] for item_id in item_ids),
            dtype=float,
            count=item_ids.size,
        )
        base_prices = np.fromiter(
            (catalog.item(item_id).base_price for item_id in item_ids),
            dtype=float,
            count=item_ids.size,
        )
        kappa = np.fromiter(
            (KAPPA[catalog.item(item_id).category] for item_id in item_ids),
            dtype=float,
            count=item_ids.size,
        )
        sigma = np.fromiter(
            (SIGMA[catalog.item(item_id).category] for item_id in item_ids),
            dtype=float,
            count=item_ids.size,
        )

        
        lnP = np.log(current_prices)
        lnbase = np.log(base_prices)
        lnP = lnP + kappa * (lnbase - lnP) + rng.normal(0.0, sigma, size=lnP.shape)
        self._next_price = dict(zip(item_ids.tolist(), np.exp(lnP).tolist()))
            


    def update_day(self,catalog: Catalog):
        # 每日补货到固定库存。
        for item_id in self._stock.keys():
            self._stock[item_id] = min(catalog.item(item_id).default_quantity, self.stock(item_id)+DEFAULT_MARKET_STOCK_INCREASE)
            self._price = self._next_price
        self.generate_price(catalog)
    @classmethod
    def get_instance(cls) -> "MarketComponent":
        return cls()


component_mapping = {"market": MarketComponent}


@dataclass(slots=True)
class LocationState:
    id: LocationId
    description: str = ""
    component: Dict[str, Any] = field(default_factory=dict)

    def market(self) -> MarketComponent:
        return self.component["market"]

    def observe(self) -> Dict[str, Any]:
        # 将地点自身字段和各组件 observe() 聚合成统一快照。
        obs: Dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "desp": self.description,
        }
        for name, comp in self.component.items():
            if hasattr(comp, "observe"):
                obs[name] = comp.observe()
        return obs
    def update_day(self,catalog: Catalog) -> None:
        for name, comp in self.component.items():
            if hasattr(comp, "update_day"):
                comp.update_day(catalog)
