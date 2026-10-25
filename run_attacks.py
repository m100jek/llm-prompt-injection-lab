import argparse
import os
from pathlib import Path

from attack_runner import AttackLoadError, run_attacks
from config import (
    DEFAULT_ATTACKS_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_LLM_HOST,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_SYSTEM_PROMPT,
    LLM_API_KEY_ENV,
    LLM_EXTRA_HEADERS_ENV,
)
from evaluator import print_summary, summarize_results
from history.db import HistoryError, get_experiment, list_experiments
from providers.errors import ProviderError


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
        help=(
            "Ollama host/IP (default: http://127.0.0.1:11434) or "
            "OpenAI-compatible exact chat API endpoint URL"
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help="LLM provider: ollama or openai-compatible (default: ollama)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite experiment history database path",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List previous experiments from SQLite and exit",
    )
    parser.add_argument(
        "--show-run",
        metavar="EXPERIMENT_ID",
        default=None,
        help="Show detailed results for an experiment ID and exit",
    )
    return parser.parse_args()


def _format_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}%"


def print_experiment_list(db_path: Path) -> None:
    try:
        experiments = list_experiments(db_path)
    except HistoryError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    if not experiments:
        print("No experiments found.")
        return

    print(
        f"{'ID':<38} {'Finished':<28} {'Model':<12} "
        f"{'Total':>5} {'Comp':>4} {'Fail':>4} {'Inc':>3} {'ASR':>6}"
    )
    for item in experiments:
        print(
            f"{item['id']:<38} "
            f"{(item.get('finished_at') or '-'):<28} "
            f"{(item.get('model') or '-'):<12} "
            f"{item.get('scenarios_total') or 0:>5} "
            f"{item.get('compromises') or 0:>4} "
            f"{item.get('failed') or 0:>4} "
            f"{item.get('inconclusive') or 0:>3} "
            f"{_format_rate(item.get('attack_success_rate')):>6}"
        )


def print_experiment_detail(db_path: Path, experiment_id: str) -> None:
    try:
        experiment = get_experiment(db_path, experiment_id)
    except HistoryError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    if experiment is None:
        print(f"Experiment not found: {experiment_id}")
        raise SystemExit(1)

    print(f"Experiment ID: {experiment['id']}")
    print(f"Started:  {experiment.get('started_at')}")
    print(f"Finished: {experiment.get('finished_at')}")
    print(f"Model:    {experiment.get('model')}")
    print(f"Host:     {experiment.get('host')}")
    print(f"Provider: {experiment.get('provider')}")
    print(
        f"Totals:   scenarios={experiment.get('scenarios_total')} "
        f"compromises={experiment.get('compromises')} "
        f"failed={experiment.get('failed')} "
        f"inconclusive={experiment.get('inconclusive')}"
    )
    print(
        f"Rates:    ASR={_format_rate(experiment.get('attack_success_rate'))} "
        f"TSR={_format_rate(experiment.get('task_success_rate'))}"
    )
    print()
    print("Scenario results:")
    for scenario in experiment.get("scenarios", []):
        status = scenario.get("status")
        compromised = scenario.get("compromised")
        leak_types = ", ".join(scenario.get("leak_types") or []) or "-"
        print(
            f"  - {scenario.get('name')} [{scenario.get('category')}] "
            f"status={status} compromised={compromised} leak_types={leak_types}"
        )


def main() -> None:
    args = parse_args()

    if args.list_runs:
        print_experiment_list(args.db)
        return

    if args.show_run:
        print_experiment_detail(args.db, args.show_run)
        return

    try:
        from config import normalize_host
        from providers import get_provider
        from providers.openai_compatible import (
            parse_extra_headers,
            validate_api_endpoint_url,
        )

        api_key = None
        extra_headers = None
        if args.provider in {"openai-compatible", "openai_compatible"}:
            api_key = os.environ.get(LLM_API_KEY_ENV)
            extra_headers = parse_extra_headers(
                os.environ.get(LLM_EXTRA_HEADERS_ENV)
            )
            persisted_host = validate_api_endpoint_url(args.host)
        else:
            persisted_host = normalize_host(args.host)

        provider = get_provider(
            provider=args.provider,
            host=args.host,
            model=args.model,
            api_key=api_key,
            extra_headers=extra_headers,
        )

        output_path, results, experiment_id = run_attacks(
            attacks_path=args.attacks,
            output_path=args.output,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            provider=provider,
            db_path=args.db,
            run_meta={
                "provider": args.provider,
                "host": persisted_host,
                "model": args.model,
            },
        )
    except AttackLoadError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    except (NotImplementedError, ValueError, ProviderError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    print(f"Completed {len(results)} attacks")
    print(f"Results saved to: {output_path}")
    if experiment_id:
        print(f"Experiment ID: {experiment_id}")
    print_summary(summarize_results(results))


if __name__ == "__main__":
    main()
