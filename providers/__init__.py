from config import DEFAULT_LLM_HOST, DEFAULT_MODEL, DEFAULT_PROVIDER, normalize_host
from providers.base import LLMProvider
from providers.ollama import OllamaProvider


def get_provider(
    provider: str = DEFAULT_PROVIDER,
    host: str = DEFAULT_LLM_HOST,
    model: str = DEFAULT_MODEL,
) -> LLMProvider:
    normalized_host = normalize_host(host)

    if provider == "ollama":
        return OllamaProvider(host=normalized_host, model=model)

    raise NotImplementedError(
        f"Provider '{provider}' is not implemented yet. Available: ollama"
    )
