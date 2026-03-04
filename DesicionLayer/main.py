"""程序入口：组装世界状态、动作执行器，并启动单一 runtime 管理全部 Agent 循环。"""

import asyncio
import logging
import os
import shutil
import threading
from datetime import datetime
from typing import Dict
from actions.executor import ActionExecutor
from config.runtime_config import AgentRuntimeConfig
from model.brains.AgentBrain import Agent
from model.brains.PromptBuilder import PromptBuilder
from model.definitions.ActorDef import ActorId
from model.definitions.Inventory import Inventory
from model.definitions.OpenAIModel import LLM
from model.state.ActorState import Attribute
from model.state.WorldState import WorldState
from model.brains.WebSocketServer import WebSocketServer
from model.brains.NoopActionLayerClient import NoopActionLayerClient
from runtime.build_state import build_state
from runtime.load_data import load_catalog
from runtime.runtime import AgentRuntime
import logging
from config.config import HUNGER_DECAY_PER_DAY,THIRST_DECAY_PER_DAY,FATIGUE_DECAY_PER_DAY,USE_ACION_LAYER

MODEL_NAME = "gpt-4.1-mini-2025-04-14"
TICK_INTERVAL_SECONDS = 1.0
logger = logging.getLogger(__name__)

def _dispatch(_event_name: str, **_payload: object) -> None:
    # 事件分发预留点：当前版本未接入总线，仅保持接口形状。
    return None


def _format_inventory_text(actor) -> str:
    # 监控面板展示用：兼容 Inventory/dict/list 等多种历史结构。
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
        text = str(snap())
        return text if text else "empty"
    return str(inv)


def _build_monitor_payload(world: WorldState, runtime: AgentRuntime, actor_id: ActorId, result) -> Dict[str, object]:
    # 将运行时内部状态整理成 UI 可直接渲染的扁平结构。
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
        attrs.setdefault("hunger", Attribute(name="饱食度", current=50.0, decay_per_day=HUNGER_DECAY_PER_DAY, max_value=100.0))
        attrs.setdefault("thirst", Attribute(name="水分值", current=50.0, decay_per_day=THIRST_DECAY_PER_DAY, max_value=100.0))
        attrs.setdefault("fatigue", Attribute(name="精神值", current=50.0, decay_per_day=FATIGUE_DECAY_PER_DAY, max_value=100.0))
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
    # 1) 读静态定义 2) 构建动态状态 3) 启动单一 runtime 管理全部 actor。

    catalog = load_catalog()
    actor_states, location_states = build_state(catalog)
    actor2agent = {actor_id:f"agent-{i}" for i,actor_id in enumerate(catalog.actors.keys(),start=1)}
    if USE_ACION_LAYER:
        client = WebSocketServer(actor2agent=actor2agent)
        await client.start()
        while not all(client.is_connected(k) for k in actor2agent.values()):
            print(client.connections.keys())
            print(actor2agent.values())
            await asyncio.sleep(1)
        logger.info("全部客户端已连接")
    else:
        client = NoopActionLayerClient()
        logger.info("USE_ACION_LAYER=False，已禁用 Unity 执行层。")
    
    world = WorldState(
        catalog=catalog,
        actors=actor_states,
        locations=location_states,
        client=client,
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

    agents: Dict[ActorId, Agent] = {}
    for actor_id, actor in actor_states.items():
        agents[actor_id] = Agent(
            id=actor_id,
            model=LLM(model_name=MODEL_NAME),
            actor=actor,
            prompt_builder=PromptBuilder(),
        )
    runtime = AgentRuntime(
        world=world,
        agents=agents,
        executor=executor,
        config=runtime_config,
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
    if os.path.exists("debug_log"):
        shutil.rmtree("debug_log")
    
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
            # 仿真逻辑跑在后台线程，避免阻塞 Qt UI 事件循环。
            def _target():
                asyncio.run(run(on_update=push_update))

            threading.Thread(target=_target, name="simulation-thread", daemon=True).start()

        run_monitor(_start_simulation, actor_ids=actor_ids, actor_name_map=actor_name_map)
