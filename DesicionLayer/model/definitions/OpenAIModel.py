from __future__ import annotations

import os
import logging
from typing import Any, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency at import time
    OpenAI = None


class LLM:
    def __init__(
        self,
        model_name: str = "gpt-4.1-mini-2025-04-14",
        api_key: Optional[str] = None,
    ):
        self._logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None

        if OpenAI is not None and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self._logger.warning(
                "LLM fallback mode enabled (openai package or OPENAI_API_KEY is missing)."
            )

    def _fallback_generate(self, restrict: Optional[str] = None) -> Any:
        if restrict == "json":
            return {"type": "wait"}
        return "fallback response"

    def generate(self, prompt: str, restrict: Optional[str] = None) -> Any:
        if self.client is None:
            return self._fallback_generate(restrict=restrict)

        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        if restrict == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        if restrict == "json":
            import json

            return json.loads(content)
        return content
