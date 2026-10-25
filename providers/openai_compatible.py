import json
from typing import Any
from urllib.parse import urlparse

import httpx

from config import DEFAULT_HTTP_TIMEOUT, DEFAULT_MODEL
from providers.errors import ProviderError


def validate_api_endpoint_url(url: str) -> str:
    """Validate and return the endpoint URL without rewriting its path."""
    url = url.strip()
    if not url:
        raise ProviderError("OpenAI-compatible host URL must not be empty")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ProviderError(
            "OpenAI-compatible host must be an http:// or https:// URL"
        )
    if not parsed.netloc:
        raise ProviderError(
            "OpenAI-compatible host must include a valid host name"
        )

    # Keep the user-provided path as-is; only trim a trailing slash.
    return url.rstrip("/")


# Backward-compatible alias.
normalize_chat_completions_url = validate_api_endpoint_url


def parse_extra_headers(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            "LLM_EXTRA_HEADERS must be a JSON object of string headers"
        ) from exc

    if not isinstance(data, dict):
        raise ProviderError(
            "LLM_EXTRA_HEADERS must be a JSON object of string headers"
        )

    headers: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ProviderError(
                "LLM_EXTRA_HEADERS must be a JSON object of string headers"
            )
        headers[key] = value
    return headers


class OpenAICompatibleProvider:
    def __init__(
        self,
        host: str,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        client: httpx.Client | None = None,
    ):
        self.host = validate_api_endpoint_url(host)
        self.model = model
        self._api_key = api_key
        self._extra_headers = dict(extra_headers or {})
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            verify=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenAICompatibleProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages}

        try:
            response = self._client.post(
                self.host,
                headers=self._build_headers(),
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Request to OpenAI-compatible endpoint timed out: {self.host}"
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Cannot connect to OpenAI-compatible endpoint: {self.host}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"HTTP client error talking to OpenAI-compatible endpoint: {self.host}"
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderError(
                f"OpenAI-compatible endpoint returned HTTP {response.status_code}"
            )

        try:
            data: Any = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "OpenAI-compatible endpoint returned invalid JSON"
            ) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "OpenAI-compatible response missing choices[0].message.content"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise ProviderError(
                "OpenAI-compatible response content must be a non-empty string"
            )

        return content
