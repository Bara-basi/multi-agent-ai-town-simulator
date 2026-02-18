from dataclasses import dataclass
from typing import Any,Optional,List,Dict

@dataclass
class Effect:
    id:str 
    source:str 
    hooks:list[str]
    mods:List[Dict[str,Any]]
    scope:str
    duration_hours:Optional[float] = None
    location_id:Optional[str] = None
    item_id:Optional[str] = None
    priority:int = 0
    
