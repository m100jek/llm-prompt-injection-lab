import ollama

DEFAULT_MODEL = "llama3.2"


class OllamaClientError(Exception):
    pass


def chat(prompt: str, model: str = DEFAULT_MODEL) -> str:
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except ConnectionError as exc:
        raise OllamaClientError(
            "Cannot connect to Ollama. Start Ollama and ensure the model is pulled: "
            f"`ollama pull {model}`"
        ) from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise OllamaClientError(
                f"Model '{model}' not found. Pull it with: `ollama pull {model}`"
            ) from exc
        raise OllamaClientError(f"Ollama error: {exc}") from exc

    return response["message"]["content"]
