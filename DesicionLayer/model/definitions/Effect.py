"""效果定义（buff/debuff）占位模型。"""

from dataclasses import dataclass
from typing import Any,Optional,List,Dict

@dataclass
class Effect:
    # 该结构尚未完全接入运行时，字段以扩展兼容为主。
    id:str 
    source:str 
    hooks:list[str]
    mods:List[Dict[str,Any]]
    scope:str
    duration_hours:Optional[float] = None
    location_id:Optional[str] = None
    item_id:Optional[str] = None
    priority:int = 0
    
