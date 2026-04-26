from __future__ import annotations

"""Location runtime state and dynamic components (currently market-focused)."""

from dataclasses import dataclass, field
import inspect
from typing import Any, Dict, Iterable, Set, Tuple

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
    _locked_today_items: Set[ItemId] = field(default_factory=set)

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
            "locked_today": list(self._locked_today_items),
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

    def is_price_locked_today(self, item_id: ItemId) -> bool:
        return item_id in self._locked_today_items

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

    def _short_item_id(self, item_id: str) -> str:
        if isinstance(item_id, str) and item_id.startswith("item:"):
            return item_id.split(":", 1)[1]
        return str(item_id)

    def _normalize_item_id(self, item_id: str) -> str:
        if isinstance(item_id, str) and item_id.startswith("item:"):
            return item_id
        return f"item:{item_id}"

    def _resolve_update_item_id(self, catalog: Catalog, raw: Any) -> ItemId | None:
        key = str(raw or "").strip()
        if not key:
            return None
        if key in catalog.items:
            return key
        normalized = self._normalize_item_id(key)
        if normalized in catalog.items:
            return normalized
        for item_id, item_def in catalog.items.items():
            if str(item_def.name).strip() == key:
                return item_id
        return None

    def _apply_decision_price_effects(self, catalog: Catalog, actors: Iterable[Any] | None) -> Set[ItemId]:
        locked_items: Set[ItemId] = set()

        for item_id in list(self._locked_next_day_items):
            if item_id in self._stock:
                cur = self.price(item_id)
                _old_next, acc = self._next_price.get(item_id, (cur, 1.0))
                self._next_price[item_id] = (cur, acc)
                locked_items.add(item_id)

        for actor in actors or []:
            for row in list(getattr(actor, "decision_intel", []) or []):
                if not bool(row.get("valid", False)):
                    continue
                item_id = self._resolve_update_item_id(catalog, row.get("item"))
                if not item_id or item_id in locked_items:
                    continue
                try:
                    intel_price = float(row.get("intel_price"))
                except Exception:
                    continue
                if intel_price <= 0:
                    continue
                _old_next, acc = self._next_price.get(item_id, (self.price(item_id), 1.0))
                self._next_price[item_id] = (float(intel_price), acc)
                locked_items.add(item_id)

        return locked_items

    async def update_day(
        self,
        catalog: Catalog,
        *,
        client: Any = None,
        day: int = 1,
        human_actor: Any = None,
        actors: Iterable[Any] | None = None,
        advance_prices: bool = True,
    ) -> None:
        locked_items = self._apply_decision_price_effects(catalog, actors)

        # Old simulated daily restock/price fluctuation logic, kept for reference:
        # for item_id in list(self._stock.keys()):
        #     self._stock[item_id] = min(
        #         catalog.item(item_id).default_quantity,
        #         self.stock(item_id) + DEFAULT_MARKET_STOCK_INCREASE,
        #     )
        #
        # new_price: Dict[ItemId, float] = {}
        # for item_id in self._stock.keys():
        #     next_val, _acc = self._next_price.get(item_id, (self.price(item_id), 1.0))
        #     new_price[item_id] = float(next_val)
        # self._price = new_price
        # self._locked_next_day_items.clear()
        # self.generate_price(catalog)

        new_price: Dict[ItemId, float] = {}
        if advance_prices:
            for item_id in self._stock.keys():
                next_val, _acc = self._next_price.get(item_id, (self.price(item_id), 1.0))
                new_price[item_id] = float(next_val)
            self._price = new_price

        self._locked_today_items = {
            item_id for item_id in locked_items
            if item_id in self._stock
        }
        self._locked_next_day_items.clear()

        if client is not None:
            clear_updates = getattr(client, "clear_stock_updates", None)
            if callable(clear_updates):
                clear_updates()

            send_info = getattr(client, "send_information", None)
            if callable(send_info):
                info = client.market_information() if callable(getattr(client, "market_information", None)) else {}
                result = send_info(target="market", info=info)
                if inspect.isawaitable(result):
                    await result

            round_start = getattr(client, "round_start", None)
            if callable(round_start) and human_actor is not None:
                result = round_start(human_actor.id, day)
                if inspect.isawaitable(result):
                    await result

            wait_update = getattr(client, "wait_shop_stock_update", None)
            if callable(wait_update):
                update_msg = await wait_update(timeout_s=300.0)
                self.apply_shop_stock_update(catalog, update_msg, human_actor=human_actor)

        self.generate_price(catalog)

    def apply_shop_stock_update(self, catalog: Catalog, update_msg: Any, *, human_actor: Any = None) -> None:
        if not update_msg:
            return
        payload = update_msg.get("parsed_info", update_msg) if isinstance(update_msg, dict) else update_msg
        if not isinstance(payload, dict):
            return

        if human_actor is not None and "currentMoney" in payload:
            try:
                human_actor.money = float(payload.get("currentMoney", human_actor.money))
            except Exception:
                pass

        for row in payload.get("items", []) or []:
            if not isinstance(row, dict):
                continue
            item_id = self._resolve_update_item_id(catalog, row.get("itemId") or row.get("name"))
            if not item_id:
                continue
            try:
                self._stock[item_id] = max(0, int(row.get("currentStock", self.stock(item_id))))
            except Exception:
                pass
            if item_id not in self._locked_today_items:
                try:
                    self._price[item_id] = max(0.0, float(row.get("todayPrice", self.price(item_id))))
                except Exception:
                    pass

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

    async def update_day(
        self,
        catalog: Catalog,
        *,
        client: Any = None,
        day: int = 1,
        human_actor: Any = None,
        actors: Iterable[Any] | None = None,
        advance_prices: bool = True,
    ) -> None:
        for name, comp in self.component.items():
            if hasattr(comp, "update_day"):
                result = comp.update_day(
                    catalog,
                    client=client,
                    day=day,
                    human_actor=human_actor,
                    actors=actors,
                    advance_prices=advance_prices,
                )
                if inspect.isawaitable(result):
                    await result
