from __future__ import annotations

import os
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
        if OpenAI is None:
            raise ImportError("openai package is not installed")
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt: str, restrict: Optional[str] = None) -> Any:
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

