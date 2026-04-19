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
        return self._normalize_action_output(action)

    async def reflect(self, obs: Any) -> None:
        prompt = self.prompt_builder.build_reflect(obs)
        reflect = await self.model.agenerate(model=REFLECT_MODEL_NAME, prompt=prompt, resoning="minimal")
        self.prompt_builder.reflect_txt = reflect

    async def make_desicion(self, obs: Any) -> List[Dict]:
        prompt = self.prompt_builder.decision_point_prompt(obs)
        decision = await self.model.agenerate(
            model=PLAN_MODEL_NAME,
            prompt=prompt,
            restrict="json",
            resoning="low",
        )
        if isinstance(decision, list):
            return [d for d in decision if isinstance(d, dict)]
        if isinstance(decision, dict):
            return [decision]
        return [{"decision": "skip", "item": None, "reason": "invalid_json_fallback"}]

    @staticmethod
    def _normalize_action_output(raw: Any) -> Dict:
        # 1) 允许模型返回 {"action": {...}} / {"actions":[...]} / [{...}]
        payload: Dict[str, Any]
        if isinstance(raw, list):
            payload = raw[0] if raw and isinstance(raw[0], dict) else {}
        elif isinstance(raw, dict):
            if isinstance(raw.get("action"), dict):
                payload = dict(raw.get("action") or {})
            elif isinstance(raw.get("actions"), list) and raw.get("actions"):
                head = raw.get("actions")[0]
                payload = head if isinstance(head, dict) else {}
            else:
                payload = dict(raw)
        else:
            payload = {}

        # 2) 兼容常见字段名
        action_type = (
            payload.get("type")
            or payload.get("name")
            or payload.get("action")
            or payload.get("command")
            or ""
        )
        action_type = str(action_type).strip().lower()

        # 3) 常见同义映射，避免被判 INVALID_ACTION
        alias = {
            "end_turn": "wait",
            "end_round": "wait",
            "finish_round": "wait",
            "finish": "wait",
            "rest": "sleep",
            "use": "consume",
            "drink": "consume",
            "eat": "consume",
            "go": "move",
            "walk": "move",
        }
        action_type = alias.get(action_type, action_type)

        normalized: Dict[str, Any] = {"type": action_type or "wait"}

        # 4) 透传常用参数
        if "target" in payload:
            normalized["target"] = payload.get("target")
        if "item" in payload:
            normalized["item"] = payload.get("item")
        elif "item_id" in payload:
            normalized["item"] = payload.get("item_id")
        if "qty" in payload:
            normalized["qty"] = payload.get("qty")
        elif "quantity" in payload:
            normalized["qty"] = payload.get("quantity")

        # 5) 动作兜底
        if normalized["type"] in {"", "none", "null"}:
            normalized["type"] = "wait"

        # 6) 参数清洗：target/item/qty
        target = str(normalized.get("target") or "").strip()
        if target:
            t = target.lower()
            if t in {"market", "shop", "store", "location_market"}:
                normalized["target"] = "location:market"
            elif t in {"home", "house", "location_home"}:
                normalized["target"] = "location:home"

        item = normalized.get("item")
        if isinstance(item, dict):
            item = item.get("id") or item.get("item") or item.get("name")
        if item is not None:
            normalized["item"] = str(item).strip()

        if "qty" in normalized:
            try:
                q = int(normalized.get("qty") or 1)
            except Exception:
                q = 1
            normalized["qty"] = max(1, q)
        return normalized
