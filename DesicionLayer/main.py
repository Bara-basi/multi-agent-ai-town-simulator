"""程序入口：组装世界状态、动作执行器和每个 Agent 的 runtime 循环。"""

import asyncio
import logging
import os
import shutil
import threading
from datetime import datetime
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
        "location": str(actor.location),
        "step": st.step,
        "hunger": round(float(hunger), 2),
        "thirst": round(float(thirst), 2),
        "fatigue": round(float(fatigue), 2),
        "inventory_text": _format_inventory_text(actor),
        "plan": runtime.agent.prompt_builder.plan_txt or "",
        "action": action_txt,
        "history_entry": history_entry,
        "reflect": runtime.agent.prompt_builder.reflect_txt or "",
        "memory": "",
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


async def _run_actor_loop(actor_id: ActorId, runtime: AgentRuntime, interval_seconds: float, on_update=None) -> None:
    # 单角色无限 tick 循环；异常只记录日志，不中断整体仿真。
    while True:
        try:
            res = await runtime.tick_actor(actor_id)
            if on_update:
                payload = _build_monitor_payload(runtime.world, runtime, actor_id, res)
                on_update(payload)
        except Exception:
            logging.exception("actor loop crashed: %s", actor_id)
        await asyncio.sleep(interval_seconds)


async def run(on_update=None) -> None:
    # 1) 读静态定义 2) 构建动态状态 3) 启动每个 actor 的 runtime。
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

    if on_update:
        for actor_id, runtime in runtimes.items():
            on_update(_build_monitor_payload(world, runtime, actor_id, result=None))

    tasks = [
        asyncio.create_task(
            _run_actor_loop(actor_id, runtime, TICK_INTERVAL_SECONDS, on_update=on_update),
            name=f"actor-{actor_id}",
        )
        for actor_id, runtime in runtimes.items()
    ]
    await asyncio.gather(*tasks)


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
        actor_ids = list(load_catalog().actors.keys())

        def _start_simulation(push_update):
            # 仿真逻辑跑在后台线程，避免阻塞 Qt UI 事件循环。
            def _target():
                asyncio.run(run(on_update=push_update))

            threading.Thread(target=_target, name="simulation-thread", daemon=True).start()

        run_monitor(_start_simulation, actor_ids=actor_ids)
