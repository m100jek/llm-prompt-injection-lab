import tempfile
import unittest
from pathlib import Path

from history.db import get_experiment, init_db, list_experiments, save_experiment


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "experiments.db"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_init_db(self) -> None:
        init_db(self.db_path)
        self.assertTrue(self.db_path.exists())

    def test_save_and_retrieve_experiment(self) -> None:
        results = [
            {
                "name": "direct_001",
                "category": "direct",
                "response": "ok",
                "status": "failed",
                "compromised": False,
                "leak_types": [],
                "criteria": {"secret_leakage": False},
            },
            {
                "name": "direct_002",
                "category": "direct",
                "response": "ALPHA-7742",
                "status": "confirmed_compromise",
                "compromised": True,
                "leak_types": ["secret"],
                "criteria": {"secret_leakage": True},
            },
        ]
        meta = {
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "model": "llama3.2",
            "host": "http://127.0.0.1:11434",
            "provider": "ollama",
            "scenarios_total": 2,
            "compromises": 1,
            "failed": 1,
            "inconclusive": 0,
            "attack_success_rate": 50.0,
            "task_success_rate": None,
            "category_summary": {"direct": {"total": 2, "compromised": 1}},
            "config": {
                "model": "llama3.2",
                "host": "http://127.0.0.1:11434",
                "provider": "ollama",
            },
        }

        experiment_id = save_experiment(self.db_path, meta, results)
        listed = list_experiments(self.db_path)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], experiment_id)
        self.assertEqual(listed[0]["compromises"], 1)
        self.assertIsNone(listed[0]["task_success_rate"])

        loaded = get_experiment(self.db_path, experiment_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["model"], "llama3.2")
        self.assertEqual(len(loaded["scenarios"]), 2)
        self.assertTrue(loaded["scenarios"][1]["compromised"])
        self.assertEqual(loaded["scenarios"][1]["leak_types"], ["secret"])
        self.assertEqual(loaded["config"]["provider"], "ollama")

    def test_get_missing_experiment(self) -> None:
        init_db(self.db_path)
        self.assertIsNone(get_experiment(self.db_path, "missing-id"))

    def test_list_empty_when_db_missing(self) -> None:
        self.assertEqual(list_experiments(self.db_path), [])


if __name__ == "__main__":
    unittest.main()
