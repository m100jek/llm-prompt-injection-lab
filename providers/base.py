from typing import Protocol


class LLMProvider(Protocol):
    def chat(self, prompt: str, system_prompt: str | None = None) -> str: ...
