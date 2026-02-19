from dataclasses import dataclass, field
from typing import Dict, Any,Optional,List

LocationId = str

@dataclass(frozen=True, slots=True)
class LocationDef: 
    id: LocationId
    name: str
    description: str
    components: List[str] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description
        }
    
