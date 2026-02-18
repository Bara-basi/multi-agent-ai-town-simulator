from model.definitions.LocationDef import LocationDef,LocationId
from model.definitions.ActorDef import ActorDef,ActorId
from model.definitions.ItemDef import ItemDef,ItemId
from model.state.LocationState import LocationState,component_mapping
from model.state.ActorState import ActorState 
from typing import Dict
def build_location_state(locations:Dict[LocationId,LocationDef]) -> Dict[LocationId,LocationState]:
    location_states:Dict[LocationId,LocationState] = {}
    for location_id,LocationDef in locations.items():
        locationstate = LocationState(
            id=location_id,
            component= {component:component_mapping[component].get_instance() for component in LocationDef.components}
        )
        location_states[location_id] = locationstate
    return location_states

def builder_actor_state(actors:Dict[ActorId,ActorDef]) -> Dict[ActorId,ActorState]:
    actor_states:Dict[ActorId,ActorState] = {}
    for actor_id,actor_def in actors.items():
        actor_states = ActorState(
            id = actor_id,
            money = 1000,
            location = "location:home",
            home = "location:home",
            inventory= [],
            known_locations= ["location:home"],
            unlocked_locations=["location:market"],
            memory= [],
            mods= [],
            status= "busy"
        )

