"""Build runtime state from static definitions."""

import logging
from typing import Dict, Tuple

from model.definitions.ActorDef import ActorDef, ActorId
from model.definitions.Catalog import Catalog
from model.definitions.LocationDef import LocationDef, LocationId
from model.definitions.MemoryStore import MemoryStore
from model.state.ActorState import ActorState
from model.state.LocationState import LocationState, MarketComponent
from runtime.load_data import HUMAN_SHOP_ASSISTANT_ACTOR_ID

logger = logging.getLogger(__name__)


def build_location_state(catalog: Catalog) -> Dict[LocationId, LocationState]:
    locations: Dict[LocationId, LocationDef] = catalog.locations
    location_states: Dict[LocationId, LocationState] = {}
    for location_id, location_def in locations.items():
        locationstate = LocationState(
            id=location_id,
            description=location_def.description,
        )
        if location_def.type == "Market":
            locationstate.component["market"] = MarketComponent()
            locationstate.market().init_stock(catalog=catalog)
            logger.info("Market initialized")

        location_states[location_id] = locationstate
    return location_states


def _build_human_shop_assistant_state(actor_id: ActorId) -> ActorState:
    # Keep the human actor minimal for now: money is the only meaningful field.
    return ActorState(
        id=actor_id,
        money=1000,
        location="",
        home="",
        inventory=[],
        known_locations=[],
        unlocked_locations=[],
        memory=MemoryStore(),
    )


def build_actor_state(actors: Dict[ActorId, ActorDef]) -> Dict[ActorId, ActorState]:
    actor_states: Dict[ActorId, ActorState] = {}
    for actor_id, _actor_def in actors.items():
        if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
            actor_states[actor_id] = _build_human_shop_assistant_state(actor_id)
            continue

        actor_states[actor_id] = ActorState(
            id=actor_id,
            money=1000,
            location="location:home",
            home="location:home",
            inventory=[],
            known_locations=["location:home"],
            unlocked_locations=["location:market"],
            memory=MemoryStore(),
        )
    return actor_states


def build_state(catalog: Catalog) -> Tuple[Dict[ActorId, ActorState], Dict[LocationId, LocationState]]:
    actor_states = build_actor_state(catalog.actors)
    logger.info("All actor states initialized")
    location_states = build_location_state(catalog)
    logger.info("All location states initialized")
    return actor_states, location_states
