from __future__ import annotations

"""Location runtime state and dynamic components (currently market-focused)."""

from dataclasses import dataclass, field
from typing import Any, Dict, Set, Tuple

import numpy as np

from config.config import (
    DEFAULT_MARKET_STOCK_INCREASE,
    INTEL_ACCURACY_MAX,
    INTEL_ACCURACY_MIN,
    KAPPA,
    MARKET_PRICE_CHANGE_PROB,
    SIGMA,
)
from model.definitions.Catalog import Catalog
from model.definitions.ItemDef import ItemId
from model.definitions.LocationDef import LocationId

rng = np.random.default_rng(42)


@dataclass(slots=True)
class MarketComponent:
    _stock: Dict[ItemId, int] = field(default_factory=dict)
    _price: Dict[ItemId, float] = field(default_factory=dict)
    # item_id -> (next_price, intel_accuracy)
    _next_price: Dict[ItemId, Tuple[float, float]] = field(default_factory=dict)
    # Locked items apply to next-day price generation and are consumed after one update_day.
    _locked_next_day_items: Set[ItemId] = field(default_factory=set)

    def init_stock(self, catalog: Catalog) -> None:
        self._stock = {item_id: item_def.default_quantity for item_id, item_def in catalog.items.items()}
        self._price = {
            item_id: float(catalog.item(item_id).base_price)
            for item_id in catalog.items.keys()
        }
        self.generate_price(catalog)

    def observe(self) -> Dict[str, Any]:
        return {
            "stock": self._stock,
            "price": self._price,
            "next_price": self._next_price,
        }

    def stock(self, item_id: ItemId) -> int:
        return int(self._stock.get(item_id, 0))

    def price(self, item_id: ItemId) -> float:
        return float(self._price.get(item_id, 0.0))

    def next_price_info(self, item_id: ItemId) -> Tuple[float, float]:
        cur = self.price(item_id)
        return self._next_price.get(item_id, (cur, 1.0))

    def add_stock(self, item_id: ItemId, qty: int) -> None:
        q = max(int(qty), 0)
        self._stock[item_id] = self.stock(item_id) + q

    def remove_stock(self, item_id: ItemId, qty: int) -> None:
        q = max(int(qty), 0)
        left = self.stock(item_id) - q
        self._stock[item_id] = max(left, 0)

    def is_price_locked_for_next_day(self, item_id: ItemId) -> bool:
        return item_id in self._locked_next_day_items

    def lock_price_for_next_day(self, item_id: ItemId) -> bool:
        if item_id not in self._stock:
            return False
        self._locked_next_day_items.add(item_id)
        # Immediate override for the upcoming day (N -> N+1 transition).
        cur = self.price(item_id)
        _old_next, acc = self._next_price.get(item_id, (cur, 1.0))
        self._next_price[item_id] = (cur, acc)
        return True

    def simulate_next_price_for_item(self, catalog: Catalog, item_id: ItemId, current_price: float | None = None) -> float:
        cur = float(current_price if current_price is not None else self.price(item_id))
        cur = max(cur, 1e-6)
        item_def = catalog.item(item_id)
        base_price = max(float(item_def.base_price), 1e-6)
        kappa = float(KAPPA[item_def.category])
        sigma = float(SIGMA[item_def.category])

        ln_p = np.log(cur)
        ln_base = np.log(base_price)
        ln_p = ln_p + kappa * (ln_base - ln_p) + rng.normal(0.0, sigma)
        return max(float(np.exp(ln_p)), 0.01)

    def generate_price(self, catalog: Catalog) -> None:
        if not self._stock:
            self._next_price = {}
            return

        next_price: Dict[ItemId, Tuple[float, float]] = {}
        for item_id in self._stock.keys():
            cur = self.price(item_id)
            if self.is_price_locked_for_next_day(item_id):
                candidate = cur
            else:
                if rng.random() < MARKET_PRICE_CHANGE_PROB:
                    candidate = self.simulate_next_price_for_item(catalog, item_id, current_price=cur)
                else:
                    candidate = cur

            accuracy = float(rng.uniform(INTEL_ACCURACY_MIN, INTEL_ACCURACY_MAX))
            next_price[item_id] = (float(candidate), accuracy)

        self._next_price = next_price

    def update_day(self, catalog: Catalog) -> None:
        # Daily restock.
        for item_id in list(self._stock.keys()):
            self._stock[item_id] = min(
                catalog.item(item_id).default_quantity,
                self.stock(item_id) + DEFAULT_MARKET_STOCK_INCREASE,
            )

        # Today's price takes previous next_price.
        new_price: Dict[ItemId, float] = {}
        for item_id in self._stock.keys():
            next_val, _acc = self._next_price.get(item_id, (self.price(item_id), 1.0))
            new_price[item_id] = float(next_val)
        self._price = new_price

        # Lock applies to N->N+1 only; clear before generating N+2.
        self._locked_next_day_items.clear()

        # Generate tomorrow's prices with probability-based fluctuation.
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
        obs: Dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "desp": self.description,
        }
        for name, comp in self.component.items():
            if hasattr(comp, "observe"):
                obs[name] = comp.observe()
        return obs

    def update_day(self, catalog: Catalog) -> None:
        for name, comp in self.component.items():
            if hasattr(comp, "update_day"):
                comp.update_day(catalog)
