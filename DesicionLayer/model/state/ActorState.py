from typing import Dict,List,Any,Callable
from dataclasses import dataclass,field 
from model.definitions.Inventory import Inventory
from model.definitions.LocationDef import LocationId
from model.definitions.ActorDef import ActorId
@dataclass(slots=True)
class Attribute:

    # 属性类，用于定义角色的各种属性
    name:str 
    current:float
    decay_per_day: float = 0.0
    max_value:float = 100.0


@dataclass(slots=True)
class ActorState:
    id: ActorId
    money: float
    location: LocationId
    home: LocationId
    attrs: Dict[str, Attribute] = field(default_factory=dict)
    inventory: Inventory = field(default_factory=Inventory)
    
    known_locations: set[LocationId] = field(default_factory=set)
    unlocked_locations: set[LocationId] = field(default_factory=set)

    memory: List[str] = field(default_factory=list)

    # 人物的特殊概率加成或其它特殊处理配置
    mods:List[Dict[str,Any]] = field(default_factory=list)
    
    status:str = "busy"

    def can_go(self, loc: LocationId) -> bool:
        return loc in self.unlocked_locations
