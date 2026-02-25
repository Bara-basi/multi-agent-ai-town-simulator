from __future__ import annotations

"""Agent 单步调度器：负责 plan -> act -> execute -> reflect 的循环。"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from actions.executor import ActionExecutor
from config.runtime_config import AgentRuntimeConfig
from model.brains.AgentBrain import Agent
from model.state.WorldState import WorldState
from model.state.actionResult import ActionResult

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    # 给 Agent 的标准观察视图，避免它直接依赖 WorldState 内部结构。
    act_id: Any
    actor_snapshot: Dict[str, Any]
    day: int
    location_snapshot: Dict[str, Any]
    catalog_snapshot: Dict[str, Any]
    working_events: List[str] = field(default_factory=list)
    memory: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RuntimeActorState:
    # runtime 内部的“每个 actor 私有状态”，用于控制触发节奏。
    step: int = 0
    plan: Optional[str] = None
    last_result: Optional[ActionResult] = None
    last_plan_step: int = 0
    last_reflect_step: int = 0


class AgentRuntime:
    def __init__(
        self,
        *,
        world: WorldState,
        agent: Agent,
        executor: ActionExecutor,
        config: Optional[AgentRuntimeConfig] = None,
        logger: Optional[Any] = None,
    ):
        self.world = world
        self.agent = agent
        self.executor = executor
        self.config = config or AgentRuntimeConfig()
        self.logger = logger
        self._states: Dict[Any, RuntimeActorState] = {}

    def _st(self, actor_id: Any) -> RuntimeActorState:
        if actor_id not in self._states:
            self._states[actor_id] = RuntimeActorState()
        return self._states[actor_id]

    def _obs(self, actor_id: Any) -> Observation:
        s = self.world.observe(actor_id)
        return Observation(
            act_id=actor_id,
            actor_snapshot=s["actor_snapshot"],
            day=s["day"],
            location_snapshot=s["location_snapshot"],
            catalog_snapshot=s["catalog_snapshot"],
            working_events=s["working_events"],
            memory=s["memory"],
        )

    def _should_plan(self, st: RuntimeActorState) -> bool:
        # 初次运行、上次 finish、或超过最小间隔时重做 plan。
        if not st.plan:
            return True
        if st.last_result and st.last_result.finish:
            return True
        return (st.step - st.last_plan_step) >= self.config.plan_min_interval_steps

    def _should_reflect(self, st: RuntimeActorState) -> bool:
        # 反思比计划更偏“总结行为结果”，触发规则类似。
        if st.last_result is None:
            return True
        if st.last_result.finish:
            return True
        return (st.step - st.last_reflect_step) >= self.config.reflect_min_interval_steps

    async def tick_actor(self, actor_id: Any) -> ActionResult:
        st = self._st(actor_id)
        st.step += 1
        obs = self._obs(actor_id)

        if self._should_plan(st):
            try:
                await self.agent.plan(obs)
                st.plan = self.agent.prompt_builder.plan_txt
                st.last_plan_step = st.step
            except Exception as e:
                logger.exception("plan failed for actor %s: %s", actor_id, e)

        proposal: Optional[Dict[str, Any]] = None
        last_err: Optional[ActionResult] = None
        # act 支持重试，避免偶发 LLM/网络错误直接打断回合。
        for _ in range(self.config.max_action_retries + 1):
            try:
                proposal = await self.agent.act(obs)
            except Exception as e:
                last_err = ActionResult(status=False, code="CRASH", message=f"动作生成失败: {e}")
                proposal = None
            if proposal is not None:
                break

        if proposal is None:
            res = last_err or ActionResult(status=False, code="NO_ACTION", message="无合法动作输出")
            st.last_result = res
            return res

        try:
            res = self.executor.execute(proposal, actor_id=actor_id)
            actor = self.world.actor(actor_id)
            if actor.memory.act_records:
                actor.memory.act_records[-1].append({"event": res.message or ""})
        except Exception as e:
            res = ActionResult(status=False, code="CRASH", message=f"动作执行失败: {e}")

        st.last_result = res

        if self._should_reflect(st):
            try:
                await self.agent.reflect(obs)
                st.last_reflect_step = st.step
            except Exception as e:
                logger.exception("reflect failed for actor %s: %s", actor_id, e)

        return res

    async def run_tick(self, *, dt: float = 1.0) -> None:
        _ = dt
        # status=True 的 actor 参与本轮决策；无人可行动时推进 day。
        actor_ids = [aid for aid, actor in self.world.actors.items() if actor.status]
        if len(actor_ids) == 0:
            self.world.update_day()
        await asyncio.gather(*(self.tick_actor(aid) for aid in actor_ids))
