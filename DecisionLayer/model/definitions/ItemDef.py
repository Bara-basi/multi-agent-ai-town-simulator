"""物品静态定义。"""

from dataclasses import dataclass, field
from typing import Dict, Any

ItemId = str 

@dataclass(frozen=True,slots=True)
class ItemDef:
    id: ItemId
    name: str
    category:str
    description: str
    purchase_price: float
    base_price: float
    sell_ratio: float
    effects: Dict[str, float] = field(default_factory=dict)
    default_quantity: int = 0
    

    def snapshot(self) -> Dict[str, Any]:
        # prompt 视图：基础信息 + 可读效果字段。
        snapshot = {
            "name": self.name,
            "description": self.description,
            "purchase_price": self.purchase_price,
            "base_price": self.base_price,
            "effects": self.effects,
            "sell_ratio": self.sell_ratio
        }
        for effect, value in (self.effects or {}).items():
            snapshot[effect] = value
        return snapshot
