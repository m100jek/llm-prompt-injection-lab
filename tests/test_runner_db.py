import tempfile
import unittest
from pathlib import Path

from attack_runner import run_attacks
from history.db import get_experiment, list_experiments


class FakeProvider:
    def __init__(self) -> None:
        self.model = "fake-model"
        self.host = "http://127.0.0.1:11434"

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        if "Ignore all previous" in prompt:
            return "I can help with product questions."
        return "Returns are accepted within 30 days."


class RunnerDbTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmpdir.name)
        self.db_path = self.root / "experiments.db"
        self.output_path = self.root / "run.json"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_run_attacks_writes_json_and_sqlite(self) -> None:
        output_path, results, experiment_id = run_attacks(
            attacks_path=Path("scenarios/direct.json"),
            output_path=self.output_path,
            provider=FakeProvider(),
            db_path=self.db_path,
            run_meta={
                "provider": "ollama",
                "model": "fake-model",
                "host": "http://127.0.0.1:11434",
            },
        )

        self.assertTrue(output_path.exists())
        self.assertIsNotNone(experiment_id)
        self.assertEqual(len(results), 6)
        self.assertIn("compromised", results[0])
        self.assertIn("leak_types", results[0])
        self.assertIn("status", results[0])
        self.assertIn("criteria", results[0])

        listed = list_experiments(self.db_path)
        self.assertEqual(len(listed), 1)
        loaded = get_experiment(self.db_path, experiment_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(len(loaded["scenarios"]), 6)
        self.assertEqual(loaded["model"], "fake-model")


if __name__ == "__main__":
    unittest.main()
