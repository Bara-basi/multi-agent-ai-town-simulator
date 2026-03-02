from __future__ import annotations

"""Agent 单步调度器：负责 plan -> act -> execute -> reflect 的循环。"""

import asyncio
import logging,random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from actions.executor import ActionExecutor
from config.runtime_config import AgentRuntimeConfig
from model.brains.AgentBrain import Agent
from model.state.WorldState import WorldState
from model.state.actionResult import ActionResult
from model.definitions.ActorDef import ActorId

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
    world_events: List[str] = field(default_factory=list)
    actor_buffs: List[str] = field(default_factory=list)
    memory: str = field(default_factory=list)
    memory_current_plan: str = ""
    memory_previous_plans: str = ""


@dataclass
class RuntimeActorState:
    # runtime 内部的“每个 actor 私有状态”，用于控制触发节奏。
    step: int = 0
    plan_id: int = 0
    plan: Optional[str] = None
    reflect: Optional[str] = None
    last_day = 1
    last_result: Optional[ActionResult] = None
    last_plan_step: int = 0
    last_reflect_step: int = 0
    need_replan: bool = False
    last_action_sig: Optional[str] = None
    same_action_streak: int = 0
    trade_day: int = 0
    trade_side_by_item: Dict[str, str] = field(default_factory=dict)
    last_trade_sig: Optional[str] = None
    same_trade_streak: int = 0
    last_success_item_action_core: Optional[str] = None
    last_success_step: int = 0


