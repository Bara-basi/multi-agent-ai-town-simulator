from __future__ import annotations

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
    act_id: Any
    actor_snapshot: Dict[str, Any]
    day: int
    location_snapshot: Dict[str, Any]
    catalog_snapshot: Dict[str, Any]
    working_events: List[str] = field(default_factory=list)


@dataclass
class RuntimeActorState:
    step: int = 0
    plan: Optional[str] = None
    last_result: Optional[ActionResult] = None
    last_plan_step: int = 0
    last_reflect_step: int = 0


class AgentRuntime:
    def __init__(
        self,
        *,
        world: WorldState,  # 世界状态对象，包含整个环境的当前状态
        agent: Agent,       # 智能体对象，负责决策和规划
        executor: ActionExecutor,
        config: Optional[AgentRuntimeConfig] = None,
        logger: Optional[Any] = None,
    ):
        self.world = world
        self.agent = agent
        self.executor = executor
        self.config = config or AgentRuntimeConfig()
        self.logger = logger
        self._states: Dict[int, RuntimeActorState] = {}

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
        )

    def _should_plan(self, st: RuntimeActorState) -> bool:
        if not st.plan:
            return True
        if st.last_result and st.last_result.finish:
            return True
        return (st.step - st.last_plan_step) >= self.config.plan_min_interval_steps

    def _should_reflect(self, st: RuntimeActorState) -> bool:
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
                self.agent.plan(obs)
                st.plan = self.agent.prompt_builder.plan_txt
                st.last_plan_step = st.step
            except Exception as e:
                logger.exception("plan failed for actor %s: %s", actor_id, e)

        proposal: Optional[Dict[str, Any]] = None
        last_err: Optional[ActionResult] = None
        for _ in range(self.config.max_action_retries + 1):
            try:
                proposal = self.agent.act(obs)
            except Exception as e:
                last_err = ActionResult(status=False, code="CRASH", message=f"act failed: {e}")
                proposal = None
            if proposal is not None:
                break
        
        if proposal is None:
            res = last_err or ActionResult(status=False, code="NO_ACTION", message="No valid action")
            st.last_result = res
            return res
    
        try:
            res = self.executor.execute(proposal, actor_id=actor_id)
        except Exception as e:
            res = ActionResult(status=False, code="CRASH", message=f"execute failed: {e}")
        st.last_result = res
        
        if self._should_reflect(st):
            try:
                self.agent.reflect(obs)
                st.last_reflect_step = st.step
            except Exception as e:
                logger.exception("reflect failed for actor %s: %s", actor_id, e)

        return res

    async def run_tick(self, *, dt: float = 1.0) -> None:
        _ = dt
        actor_ids = list(self.world.actors.keys())
        await asyncio.gather(*(self.tick_actor(aid) for aid in actor_ids))
