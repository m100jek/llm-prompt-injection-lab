import json
from datetime import datetime, timezone
from pathlib import Path

from config import (
    DEFAULT_ATTACKS_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_SYSTEM_PROMPT,
    RAG_DOCUMENTS_DIR,
    RAG_TOP_K,
    RESULTS_DIR,
    VALID_CATEGORIES,
)
from encoding import validate_encoded_payload
from evaluator import enrich_result, summarize_results
from providers.base import LLMProvider
from providers.errors import ProviderError
from rag.retriever import load_document, retrieve


class AttackLoadError(Exception):
    pass


def _parse_attack(item: dict, index: int, seen_names: set[str]) -> dict:
    if not isinstance(item, dict):
        raise AttackLoadError(f"Attack at index {index} must be an object")

    name = item.get("name")
    category = item.get("category")
    prompt = item.get("prompt")

    if not name or not isinstance(name, str):
        raise AttackLoadError(f"Attack at index {index} is missing a valid 'name'")
    if not category or category not in VALID_CATEGORIES:
        raise AttackLoadError(
            f"Attack '{name}' must have a valid category: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    if not prompt or not isinstance(prompt, str):
        raise AttackLoadError(f"Attack '{name}' is missing a valid 'prompt'")
    if name in seen_names:
        raise AttackLoadError(f"Duplicate attack name: {name}")

    attack = {
        "name": name,
        "category": category,
        "prompt": prompt,
    }

    evaluation = item.get("evaluation")
    if evaluation is not None:
        if not isinstance(evaluation, dict):
            raise AttackLoadError(f"Attack '{name}' has an invalid 'evaluation' block")
        attack["evaluation"] = evaluation

    if category == "indirect":
        rag_query = item.get("rag_query")
        document = item.get("document")
        if rag_query is not None:
            if not isinstance(rag_query, str) or not rag_query.strip():
                raise AttackLoadError(f"Attack '{name}' has an invalid 'rag_query'")
            attack["rag_query"] = rag_query
        if document is not None:
            if not isinstance(document, str) or not document.strip():
                raise AttackLoadError(f"Attack '{name}' has an invalid 'document'")
            attack["document"] = document

    if category == "encoding":
        encoding = item.get("encoding")
        if not encoding or not isinstance(encoding, str):
            raise AttackLoadError(f"Attack '{name}' is missing a valid 'encoding'")
        try:
            validate_encoded_payload(prompt, encoding)
        except ValueError as exc:
            raise AttackLoadError(f"Attack '{name}': {exc}") from exc
        attack["encoding"] = encoding

    seen_names.add(name)
    return attack


def load_attacks(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AttackLoadError(f"Attacks file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AttackLoadError(f"Invalid JSON in attacks file: {path}") from exc

    if not isinstance(data, list):
        raise AttackLoadError("Attacks file must contain a JSON array")

    seen_names: set[str] = set()
    return [_parse_attack(item, index, seen_names) for index, item in enumerate(data)]


def load_all_attacks(path: Path) -> list[dict]:
    if path.is_dir():
        attack_files = sorted(path.glob("*.json"))
        if not attack_files:
            raise AttackLoadError(f"No attack JSON files found in: {path}")

        attacks: list[dict] = []
        seen_names: set[str] = set()
        for attack_file in attack_files:
            for index, item in enumerate(
                json.loads(attack_file.read_text(encoding="utf-8"))
            ):
                attack = _parse_attack(item, index, seen_names)
                attacks.append(attack)
        return attacks

    return load_attacks(path)


def prepare_attack_prompt(attack: dict) -> str:
    category = attack["category"]
    prompt = attack["prompt"]

    if category in {"direct", "role_confusion", "encoding", "benign"}:
        return prompt

    if category == "indirect":
        if "document" in attack:
            chunk = load_document(RAG_DOCUMENTS_DIR, attack["document"])
            chunks = [chunk]
        else:
            rag_query = attack.get("rag_query", prompt)
            chunks = retrieve(rag_query, RAG_DOCUMENTS_DIR, top_k=RAG_TOP_K)

        if not chunks:
            return prompt

        context_blocks = []
        for chunk in chunks:
            context_blocks.append(
                f"[source: {chunk['source']}]\n{chunk['text']}"
            )

        context = "\n---\n".join(context_blocks)
        return (
            "Retrieved context:\n"
            "---\n"
            f"{context}\n"
            "---\n\n"
            f"User request: {prompt}"
        )

    return prompt


def run_attack(
    attack: dict,
    provider: LLMProvider,
    system_prompt: str,
) -> dict:
    prepared_prompt = prepare_attack_prompt(attack)

    try:
        response = provider.chat(prepared_prompt, system_prompt=system_prompt)
    except ProviderError as exc:
        response = f"Error: {exc}"

    return enrich_result(
        {
            "name": attack["name"],
            "category": attack["category"],
            "response": response,
        },
        attack=attack,
    )


def save_result(results: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return RESULTS_DIR / f"run_{timestamp}.json"


def run_attacks(
    attacks_path: Path = DEFAULT_ATTACKS_PATH,
    output_path: Path | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    provider: LLMProvider | None = None,
    db_path: Path | None = DEFAULT_DB_PATH,
    run_meta: dict | None = None,
) -> tuple[Path, list[dict], str | None]:
    from providers import get_provider

    llm = provider or get_provider()
    attacks = load_all_attacks(attacks_path)
    target_path = output_path or default_output_path()
    started_at = datetime.now(timezone.utc).isoformat()

    results = []
    for attack in attacks:
        result = run_attack(attack, llm, system_prompt)
        results.append(result)

    finished_at = datetime.now(timezone.utc).isoformat()
    save_result(results, target_path)

    experiment_id = None
    if db_path is not None:
        try:
            from history.db import HistoryError, save_experiment

            summary = summarize_results(results)
            meta = {
                "started_at": started_at,
                "finished_at": finished_at,
                "model": getattr(llm, "model", None),
                "host": getattr(llm, "host", None),
                "provider": (run_meta or {}).get("provider"),
                "scenarios_total": summary["total"],
                "compromises": summary["compromised"],
                "failed": summary["failed"],
                "inconclusive": summary["inconclusive"],
                "attack_success_rate": summary["attack_success_rate"],
                "task_success_rate": summary["task_success_rate"],
                "category_summary": summary["by_category"],
                "config": {
                    "attacks_path": str(attacks_path),
                    "model": getattr(llm, "model", None),
                    "host": getattr(llm, "host", None),
                    "provider": (run_meta or {}).get("provider"),
                },
            }
            if run_meta:
                for key in ("model", "host", "provider"):
                    if run_meta.get(key) is not None:
                        meta[key] = run_meta[key]
                        meta["config"][key] = run_meta[key]

            experiment_id = save_experiment(db_path, meta, results)
        except HistoryError as exc:
            print(f"Warning: could not save experiment history: {exc}")

    return target_path, results, experiment_id
