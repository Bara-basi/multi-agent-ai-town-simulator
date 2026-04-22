"""Program entry: build world state, action executor and start runtime."""

import asyncio
import logging
import os
import shutil
import threading
from datetime import datetime
from typing import Dict

from actions.executor import ActionExecutor
from config.config import (
    ACT_MODEL_NAME,
    ACTION_LAYER_CONNECT_POLL_SECONDS,
    FATIGUE_DECAY_PER_DAY,
    HUNGER_DECAY_PER_DAY,
    THIRST_DECAY_PER_DAY,
    TICK_INTERVAL_SECONDS,
    USE_ACION_LAYER,
)
from model.brains.AgentBrain import Agent
from model.brains.NoopActionLayerClient import NoopActionLayerClient
from model.brains.PromptBuilder import PromptBuilder
from model.brains.WebSocketServer import WebSocketServer
from model.definitions.ActorDef import ActorId
from model.definitions.Inventory import Inventory
from model.definitions.OpenAIModel import LLM
from model.state.ActorState import Attribute
from model.state.WorldState import WorldState
from runtime.build_state import build_state
from runtime.load_data import HUMAN_SHOP_ASSISTANT_ACTOR_ID, load_catalog
from runtime.runtime import AgentRuntime

logger = logging.getLogger(__name__)


