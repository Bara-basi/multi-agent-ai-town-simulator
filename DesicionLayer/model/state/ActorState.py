"""角色运行时状态定义。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from model.definitions.ActorDef import ActorId
from model.definitions.Inventory import Inventory
from model.definitions.LocationDef import LocationId
from model.definitions.MemoryStore import MemoryStore


@dataclass(slots=True)
class Attribute:
    # 单个可衰减/可恢复属性（如 hunger、thirst、fatigue）。
    name: str
    current: float
    decay_per_day: float = 0.0
    max_value: float = 100.0


@dataclass(slots=True)
class ActorState:
    # 动态角色状态：会随动作执行和 day 推进持续变化。
    id: ActorId
    money: float
    location: LocationId
    home: LocationId
    memory: MemoryStore
    attrs: Dict[str, Attribute] = field(default_factory=dict)
    inventory: Inventory = field(default_factory=Inventory)
    known_locations: set[LocationId] = field(default_factory=set)
    unlocked_locations: set[LocationId] = field(default_factory=set)
    # 预留：人物特性修正（buff/debuff 或技能加成）。
    mods: List[Dict[str, Any]] = field(default_factory=list)
    status: bool = True

    def can_go(self, loc: LocationId) -> bool:
        return loc in self.unlocked_locations

    def update_day(self):
        # 新的一天：恢复可行动，并新开一条当日行为记录。
        self.status = True
        self.memory.act_records.append([])