class AgentRuntime:
    def __init__(
        self,
        *,
        world: WorldState,
        agents: Dict[ActorId, Agent],
        executor: ActionExecutor,
        config: Optional[AgentRuntimeConfig] = None,
        logger: Optional[Any] = None,
    ):
        self.world = world
        self.agents = agents
        self.executor = executor
        self.config = config or AgentRuntimeConfig()
        self.logger = logger
        self._states: Dict[Any, RuntimeActorState] = {}

    @staticmethod
    def _safe_int(v: Any, default: int = 1) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _normalize_action_signature(action: Any) -> str:
        if not isinstance(action, dict):
            return "invalid"
        action_type = str(action.get("type") or action.get("name") or "").strip()
        target = str(action.get("target") or "").strip()
        item = str(action.get("item") or action.get("item_id") or "").strip()
        qty = AgentRuntime._safe_int(action.get("qty", 1), 1)
        return f"{action_type}|{target}|{item}|{qty}"

    @staticmethod
    def _normalize_item_short(item: Any) -> str:
        s = str(item or "").strip()
        if s.startswith("item:"):
            return s.split(":", 1)[1]
        return s

    @staticmethod
    def _is_survival_danger(obs: Observation) -> bool:
        actor = obs.actor_snapshot or {}
        hunger = float(actor.get("hunger", 0.0) or 0.0)
        thirst = float(actor.get("thirst", 0.0) or 0.0)
        fatigue = float(actor.get("fatigue", 0.0) or 0.0)
        return hunger < 20.0 or thirst < 20.0 or fatigue < 15.0

    def _allow_repeat_action_for_survival(self, action: Dict[str, Any], obs: Observation) -> bool:
        if not self._is_survival_danger(obs):
            return False
        action_type = str(action.get("type") or action.get("name") or "")
        # 生存危机时允许重复恢复类动作，避免误伤必要自救。
        return action_type in {"consume", "sleep"}

    def _is_repeat_loop(self, st: RuntimeActorState, action: Any, obs: Observation) -> Tuple[bool, str]:
        if not isinstance(action, dict):
            return False, ""
        sig = self._normalize_action_signature(action)
        if sig != st.last_action_sig:
            return False, ""
        if st.same_action_streak < self.config.repeat_action_guard_threshold:
            return False, ""
        if self._allow_repeat_action_for_survival(action, obs):
            return False, ""
        msg = (
            "检测到你在连续重复完全相同的动作。"
            "请不要复读上一动作，改为执行计划中的下一步；"
            "若计划已不适用或应结束回合请输出 wait。"
        )
        return True, msg

    def _is_trade_churn(self, st: RuntimeActorState, action: Any) -> Tuple[bool, str]:
        if not isinstance(action, dict):
            return False, ""
        act_type = str(action.get("type") or action.get("name") or "").strip()
        if act_type not in {"buy", "sell"}:
            return False, ""
        item = self._normalize_item_short(action.get("item") or action.get("item_id"))
        if not item:
            return False, ""

        prev_side = st.trade_side_by_item.get(item)
        if (
            prev_side
            and prev_side != act_type
            and not self.config.allow_opposite_trade_same_item_same_day
        ):
            return True, (
                f"检测到同一回合对 `{item}` 发生买卖对冲倾向。"
                "同一物品在同一回合只能单向交易（只买或只卖）。"
                "请改为其他物品、consume、move 或 wait。"
            )

        trade_sig = f"{act_type}|{item}"
        if trade_sig == st.last_trade_sig and st.same_trade_streak >= self.config.repeat_trade_same_item_threshold:
            return True, (
                f"检测到对 `{item}` 连续重复 `{act_type}`。"
                "请停止同一交易动作的复读，改为下一步或结束本回合。"
            )
        return False, ""

    def _is_split_action(self, st: RuntimeActorState, action: Any, obs: Observation) -> Tuple[bool, str]:
        if not isinstance(action, dict):
            return False, ""
        act_type = str(action.get("type") or action.get("name") or "").strip()
        if act_type not in {"buy", "sell", "consume"}:
            return False, ""
        item = self._normalize_item_short(action.get("item") or action.get("item_id"))
        if not item:
            return False, ""

        core = f"{act_type}|{item}"
        # 仅拦截“紧邻上一步成功动作”的同类同物品拆分执行。
        if core == st.last_success_item_action_core and st.last_success_step == st.step - 1:
            # 生存危机下允许连续 consume，自救优先。
            if act_type == "consume" and self._is_survival_danger(obs):
                return False, ""
            return True, (
                f"检测到你将 `{core}` 拆成多次小动作执行。"
                "这会造成不必要的精神消耗。"
                "请合并为一次动作（提高 qty）或改为下一步。"
            )
        return False, ""

    def _update_action_streak(self, st: RuntimeActorState, proposal: Dict[str, Any], res: ActionResult) -> None:
        # 仅统计“成功执行”的动作，避免把失败重试计入循环。
        if not res.status:
            return
        sig = self._normalize_action_signature(proposal)
        if sig == st.last_action_sig:
            st.same_action_streak += 1
        else:
            st.last_action_sig = sig
            st.same_action_streak = 1

        act_type = str(proposal.get("type") or proposal.get("name") or "").strip()
        item = self._normalize_item_short(proposal.get("item") or proposal.get("item_id"))
        if act_type in {"buy", "sell", "consume"} and item:
            st.last_success_item_action_core = f"{act_type}|{item}"
        else:
            st.last_success_item_action_core = None
        st.last_success_step = st.step

    def _update_trade_state(self, st: RuntimeActorState, proposal: Dict[str, Any], res: ActionResult) -> None:
        if not res.status:
            return
        act_type = str(proposal.get("type") or proposal.get("name") or "").strip()
        if act_type not in {"buy", "sell"}:
            return
        item = self._normalize_item_short(proposal.get("item") or proposal.get("item_id"))
        if not item:
            return

        if st.trade_day != self.world.day:
            st.trade_day = self.world.day
            st.trade_side_by_item.clear()
            st.last_trade_sig = None
            st.same_trade_streak = 0

        prev_side = st.trade_side_by_item.get(item)
        if prev_side is None:
            st.trade_side_by_item[item] = act_type

        trade_sig = f"{act_type}|{item}"
        if trade_sig == st.last_trade_sig:
            st.same_trade_streak += 1
        else:
            st.last_trade_sig = trade_sig
            st.same_trade_streak = 1

    @staticmethod
    def _action_error_hint(res: ActionResult) -> str:
        msg = (res.message or "").strip()
        code = (res.code or "").strip().upper()
        if not msg:
            return "上一步动作无效，请改用其他可执行动作。"
        if "finish" in msg.lower():
            return "finish 动作已废弃。修正：继续输出可执行动作，或在需要结束回合时输出 wait。"
        if code == "TRADE_CHURN_GUARD":
            return msg + " 修正：同一物品本回合只保留买或卖一种方向。"
        if code == "SPLIT_ACTION_GUARD":
            return msg + " 修正：将同类同物品动作合并为一次，避免小步重复。"
        if "必须在" in msg:
            return f"{msg}。修正：先输出 move 到 location:market，再进行买卖。"
        if "库存" in msg and "不足" in msg:
            return f"{msg}。修正：下调 qty 到库存以内，或更换商品。"
        if ("没有足够" in msg) or ("背包" in msg and "不足" in msg):
            return f"{msg}。修正：不要继续 consume/sell 该物品，改为先买入或换动作。"
        if code in {"INVALID", "FORBIDDEN"}:
            return f"{msg}。修正：请先通过边界检查后再输出动作。"
        return msg

    async def _force_replan_after_error(self, actor_id: Any, st: RuntimeActorState, reason: str = "") -> None:
        actor = self.world.actor(actor_id)
        if hasattr(actor, "memory") and hasattr(actor.memory, "reset_today"):
            actor.memory.reset_today()

        st.need_replan = True
        st.plan = None
        st.last_action_sig = None
        st.same_action_streak = 0
        st.trade_side_by_item.clear()
        st.last_trade_sig = None
        st.same_trade_streak = 0
        st.last_success_item_action_core = None
        st.last_success_step = 0

        agent = self.agents[actor_id]
        agent.prompt_builder.error_log = reason or ""
        obs = self._obs(actor_id)
        await agent.plan(obs)
        st.plan_id += 1
        st.plan = agent.prompt_builder.plan_txt
        st.last_plan_step = st.step
        st.need_replan = False
        if hasattr(actor, "memory") and hasattr(actor.memory, "start_plan"):
            actor.memory.start_plan(plan_id=st.plan_id, plan_text=st.plan)

    def plan_text(self, actor_id: Any) -> str:
        return self.agents[actor_id].prompt_builder.plan_txt or ""

    def reflect_text(self, actor_id: Any) -> str:
        return self.agents[actor_id].prompt_builder.reflect_txt or ""
    def memory_text(self, actor_id: Any) -> str:
        return self.world.actor(actor_id).memory.observe()

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
            world_events=s["world_events"],
            actor_buffs=s["actor_buffs"],
            memory=s["memory"],
            memory_current_plan=s.get("memory_current_plan", ""),
            memory_previous_plans=s.get("memory_previous_plans", ""),
        )
    def _should_plan(self, st: RuntimeActorState) -> bool:
        # 正常情况：每回合只计划一次。只有首轮/跨天/显式重计划 才计划。
        if not st.plan:
            return True
        if st.need_replan:
            return True
        if st.last_day != self.world.day:
            st.last_day = self.world.day
            return True
        return False

    def _should_reflect(self, st: RuntimeActorState) -> bool:
        # 反思比计划更偏“总结行为结果”，触发规则类似。
        if st.last_result is None:
            return True
        if st.last_result.status is False :
            return True
        if st.last_day != self.world.day:
            return True
        return (st.step - st.last_reflect_step) >= self.config.reflect_min_interval_steps

    async def tick_actor(self, actor_id: Any) -> ActionResult:
        st = self._st(actor_id)
        agent = self.agents[actor_id]
        st.step += 1
        obs = self._obs(actor_id)
        if st.trade_day != self.world.day:
            st.trade_day = self.world.day
            st.trade_side_by_item.clear()
            st.last_trade_sig = None
            st.same_trade_streak = 0
        # 仅保留“最近失败反馈”，成功后会清空，避免长期污染提示词。
        if st.last_result is None or st.last_result.status:
            agent.prompt_builder.error_log = ""

        if self._should_plan(st):
            try:
                await agent.plan(obs)
                st.plan_id += 1
                st.plan = agent.prompt_builder.plan_txt
                st.last_plan_step = st.step
                agent.prompt_builder.error_log = ""
                actor = self.world.actor(actor_id)
                if hasattr(actor, "memory") and hasattr(actor.memory, "start_plan"):
                    actor.memory.start_plan(plan_id=st.plan_id, plan_text=st.plan)
            except Exception as e:
                logger.exception("plan failed for actor %s: %s", actor_id, e)

        proposal: Optional[Dict[str, Any]] = None
        res: Optional[ActionResult] = None
        last_err: Optional[ActionResult] = None
        max_try = self.config.max_action_retries + self.config.max_replan_after_action_error + 1
        for _ in range(max_try):
            obs = self._obs(actor_id)
            try:
                proposal = await agent.act(obs)
            except Exception as e:
                last_err = ActionResult(status=False, code="CRASH", message=f"动作生成失败: {e}")
                proposal = None
                try:
                    await self._force_replan_after_error(actor_id, st, reason=last_err.message)
                except Exception as plan_e:
                    logger.exception("replan after act-generate error failed for actor %s: %s", actor_id, plan_e)
                continue

            if proposal is None:
                last_err = ActionResult(status=False, code="NO_ACTION", message="无合法动作输出")
                try:
                    await self._force_replan_after_error(actor_id, st, reason=last_err.message)
                except Exception as plan_e:
                    logger.exception("replan after no-action failed for actor %s: %s", actor_id, plan_e)
                continue

            if str(proposal.get("type") or proposal.get("name") or "").strip() == "finish":
                last_err = ActionResult(
                    status=False,
                    code="INVALID_ACTION",
                    message="finish 动作已废弃，请改为可执行动作或 wait。",
                )
                try:
                    await self._force_replan_after_error(actor_id, st, reason=last_err.message)
                except Exception as plan_e:
                    logger.exception("replan after finish action failed for actor %s: %s", actor_id, plan_e)
                continue

            is_loop, loop_msg = self._is_repeat_loop(st, proposal, obs)
            if is_loop:
                agent.prompt_builder.error_log = loop_msg
                last_err = ActionResult(status=False, code="LOOP_GUARD", message=loop_msg)
                try:
                    await self._force_replan_after_error(actor_id, st, reason=loop_msg)
                except Exception as plan_e:
                    logger.exception("replan after loop-guard failed for actor %s: %s", actor_id, plan_e)
                continue

            trade_loop, trade_msg = self._is_trade_churn(st, proposal)
            if trade_loop:
                agent.prompt_builder.error_log = trade_msg
                last_err = ActionResult(status=False, code="TRADE_CHURN_GUARD", message=trade_msg)
                try:
                    await self._force_replan_after_error(actor_id, st, reason=trade_msg)
                except Exception as plan_e:
                    logger.exception("replan after trade-churn failed for actor %s: %s", actor_id, plan_e)
                continue

            split_loop, split_msg = self._is_split_action(st, proposal, obs)
            if split_loop:
                agent.prompt_builder.error_log = split_msg
                last_err = ActionResult(status=False, code="SPLIT_ACTION_GUARD", message=split_msg)
                try:
                    await self._force_replan_after_error(actor_id, st, reason=split_msg)
                except Exception as plan_e:
                    logger.exception("replan after split-action failed for actor %s: %s", actor_id, plan_e)
                continue

            logger.info("proposal: %s", proposal)
            try:
                res = self.executor.execute(proposal, actor_id=actor_id)
            except Exception as e:
                res = ActionResult(status=False, code="CRASH", message=f"动作执行失败: {e}")

            if res.status:
                break

            # 执行失败时，把失败原因作为下一次 act 的纠错反馈。
            agent.prompt_builder.error_log = self._action_error_hint(res)
            last_err = res
            try:
                await self._force_replan_after_error(actor_id, st, reason=agent.prompt_builder.error_log)
            except Exception as plan_e:
                logger.exception("replan after execute error failed for actor %s: %s", actor_id, plan_e)

        if res is None:
            res = last_err or ActionResult(status=False, code="NO_ACTION", message="无合法动作输出")

        actor = self.world.actor(actor_id)
        if hasattr(actor, "memory") and hasattr(actor.memory, "add_action"):
            actor.memory.add_action(
                message=res.message,
                plan_id=st.plan_id,
                status=res.status,
                code=res.code,
                finish=res.finish,
            )
        else:
            actor.memory.act_records[-1].append(res.message)
        if proposal is not None and res.status:
            self._update_action_streak(st, proposal, res)
            self._update_trade_state(st, proposal, res)
            agent.prompt_builder.error_log = ""

        st.last_result = res

        if self._should_reflect(st):
            try:
                await agent.reflect(obs)
                st.last_reflect_step = st.step
            except Exception as e:
                logger.exception("reflect failed for actor %s: %s", actor_id, e)

        return res

    async def _run_actor_loop(
        self,
        actor_id: Any,
        interval_seconds: float,
        on_tick: Optional[Callable[[Any, ActionResult], None]] = None,
    ) -> None:
        # 单角色无限 tick 循环；异常只记录日志，不中断整体仿真。
        while True:
            try:
                res = await self.tick_actor(actor_id)
                if on_tick:
                    on_tick(actor_id, res)
            except Exception:
                logger.exception("actor loop crashed: %s", actor_id)
            await asyncio.sleep(interval_seconds)

    async def run(
        self,
        *,
        interval_seconds: float,
        actor_ids: Optional[Iterable[Any]] = None,
        on_tick: Optional[Callable[[Any, ActionResult], None]] = None,
    ) -> None:
        target_ids = list(actor_ids) if actor_ids is not None else list(self.agents.keys())
        # 洗牌，避免先发优势
        random.shuffle(target_ids)
        tasks = [
            asyncio.create_task(
                self._run_actor_loop(actor_id, interval_seconds, on_tick=on_tick),
                name=f"actor-{actor_id}",
            )
            for actor_id in target_ids
        ]
        await asyncio.gather(*tasks)