def _delete_dir_safely(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        logger.exception("Failed to delete directory: %s", path)


def _cleanup_debug_log_on_start(path: str = "debug_log") -> None:
    mode = str(os.getenv("DEBUG_LOG_CLEANUP_MODE", "async") or "async").strip().lower()
    if not os.path.exists(path):
        return
    if mode == "off":
        logger.info("Skip debug log cleanup (DEBUG_LOG_CLEANUP_MODE=off)")
        return
    if mode == "sync":
        _delete_dir_safely(path)
        return

    # Default: async cleanup to avoid startup blocking on large log trees.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived = f"{path}_old_{ts}"
    try:
        os.replace(path, archived)
    except Exception:
        logger.exception("Archive debug log failed, fallback to sync delete")
        _delete_dir_safely(path)
        return

    t = threading.Thread(
        target=_delete_dir_safely,
        args=(archived,),
        name="debug-log-cleanup",
        daemon=True,
    )
    t.start()


def _dispatch(_event_name: str, **_payload: object) -> None:
    return None


def _format_inventory_text(actor) -> str:
    inv = getattr(actor, "inventory", None)
    if inv is None:
        return ""
    qty = getattr(inv, "qty", None)
    if isinstance(qty, dict):
        if not qty:
            return "empty"
        return "\n".join(f"{k}: {v}" for k, v in sorted(qty.items()))
    snap = getattr(inv, "snapshot", None)
    if callable(snap):
        try:
            text = str(snap())
        except TypeError:
            text = str(inv)
        return text if text else "empty"
    return str(inv)


def _build_monitor_payload(world: WorldState, runtime: AgentRuntime, actor_id: ActorId, result) -> Dict[str, object]:
    actor = world.actor(actor_id)
    st = runtime._st(actor_id)
    try:
        actor_name = str(world.catalog.actor(actor_id).name)
    except Exception:
        actor_name = str(actor_id)

    hunger = actor.attrs.get("hunger").current if actor.attrs.get("hunger") else 0.0
    thirst = actor.attrs.get("thirst").current if actor.attrs.get("thirst") else 0.0
    fatigue = actor.attrs.get("fatigue").current if actor.attrs.get("fatigue") else 0.0

    action_txt = "[INIT] initial state"
    if result is not None:
        action_txt = f"[{getattr(result, 'code', '')}] {getattr(result, 'message', '')}".strip()

    ts = datetime.now().strftime("%H:%M:%S")
    history_entry = f"{ts} | step={st.step} | day={world.day} | {action_txt}"

    return {
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "location": str(actor.location),
        "money": round(float(getattr(actor, "money", 0.0) or 0.0), 2),
        "step": st.step,
        "hunger": round(float(hunger), 2),
        "thirst": round(float(thirst), 2),
        "fatigue": round(float(fatigue), 2),
        "inventory_text": _format_inventory_text(actor),
        "plan": runtime.plan_text(actor_id),
        "action": action_txt,
        "history_entry": history_entry,
        "reflect": runtime.reflect_text(actor_id),
        "memory": runtime.memory_text(actor_id),
    }


def _bootstrap_world_state(world: WorldState) -> None:
    for actor in world.actors.values():
        if actor.id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
            # Human shop assistant actor is intentionally minimal at this stage.
            continue
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
        attrs.setdefault(
            "hunger",
            Attribute(name="hunger", current=50.0, decay_per_day=HUNGER_DECAY_PER_DAY, max_value=100.0),
        )
        attrs.setdefault(
            "thirst",
            Attribute(name="thirst", current=50.0, decay_per_day=THIRST_DECAY_PER_DAY, max_value=100.0),
        )
        attrs.setdefault(
            "fatigue",
            Attribute(name="fatigue", current=50.0, decay_per_day=FATIGUE_DECAY_PER_DAY, max_value=100.0),
        )
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


async def run(on_update=None) -> None:
    catalog = load_catalog()
    actor_states, location_states = build_state(catalog)
    actor2agent: Dict[ActorId, str] = {}
    ai_index = 1
    for actor_id in catalog.actors.keys():
        if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
            actor2agent[actor_id] = "Agent-X"
            continue
        actor2agent[actor_id] = f"Agent-{ai_index}"
        ai_index += 1

    if USE_ACION_LAYER:
        client = WebSocketServer(actor2agent=actor2agent)
        await client.start()
        while not all(client.is_connected(k) for k in actor2agent.values()):
            await asyncio.sleep(ACTION_LAYER_CONNECT_POLL_SECONDS)
        logger.info("All action-layer clients connected")
    else:
        client = NoopActionLayerClient()
        logger.info("USE_ACION_LAYER=False, Unity action layer disabled")

    world = WorldState(
        catalog=catalog,
        actors=actor_states,
        locations=location_states,
        client=client,
    )
    _bootstrap_world_state(world)

    executor = ActionExecutor(
        world=world,
        dispatch=_dispatch,
        catalog=catalog,
        logger=logging.getLogger("action"),
    )

    agents: Dict[ActorId, Agent] = {}
    for actor_id, actor in actor_states.items():
        if actor_id == HUMAN_SHOP_ASSISTANT_ACTOR_ID:
            continue
        agents[actor_id] = Agent(
            id=actor_id,
            model=LLM(model_name=ACT_MODEL_NAME),
            actor=actor,
            prompt_builder=PromptBuilder(),
        )

    runtime = AgentRuntime(
        world=world,
        agents=agents,
        executor=executor,
        logger=logging.getLogger("runtime"),
    )

    if on_update:
        for actor_id in agents.keys():
            on_update(_build_monitor_payload(world, runtime, actor_id, result=None))

    def _on_tick(actor_id: ActorId, result) -> None:
        if on_update:
            on_update(_build_monitor_payload(world, runtime, actor_id, result))

    await runtime.run(
        interval_seconds=TICK_INTERVAL_SECONDS,
        actor_ids=agents.keys(),
        on_tick=_on_tick,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _cleanup_debug_log_on_start("debug_log")

    enable_monitor = str(os.getenv("ENABLE_MONITOR_UI", "1") or "1").strip().lower() not in {"0", "false", "off"}
    if not enable_monitor:
        logging.info("ENABLE_MONITOR_UI=0, run in CLI mode.")
        asyncio.run(run())
    else:
        try:
            from monitor import run_monitor
        except Exception as e:
            logging.warning("PyQt monitor unavailable, fallback to CLI mode: %s", e)
            asyncio.run(run())
        else:
            catalog = load_catalog()
            actor_ids = list(catalog.actors.keys())
            actor_name_map = {str(actor_id): str(actor_def.name) for actor_id, actor_def in catalog.actors.items()}

            def _start_simulation(push_update):
                def _target():
                    asyncio.run(run(on_update=push_update))

                threading.Thread(target=_target, name="simulation-thread", daemon=True).start()

            run_monitor(_start_simulation, actor_ids=actor_ids, actor_name_map=actor_name_map)
