import unittest
from pathlib import Path

from attack_runner import load_all_attacks, load_attacks
from evaluator import enrich_result


class CompatibilityTests(unittest.TestCase):
    def test_existing_scenario_files_load(self) -> None:
        scenarios_dir = Path("scenarios")
        attacks = load_all_attacks(scenarios_dir)
        self.assertGreaterEqual(len(attacks), 15)
        names = {attack["name"] for attack in attacks}
        self.assertIn("direct_001", names)
        self.assertIn("indirect_001", names)
        self.assertIn("benign_001", names)

    def test_existing_direct_file_without_evaluation_block(self) -> None:
        attacks = load_attacks(Path("scenarios/direct.json"))
        self.assertTrue(all("evaluation" not in attack for attack in attacks))

    def test_enrich_result_backward_compatible_fields(self) -> None:
        result = enrich_result(
            {
                "name": "direct_001",
                "category": "direct",
                "response": "I can help with products.",
            }
        )
        self.assertIn("compromised", result)
        self.assertIn("leak_types", result)
        self.assertIn("status", result)
        self.assertIn("criteria", result)
        self.assertIsInstance(result["compromised"], bool)
        self.assertIsInstance(result["leak_types"], list)


if __name__ == "__main__":
    unittest.main()
