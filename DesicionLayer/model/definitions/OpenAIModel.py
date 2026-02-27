from __future__ import annotations

"""OpenAI Chat Completions 的轻封装，含无密钥回退模式。
- 对 gpt-5*：使用 Responses API 来支持 reasoning.effort=minimal
- 其它模型：保持使用 Chat Completions API
"""

import os
import logging
from typing import Any, Optional


try:
    from openai import OpenAI, AsyncOpenAI
except Exception: 
    OpenAI = None
    AsyncOpenAI = None


class LLM:
    def __init__(
        self,
        model_name: str = "gpt-5-mini-2025-08-07",
        api_key: Optional[str] = None,
        reasoning_effort: str = "minimal",  # gpt-5-mini 支持 minimal/low/medium/high（你已验证 none 不支持）
    ):
        self._logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.reasoning_effort = reasoning_effort
        self.client = None
        self.async_client = None

        if OpenAI is not None and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            if AsyncOpenAI is not None:
                self.async_client = AsyncOpenAI(api_key=self.api_key)
        else:
            self._logger.warning(
                "LLM fallback mode enabled (openai package or OPENAI_API_KEY is missing)."
            )

    def _fallback_generate(self, restrict: Optional[str] = None) -> Any:
        if restrict == "json":
            return {"type": "wait"}
        return "fallback response"

    @staticmethod
    def _is_gpt5(model: str) -> bool:
        return bool(model) and model.startswith("gpt-5")

    def generate(self, prompt: str, restrict: Optional[str] = None) -> Any:
        if self.client is None:
            return self._fallback_generate(restrict=restrict)

        model = self.model_name

        # —— gpt-5*：用 Responses API（reasoning 参数在这里是官方支持的）——
        if self._is_gpt5(model) and hasattr(self.client, "responses"):
            kwargs = {
                "model": model,
                "input": [{"role": "user", "content": prompt}],
                "reasoning": {"effort": self.reasoning_effort},
            }
            if restrict == "json":
                # Responses API 的 JSON mode：通过 text.format 请求 JSON object
                kwargs["text"] = {"format": {"type": "json_object"}}

            resp = self.client.responses.create(**kwargs)
            content = getattr(resp, "output_text", None) or ""
            if restrict == "json":
                import json
                return json.loads(content)
            return content

        # —— 其它模型：保持 Chat Completions（不传 reasoning，避免你的 TypeError）——
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if restrict == "json":
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content

        if restrict == "json":
            import json
            return json.loads(content)
        return content

    async def agenerate(self, model: str, prompt: str, restrict: Optional[str] = None) -> Any:
        if self.async_client is None:
            return self.generate(prompt, restrict=restrict)

        use_model = model if model else self.model_name

        # —— gpt-5*：用 Async Responses API —— 
        if self._is_gpt5(use_model) and hasattr(self.async_client, "responses"):
            kwargs = {
                "model": use_model,
                "input": [{"role": "user", "content": prompt}],
                "reasoning": {"effort": self.reasoning_effort},
            }
            if restrict == "json":
                kwargs["text"] = {"format": {"type": "json_object"}}

            resp = await self.async_client.responses.create(**kwargs)
            content = getattr(resp, "output_text", None) or ""
            if restrict == "json":
                import json
                return json.loads(content)
            return content

        # —— 其它模型：Async Chat Completions —— 
        kwargs = {
            "model": use_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if restrict == "json":
            kwargs["response_format"] = {"type": "json_object"}

        resp = await self.async_client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content

        if restrict == "json":
            import json
            return json.loads(content)
        return content