"""定义层 -> 运行时状态层的组装逻辑。"""

from model.definitions.LocationDef import LocationDef,LocationId
from model.definitions.ActorDef import ActorDef,ActorId
from model.definitions.ItemDef import ItemDef,ItemId
from model.state.LocationState import LocationState, MarketComponent
from model.state.ActorState import ActorState 
from model.definitions.Catalog import Catalog
from model.definitions.MemoryStore import MemoryStore
from typing import Dict,Tuple
def build_location_state(locations:Dict[LocationId,LocationDef]) -> Dict[LocationId,LocationState]:
    # 每个地点根据 components 声明实例化动态组件（如 market）。
    location_states:Dict[LocationId,LocationState] = {}
    for location_id, location_def in locations.items():
        locationstate = LocationState(
            id=location_id,
            description=location_def.description,
        )
        if location_def.type=="market":
            locationstate.components["market"] = MarketComponent()
            locationstate.market().init_stock()
        
        location_states[location_id] = locationstate
    return location_states

def build_actor_state(actors:Dict[ActorId,ActorDef]) -> Dict[ActorId,ActorState]:
    # 角色初始状态目前使用统一默认值，后续可按 ActorDef 扩展差异化初始化。
    actor_states:Dict[ActorId,ActorState] = {}
    for actor_id,actor_def in actors.items():
        actor_state = ActorState(
            id = actor_id,
            money = 1000,
            location = "location:home",
            home = "location:home",
            inventory= [],
            known_locations= ["location:home"],
            unlocked_locations=["location:market"],
            memory= MemoryStore(),
            mods= [],
            status= "busy"
        )
        actor_states[actor_id] = actor_state
    return actor_states

def build_state(catalog:Catalog) -> Tuple[Dict[ActorId,ActorState],Dict[LocationId,LocationState]]:
    # 主入口：同时构建 actor/location 两类动态状态。
    actor_states = build_actor_state(catalog.actors)
    location_states = build_location_state(catalog.locations)
    return actor_states,location_states
