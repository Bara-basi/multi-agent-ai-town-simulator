from model.definitions.LocationDef import LocationDef,LocationId
from model.definitions.ActorDef import ActorDef,ActorId
from model.definitions.ItemDef import ItemDef,ItemId
from model.state.LocationState import LocationState,component_mapping
from model.state.ActorState import ActorState 
from model.definitions.Catalog import Catalog
from typing import Dict,Tuple
def build_location_state(locations:Dict[LocationId,LocationDef]) -> Dict[LocationId,LocationState]:
    location_states:Dict[LocationId,LocationState] = {}
    for location_id, location_def in locations.items():
        components = {
            component: component_mapping[component].get_instance()
            for component in location_def.components
            if component in component_mapping
        }
        locationstate = LocationState(
            id=location_id,
            description=location_def.description,
            component=components
        )
        location_states[location_id] = locationstate
    return location_states

def build_actor_state(actors:Dict[ActorId,ActorDef]) -> Dict[ActorId,ActorState]:
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
            memory= [],
            mods= [],
            status= "busy"
        )
        actor_states[actor_id] = actor_state
    return actor_states

def build_state(catalog:Catalog) -> Tuple[Dict[ActorId,ActorState],Dict[LocationId,LocationState]]:
    actor_states = build_actor_state(catalog.actors)
    location_states = build_location_state(catalog.locations)
    return actor_states,location_states
