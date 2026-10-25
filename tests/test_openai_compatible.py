import json
import tempfile
import unittest
from pathlib import Path

import httpx

from attack_runner import run_attacks
from history.db import get_experiment
from providers import get_provider
from providers.errors import ProviderError
from providers.openai_compatible import (
    OpenAICompatibleProvider,
    parse_extra_headers,
    validate_api_endpoint_url,
)


class UrlValidationTests(unittest.TestCase):
    def test_keeps_arbitrary_path(self) -> None:
        url = "https://gateway.corp/llm"
        self.assertEqual(validate_api_endpoint_url(url), url)

    def test_keeps_openai_style_path(self) -> None:
        url = "https://api.example.com/v1/chat/completions"
        self.assertEqual(validate_api_endpoint_url(url), url)

    def test_trims_trailing_slash_only(self) -> None:
        self.assertEqual(
            validate_api_endpoint_url("https://api.example.com/custom/path/"),
            "https://api.example.com/custom/path",
        )

    def test_does_not_append_chat_completions(self) -> None:
        self.assertEqual(
            validate_api_endpoint_url("https://api.example.com/v1"),
            "https://api.example.com/v1",
        )

    def test_rejects_non_http(self) -> None:
        with self.assertRaises(ProviderError):
            validate_api_endpoint_url("ftp://api.example.com/v1")


class OpenAICompatibleProviderTests(unittest.TestCase):
    def _provider(
        self,
        handler,
        host: str = "https://gateway.corp/llm",
        api_key: str | None = "secret-key",
        extra_headers: dict[str, str] | None = None,
    ) -> OpenAICompatibleProvider:
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, follow_redirects=False)
        return OpenAICompatibleProvider(
            host=host,
            model="my-model",
            api_key=api_key,
            extra_headers=extra_headers,
            client=client,
        )

    def test_request_construction_and_response_parsing(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Hello there"}}
                    ]
                },
            )

        provider = self._provider(handler, extra_headers={"X-Test": "1"})
        text = provider.chat("Hi", system_prompt="Be helpful")
        self.assertEqual(text, "Hello there")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://gateway.corp/llm")
        self.assertEqual(captured["body"]["model"], "my-model")
        self.assertEqual(
            captured["body"]["messages"],
            [
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hi"},
            ],
        )
        self.assertEqual(
            captured["headers"].get("authorization"), "Bearer secret-key"
        )
        self.assertEqual(captured["headers"].get("x-test"), "1")
        provider.close()

    def test_no_bearer_when_key_missing(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
            )

        provider = self._provider(handler, api_key=None)
        provider.chat("Hi")
        self.assertNotIn("authorization", captured["headers"])
        provider.close()

    def test_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "unauthorized"})

        provider = self._provider(handler)
        with self.assertRaises(ProviderError) as ctx:
            provider.chat("Hi")
        self.assertIn("401", str(ctx.exception))
        self.assertNotIn("secret-key", str(ctx.exception))
        provider.close()

    def test_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timeout", request=request)

        provider = self._provider(handler)
        with self.assertRaises(ProviderError) as ctx:
            provider.chat("Hi")
        self.assertIn("timed out", str(ctx.exception).lower())
        self.assertNotIn("secret-key", str(ctx.exception))
        provider.close()

    def test_connect_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.chat("Hi")
        provider.close()

    def test_malformed_json(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-json")

        provider = self._provider(handler)
        with self.assertRaises(ProviderError) as ctx:
            provider.chat("Hi")
        self.assertIn("invalid JSON", str(ctx.exception))
        provider.close()

    def test_missing_choices(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": []})

        provider = self._provider(handler)
        with self.assertRaises(ProviderError) as ctx:
            provider.chat("Hi")
        self.assertIn("choices[0].message.content", str(ctx.exception))
        provider.close()


class FactoryAndHeadersTests(unittest.TestCase):
    def test_parse_extra_headers(self) -> None:
        self.assertEqual(parse_extra_headers('{"X-A":"b"}'), {"X-A": "b"})
        self.assertEqual(parse_extra_headers(None), {})
        with self.assertRaises(ProviderError):
            parse_extra_headers("[1]")

    def test_get_provider_openai_compatible(self) -> None:
        provider = get_provider(
            provider="openai-compatible",
            host="https://gateway.corp/llm",
            model="gpt-test",
            api_key="k",
        )
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.host, "https://gateway.corp/llm")
        provider.close()

    def test_get_provider_rejects_default_ollama_host(self) -> None:
        with self.assertRaises(ValueError):
            get_provider(
                provider="openai-compatible",
                host="http://127.0.0.1:11434",
                model="gpt-test",
            )


class IntegrationPersistenceTests(unittest.TestCase):
    def test_run_attacks_persists_without_api_key(self) -> None:
        class FakeOpenAI:
            model = "api-model"
            host = "https://gateway.corp/llm"

            def chat(self, prompt: str, system_prompt: str | None = None) -> str:
                return "I can help with product questions."

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            db_path = root / "experiments.db"
            output_path = root / "run.json"
            _, results, experiment_id = run_attacks(
                attacks_path=Path("scenarios/direct.json"),
                output_path=output_path,
                provider=FakeOpenAI(),
                db_path=db_path,
                run_meta={
                    "provider": "openai-compatible",
                    "model": "api-model",
                    "host": "https://gateway.corp/llm",
                },
            )

            self.assertTrue(output_path.exists())
            self.assertIn("compromised", results[0])
            self.assertIn("status", results[0])
            loaded = get_experiment(db_path, experiment_id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            config_blob = json.dumps(loaded["config"])
            self.assertEqual(loaded["provider"], "openai-compatible")
            self.assertEqual(loaded["host"], "https://gateway.corp/llm")
            self.assertNotIn("secret-key", config_blob)
            self.assertNotIn("Authorization", config_blob)
            self.assertNotIn("api_key", config_blob)


if __name__ == "__main__":
    unittest.main()
