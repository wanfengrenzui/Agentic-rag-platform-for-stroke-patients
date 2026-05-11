from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from src.config import Settings


class DeepSeekConfigError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    @property
    def client(self) -> OpenAI:
        if not self.settings.deepseek_api_key:
            raise DeepSeekConfigError("DEEPSEEK_API_KEY is not configured.")
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.deepseek_api_key, base_url=self.settings.deepseek_base_url)
        return self._client

    def chat_text(self, system: str, user: str, temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def chat_json(self, system: str, user: str, temperature: float = 0.1) -> dict[str, Any]:
        text = self.chat_text(system, user, temperature=temperature)
        return self._parse_json_object(text)

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end >= start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)
