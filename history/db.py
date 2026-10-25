import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class HistoryError(Exception):
    pass


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path) -> None:
    connection = _connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                started_at TEXT,
                finished_at TEXT,
                model TEXT,
                host TEXT,
                provider TEXT,
                scenarios_total INTEGER,
                compromises INTEGER,
                failed INTEGER,
                inconclusive INTEGER,
                attack_success_rate REAL,
                task_success_rate REAL,
                category_summary_json TEXT,
                config_json TEXT
            );

            CREATE TABLE IF NOT EXISTS scenario_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                name TEXT,
                category TEXT,
                response TEXT,
                status TEXT,
                compromised INTEGER,
                leak_types_json TEXT,
                criteria_json TEXT,
                created_at TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            );
            """
        )
        connection.commit()
    except sqlite3.Error as exc:
        raise HistoryError(f"Failed to initialize database: {exc}") from exc
    finally:
        connection.close()


def save_experiment(
    db_path: Path,
    experiment_meta: dict,
    results: list[dict],
) -> str:
    init_db(db_path)
    experiment_id = experiment_meta.get("id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    connection = _connect(db_path)

    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO experiments (
                id, started_at, finished_at, model, host, provider,
                scenarios_total, compromises, failed, inconclusive,
                attack_success_rate, task_success_rate,
                category_summary_json, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                experiment_meta.get("started_at"),
                experiment_meta.get("finished_at"),
                experiment_meta.get("model"),
                experiment_meta.get("host"),
                experiment_meta.get("provider"),
                experiment_meta.get("scenarios_total", len(results)),
                experiment_meta.get("compromises", 0),
                experiment_meta.get("failed", 0),
                experiment_meta.get("inconclusive", 0),
                experiment_meta.get("attack_success_rate"),
                experiment_meta.get("task_success_rate"),
                json.dumps(experiment_meta.get("category_summary", {})),
                json.dumps(experiment_meta.get("config", {})),
            ),
        )

        for result in results:
            connection.execute(
                """
                INSERT INTO scenario_results (
                    experiment_id, name, category, response, status,
                    compromised, leak_types_json, criteria_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    result.get("name"),
                    result.get("category"),
                    result.get("response"),
                    result.get("status"),
                    1 if result.get("compromised") else 0,
                    json.dumps(result.get("leak_types") or []),
                    json.dumps(result.get("criteria") or {}),
                    now,
                ),
            )

        connection.commit()
    except sqlite3.Error as exc:
        connection.rollback()
        raise HistoryError(f"Failed to save experiment: {exc}") from exc
    finally:
        connection.close()

    return experiment_id


def list_experiments(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []

    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT id, started_at, finished_at, model, host, provider,
                   scenarios_total, compromises, failed, inconclusive,
                   attack_success_rate, task_success_rate
            FROM experiments
            ORDER BY finished_at DESC, started_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise HistoryError(f"Failed to list experiments: {exc}") from exc
    finally:
        connection.close()


def get_experiment(db_path: Path, experiment_id: str) -> dict | None:
    if not db_path.exists():
        return None

    connection = _connect(db_path)
    try:
        experiment = connection.execute(
            """
            SELECT id, started_at, finished_at, model, host, provider,
                   scenarios_total, compromises, failed, inconclusive,
                   attack_success_rate, task_success_rate,
                   category_summary_json, config_json
            FROM experiments
            WHERE id = ?
            """,
            (experiment_id,),
        ).fetchone()

        if experiment is None:
            return None

        scenario_rows = connection.execute(
            """
            SELECT name, category, response, status, compromised,
                   leak_types_json, criteria_json, created_at
            FROM scenario_results
            WHERE experiment_id = ?
            ORDER BY id ASC
            """,
            (experiment_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise HistoryError(f"Failed to load experiment: {exc}") from exc
    finally:
        connection.close()

    meta = dict(experiment)
    meta["category_summary"] = json.loads(meta.pop("category_summary_json") or "{}")
    meta["config"] = json.loads(meta.pop("config_json") or "{}")

    scenarios = []
    for row in scenario_rows:
        item = dict(row)
        item["compromised"] = bool(item["compromised"])
        item["leak_types"] = json.loads(item.pop("leak_types_json") or "[]")
        item["criteria"] = json.loads(item.pop("criteria_json") or "{}")
        scenarios.append(item)

    meta["scenarios"] = scenarios
    return meta
