import argparse
from pathlib import Path

from attack_runner import AttackLoadError, run_attacks
from config import DEFAULT_ATTACKS_PATH, DEFAULT_SYSTEM_PROMPT
from ollama_client import DEFAULT_MODEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run prompt injection attacks from a JSON catalog"
    )
    parser.add_argument(
        "--attacks",
        type=Path,
        default=DEFAULT_ATTACKS_PATH,
        help="Path to attacks JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output JSON file (default: results/run_TIMESTAMP.json)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model name",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        output_path, attack_count = run_attacks(
            attacks_path=args.attacks,
            output_path=args.output,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            model=args.model,
        )
    except AttackLoadError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    print(f"Completed {attack_count} attacks")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
