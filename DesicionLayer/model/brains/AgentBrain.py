from dataclasses import dataclass
from typing import List, Tuple, Dict,Any
from model.state.ActorState import ActorState,ActorId
from model.brains.PromptBuilder import PromptBuilder
from model.definitions.OpenAIModel import LLM

@dataclass
class Agent:
    id: ActorId 
    model: LLM
    actor: ActorState
    prompt_builder:PromptBuilder

    def plan(self, obs:Any) -> None:
        prompt = self.prompt_builder.build_plan(obs)
        plan = self.model.generate(prompt)
        self.prompt_builder.plan_txt = plan

    def act(self, obs:Any) ->Dict|List:
        prompt = self.prompt_builder.build_act(obs)
        action = self.model.generate(prompt,restrict="json")
        return action

    def reflect(self, obs:Any) -> None:
        prompt = self.prompt_builder.build_reflect(obs)
        reflect = self.model.generate(prompt)
        self.prompt_builder.reflect_txt = reflect


