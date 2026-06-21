import json
from datetime import datetime
from pathlib import Path

from config import DEFAULT_ATTACKS_PATH, DEFAULT_SYSTEM_PROMPT, RESULTS_DIR
from ollama_client import DEFAULT_MODEL, OllamaClientError, chat


class AttackLoadError(Exception):
    pass


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
    attacks = []

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise AttackLoadError(f"Attack at index {index} must be an object")

        name = item.get("name")
        prompt = item.get("prompt")

        if not name or not isinstance(name, str):
            raise AttackLoadError(f"Attack at index {index} is missing a valid 'name'")
        if not prompt or not isinstance(prompt, str):
            raise AttackLoadError(f"Attack '{name}' is missing a valid 'prompt'")
        if name in seen_names:
            raise AttackLoadError(f"Duplicate attack name: {name}")

        seen_names.add(name)
        attacks.append({"name": name, "prompt": prompt})

    return attacks


def run_attack(attack: dict, system_prompt: str, model: str) -> dict:
    try:
        response = chat(attack["prompt"], model=model, system_prompt=system_prompt)
    except OllamaClientError as exc:
        response = f"Error: {exc}"

    return {"name": attack["name"], "response": response}


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
    model: str = DEFAULT_MODEL,
) -> Path:
    attacks = load_attacks(attacks_path)
    target_path = output_path or default_output_path()

    results = []
    for attack in attacks:
        result = run_attack(attack, system_prompt, model)
        results.append(result)

    save_result(results, target_path)
    return target_path, len(results)
