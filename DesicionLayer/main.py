import asyncio
import logging
from typing import Dict

import actions.handlers 
from actions.executor import ActionExecutor
from config.runtime_config import AgentRuntimeConfig
from model.brains.AgentBrain import Agent
from model.brains.PromptBuilder import PromptBuilder
from model.definitions.ActorDef import ActorId
from model.definitions.Inventory import Inventory
from model.definitions.OpenAIModel import LLM
from model.state.ActorState import Attribute
from model.state.WorldState import WorldState
from runtime.build_state import build_state
from runtime.load_data import load_catalog
from runtime.runtime import AgentRuntime

MODEL_NAME = "gpt-4.1-mini-2025-04-14"
TICK_INTERVAL_SECONDS = 1.0


def _dispatch(_event_name: str, **_payload: object) -> None:
    return None


def _run_tick_blocking(runtime: AgentRuntime, actor_id: ActorId):
    return asyncio.run(runtime.tick_actor(actor_id))


def _bootstrap_world_state(world: WorldState) -> None:
    for actor in world.actors.values():
        if not isinstance(actor.inventory, Inventory):
            normalized = Inventory()
            raw = actor.inventory
            if isinstance(raw, dict):
                for item_id, qty in raw.items():
                    try:
                        q = int(qty)
                    except Exception:
                        continue
                    if q > 0:
                        normalized.add(str(item_id), q)
            elif isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        normalized.add(item, 1)
                    elif isinstance(item, dict):
                        item_id = item.get("item") or item.get("id")
                        try:
                            qty = int(item.get("qty", 1) or 1)
                        except Exception:
                            qty = 1
                        if item_id and qty > 0:
                            normalized.add(str(item_id), qty)
            actor.inventory = normalized

        attrs = actor.attrs or {}
        attrs.setdefault("hunger", Attribute(name="hunger", current=80.0, decay_per_day=8.0, max_value=100.0))
        attrs.setdefault("thirst", Attribute(name="thirst", current=80.0, decay_per_day=10.0, max_value=100.0))
        attrs.setdefault("fatigue", Attribute(name="fatigue", current=80.0, decay_per_day=6.0, max_value=100.0))
        actor.attrs = attrs

    for location in world.locations.values():
        market_getter = getattr(location, "market", None)
        if not callable(market_getter):
            continue
        try:
            market = market_getter()
        except Exception:
            continue
        init_stock = getattr(market, "init_stock", None)
        if callable(init_stock):
            try:
                init_stock(world.catalog)
            except Exception:
                logging.exception("market init failed for location: %s", getattr(location, "id", "<unknown>"))


async def _run_actor_loop(actor_id: ActorId, runtime: AgentRuntime, interval_seconds: float) -> None:
    while True:
        try:
            await asyncio.to_thread(_run_tick_blocking, runtime, actor_id)
        except Exception:
            logging.exception("actor loop crashed: %s", actor_id)
        await asyncio.sleep(interval_seconds)


async def run() -> None:
    catalog = load_catalog()
    actor_states, location_states = build_state(catalog)
    world = WorldState(
        catalog=catalog,
        actors=actor_states,
        locations=location_states,
    )
    _bootstrap_world_state(world)

    runtime_config = AgentRuntimeConfig()
    executor = ActionExecutor(
        world=world,
        dispatch=_dispatch,
        config=runtime_config,
        catalog=catalog,
        logger=logging.getLogger("action"),
    )

    runtimes: Dict[ActorId, AgentRuntime] = {}
    for actor_id, actor in actor_states.items():
        agent = Agent(
            id=actor_id,
            model=LLM(model_name=MODEL_NAME),
            actor=actor,
            prompt_builder=PromptBuilder(),
        )
        runtimes[actor_id] = AgentRuntime(
            world=world,
            agent=agent,
            executor=executor,
            config=runtime_config,
            logger=logging.getLogger(f"runtime.{actor_id}"),
        )

    tasks = [
        asyncio.create_task(_run_actor_loop(actor_id, runtime, TICK_INTERVAL_SECONDS), name=f"actor-{actor_id}")
        for actor_id, runtime in runtimes.items()
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
