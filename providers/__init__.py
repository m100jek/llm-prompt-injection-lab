from config import (
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_LLM_HOST,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
)
from providers.base import LLMProvider


def get_provider(
    provider: str = DEFAULT_PROVIDER,
    host: str = DEFAULT_LLM_HOST,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
) -> LLMProvider:
    if provider == "ollama":
        from providers.ollama import OllamaProvider

        return OllamaProvider(host=host, model=model)

    if provider in {"openai-compatible", "openai_compatible"}:
        from providers.openai_compatible import OpenAICompatibleProvider

        if host.strip() in {"", DEFAULT_LLM_HOST, "http://127.0.0.1:11434"}:
            raise ValueError(
                "For --provider openai-compatible, set --host to the exact "
                "HTTP API endpoint URL to POST chat requests to"
            )

        return OpenAICompatibleProvider(
            host=host,
            model=model,
            api_key=api_key,
            extra_headers=extra_headers,
            timeout=timeout,
        )

    raise NotImplementedError(
        f"Provider '{provider}' is not implemented yet. "
        "Available: ollama, openai-compatible"
    )
