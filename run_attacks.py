import argparse
from pathlib import Path

from attack_runner import AttackLoadError, run_attacks
from evaluator import print_summary, summarize_results
from config import DEFAULT_ATTACKS_PATH, DEFAULT_LLM_HOST, DEFAULT_PROVIDER, DEFAULT_SYSTEM_PROMPT
from config import DEFAULT_MODEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run prompt injection attacks from a JSON catalog"
    )
    parser.add_argument(
        "--attacks",
        type=Path,
        default=DEFAULT_ATTACKS_PATH,
        help="Path to attacks JSON file or scenarios directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output JSON file (default: results/run_TIMESTAMP.json)",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_LLM_HOST,
        help="LLM host URL or IP (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help="LLM provider (default: ollama)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from providers import get_provider

        provider = get_provider(
            provider=args.provider,
            host=args.host,
            model=args.model,
        )
        output_path, results = run_attacks(
            attacks_path=args.attacks,
            output_path=args.output,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            provider=provider,
        )
    except AttackLoadError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    except NotImplementedError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    print(f"Completed {len(results)} attacks")
    print(f"Results saved to: {output_path}")
    print_summary(summarize_results(results))


if __name__ == "__main__":
    main()
