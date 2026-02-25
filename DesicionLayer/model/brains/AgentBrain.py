from dataclasses import dataclass
from typing import List, Tuple, Dict,Any
from model.state.ActorState import ActorState,ActorId
from model.brains.PromptBuilder import PromptBuilder
from model.definitions.OpenAIModel import LLM

@dataclass
class Agent:
    # Agent 只负责“调用模型”，具体 prompt 结构由 PromptBuilder 提供。
    id: ActorId 
    model: LLM
    actor: ActorState
    prompt_builder:PromptBuilder

    async def plan(self, obs:Any) -> None:
        # 生成阶段性计划文本（不直接执行动作）。
        prompt = self.prompt_builder.build_plan(obs)
        plan = await self.model.agenerate(prompt)
        self.prompt_builder.plan_txt = plan

    async def act(self, obs:Any) ->Dict|List:
        # 生成结构化动作，restrict=json 会触发 JSON 反序列化路径。
        prompt = self.prompt_builder.build_act(obs)
        action = await self.model.agenerate(prompt,restrict="json")
        return action

    async def reflect(self, obs:Any) -> None:
        # 生成总结/反思文本，供下一轮计划参考。
        prompt = self.prompt_builder.build_reflect(obs)
        reflect = await self.model.agenerate(prompt)
        self.prompt_builder.reflect_txt = reflect


