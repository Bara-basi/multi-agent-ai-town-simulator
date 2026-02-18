from dataclasses import dataclass
from typing import Dict, Any,Optional,List

LocationId = str

@dataclass(frozen=True, slots=True)
class LocationDef: 
    id: LocationId
    name: str
    description: str
    components: List[str] = []

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description
        }
    