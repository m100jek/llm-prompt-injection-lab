import ollama
from ollama import Client

from config import DEFAULT_LLM_HOST, DEFAULT_MODEL, normalize_host


class OllamaClientError(Exception):
    pass


class OllamaProvider:
    def __init__(self, host: str = DEFAULT_LLM_HOST, model: str = DEFAULT_MODEL):
        self.host = normalize_host(host)
        self.model = model
        self._client = Client(host=self.host)

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat(model=self.model, messages=messages)
        except ConnectionError as exc:
            raise OllamaClientError(
                f"Cannot connect to Ollama at {self.host}. Start Ollama and ensure "
                f"the model is pulled: `ollama pull {self.model}`"
            ) from exc
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise OllamaClientError(
                    f"Model '{self.model}' not found. Pull it with: `ollama pull {self.model}`"
                ) from exc
            raise OllamaClientError(f"Ollama error: {exc}") from exc

        return response["message"]["content"]
