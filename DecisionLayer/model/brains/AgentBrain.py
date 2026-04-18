from dataclasses import dataclass
from typing import Any, Dict, List

from config.config import ACT_MODEL_NAME, PLAN_MODEL_NAME, REFLECT_MODEL_NAME
from model.brains.PromptBuilder import PromptBuilder
from model.definitions.OpenAIModel import LLM
from model.state.ActorState import ActorId, ActorState


@dataclass
class Agent:
    id: ActorId
    model: LLM
    actor: ActorState
    prompt_builder: PromptBuilder

    async def plan(self, obs: Any) -> None:
        prompt = self.prompt_builder.build_plan(obs)
        plan = await self.model.agenerate(model=PLAN_MODEL_NAME, prompt=prompt, resoning="low")
        self.prompt_builder.plan_txt = plan

    async def act(self, obs: Any) -> Dict | List:
        prompt = self.prompt_builder.build_act(obs)
        action = await self.model.agenerate(
            model=ACT_MODEL_NAME,
            prompt=prompt,
            restrict="json",
            resoning="minimal",
        )
        return action

    async def reflect(self, obs: Any) -> None:
        prompt = self.prompt_builder.build_reflect(obs)
        reflect = await self.model.agenerate(model=REFLECT_MODEL_NAME, prompt=prompt, resoning="minimal")
        self.prompt_builder.reflect_txt = reflect

    async def make_desicion(self, obs: Any) -> Dict:
        prompt = self.prompt_builder.decision_point_prompt(obs)
        decision = await self.model.agenerate(
            model=PLAN_MODEL_NAME,
            prompt=prompt,
            restrict="json",
            resoning="low",
        )
        if isinstance(decision, dict):
            return decision
        return {"decision": "skip", "item": None, "reason": "invalid_json_fallback"}
