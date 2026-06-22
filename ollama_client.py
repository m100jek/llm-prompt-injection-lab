from config import DEFAULT_LLM_HOST, DEFAULT_MODEL
from providers.ollama import OllamaClientError, OllamaProvider


def chat(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: str | None = None,
    host: str = DEFAULT_LLM_HOST,
) -> str:
    provider = OllamaProvider(host=host, model=model)
    return provider.chat(prompt, system_prompt=system_prompt)
