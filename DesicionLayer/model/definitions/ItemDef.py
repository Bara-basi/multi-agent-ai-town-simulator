from dataclasses import dataclass, field
from typing import Dict, Any

ItemId = str 

@dataclass(frozen=True,slots=True)
class ItemDef:
    id: ItemId
    name: str
    category:str
    description: str
    base_price: float
    sell_ratio: float
    effects: Dict[str, float] = field(default_factory=dict)
    
    

    def snapshot(self) -> Dict[str, Any]:
        snapshot = {
            "name": self.name,
            "description": self.description,
        }
        for effect, value in (self.effects or {}).items():
            snapshot[effect] = value
        return snapshot
