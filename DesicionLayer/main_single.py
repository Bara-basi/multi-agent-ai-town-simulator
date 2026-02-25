"""单 Agent 入口：构建世界后仅运行 actor.csv 中的首个角色。"""

import asyncio
import logging
import os
import shutil

import actions.handlers
from actions.executor import ActionExecutor
from config.runtime_config import AgentRuntimeConfig
from model.brains.AgentBrain import Agent
from model.brains.PromptBuilder import PromptBuilder
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
    # 事件分发预留点：当前版本未接入总线，仅保持接口形状。
    return None


def _bootstrap_world_state(world: WorldState) -> None:
    # 启动时兜底标准化：把历史数据结构纠正为当前运行时期望形状。
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
        attrs.setdefault("hunger", Attribute(name="hunger", current=100.0, decay_per_day=8.0, max_value=100.0))
        attrs.setdefault("thirst", Attribute(name="thirst", current=100.0, decay_per_day=10.0, max_value=100.0))
        attrs.setdefault("fatigue", Attribute(name="fatigue", current=100.0, decay_per_day=6.0, max_value=100.0))
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


def _format_actor_status(runtime: AgentRuntime, actor_id: str, result) -> str:
    actor = runtime.world.actor(actor_id)
    st = runtime._st(actor_id)

    hunger = actor.attrs.get("hunger").current if actor.attrs.get("hunger") else 0.0
    thirst = actor.attrs.get("thirst").current if actor.attrs.get("thirst") else 0.0
    fatigue = actor.attrs.get("fatigue").current if actor.attrs.get("fatigue") else 0.0

    code = getattr(result, "code", "") if result is not None else "INIT"
    message = getattr(result, "message", "initial state") if result is not None else "initial state"
    return (
        f"step={st.step} | actor={actor_id} | location={actor.location} | "
        f"hunger={hunger:.2f} thirst={thirst:.2f} fatigue={fatigue:.2f} | "
        f"result=[{code}] {message}"
    )


async def run_single() -> None:
    catalog = load_catalog()
    actor_ids = list(catalog.actors.keys())
    if not actor_ids:
        logging.error("actor.csv 中没有可运行角色，程序退出")
        return

    actor_id = actor_ids[0]
    logging.info("单 Agent 模式启动，固定角色：%s", actor_id)

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

    actor = actor_states[actor_id]
    agent = Agent(
        id=actor_id,
        model=LLM(model_name=MODEL_NAME),
        actor=actor,
        prompt_builder=PromptBuilder(),
    )
    runtime = AgentRuntime(
        world=world,
        agent=agent,
        executor=executor,
        config=runtime_config,
        logger=logging.getLogger(f"runtime.{actor_id}"),
    )

    while True:
        try:
            res = await runtime.tick_actor(actor_id)
            logging.info(_format_actor_status(runtime, actor_id, res))
        except Exception:
            logging.exception("single actor loop crashed: %s", actor_id)
        await asyncio.sleep(TICK_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if os.path.exists("debug_log"):
        shutil.rmtree("debug_log")
    asyncio.run(run_single())
