"""背包数量容器。"""

from dataclasses import dataclass, field
from typing import Dict
from model.definitions.ItemDef import ItemId

@dataclass(slots=True)
class Inventory:
    qty: Dict[ItemId, int] = field(default_factory=dict)

    def has(self, item_id: ItemId, n: int = 1) -> bool:
        return self.qty.get(item_id, 0) >= n

    def add(self, item_id: ItemId, n: int = 1) -> None:
        self.qty[item_id] = self.qty.get(item_id, 0) + n

    def remove(self, item_id: ItemId, n: int = 1) -> None:
        # 库存不足时抛错，由动作层决定如何转成 ActionResult。
        cur = self.qty.get(item_id, 0)
        if cur < n:
            raise ValueError(f"not enough {item_id}: {cur} < {n}")
        left = cur - n
        if left == 0:
            self.qty.pop(item_id, None)
        else:
            self.qty[item_id] = left

    
    def snapshot(self) -> str:
        # 输出紧凑字符串，便于直接写进 prompt。
        return ",".join(f"{k}x{v}" for k, v in self.qty.items())
