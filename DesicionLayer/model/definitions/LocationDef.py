"""地点静态定义。"""

from dataclasses import dataclass, field
from typing import Dict, Any,Optional,List

LocationId = str

@dataclass(frozen=True, slots=True)
class LocationDef: 
    id: LocationId
    name: str
    description: str
    type: List[str] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        # prompt 场景目前只需要名称和描述。
        return {
            "name": self.name,
            "description": self.description
        }
    
