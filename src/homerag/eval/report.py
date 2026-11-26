"""Run files: write, read back, print and compare them. Plain JSON in, plain text out.

A run folder holds `config.yaml`, `results.jsonl` (one row per golden question), `metrics.json`
(means per part: retrieval, generation, gate; then per category) and `meta.json`.
`RUN_FORMAT` changes whenever these files do; an older run must be re-run, not compared.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any  # JSON rows and metadata: values of mixed types, checked when read

import yaml

from homerag.config import ExperimentConfig

RUN_FORMAT = 2  # 2: one results row per question with every part; metrics.json by part

Metrics = dict[str, dict[str, float]]

# Per-question metrics where a lower value in the second run is a regression.
TRACKED = {"retrieval": ("mrr",), "generation": ("correct", "faithful", "cites", "paraphrase")}


@dataclass(frozen=True, slots=True)
class SavedRun:
    """A run folder read back from disk."""

    folder: Path
    meta: dict[str, Any]
    metrics: dict[str, Metrics]
    rows: list[dict[str, Any]]


def save_run(
    folder: Path,
    cfg: ExperimentConfig,
    rows: list[dict[str, Any]],
    metrics: dict[str, Metrics],
    meta: dict[str, Any],
) -> None:
    """Write the four run files; refuses to overwrite an existing run."""
    folder.mkdir(parents=True, exist_ok=False)
    config = yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False)
    (folder / "config.yaml").write_text(config, encoding="utf-8")
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    (folder / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def load_run(folder: Path) -> SavedRun:
    """Read a run folder; fails clearly on a missing folder or an older format."""
    if not (folder / "meta.json").exists():
        raise ValueError(f"{folder}: not a run folder (no meta.json)")
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    if meta.get("run_format") != RUN_FORMAT:
        raise ValueError(f"{folder}: saved in an older run format: run the experiment again")
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    lines = (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()
    return SavedRun(folder, meta, metrics, [json.loads(line) for line in lines if line])


def format_metrics(metrics: Metrics) -> str:
    """A plain-text table: one row per category (then "all"), one column per metric."""
    if not metrics:
        return "no questions evaluated\n"
    names = [name for name in next(iter(metrics.values())) if name != "n"]
    widths = [max(6, len(name)) for name in names]
    header = f"{'category':<12} {'n':>3}  " + "  ".join(
        f"{name:>{w}}" for name, w in zip(names, widths, strict=True)
    )
    rows = [
        f"{category:<12} {int(values['n']):>3}  "
        + "  ".join(f"{values[name]:>{w}.2f}" for name, w in zip(names, widths, strict=True))
        for category, values in metrics.items()
    ]
    return "\n".join([header, *rows]) + "\n"


def format_gate(gate: dict[str, float], errors: list[str]) -> str:
    """One line with the gate scores, plus the ids of the misjudged questions if any."""
    line = (
        f"language gate: {int(gate['n'])} messages, accuracy {gate['accuracy']:.2f}, "
        f"English blocked {int(gate['english_blocked'])}, "
        f"non-English passed {int(gate['non_english_passed'])}\n"
    )
    return line + (f"  misjudged: {', '.join(errors)}\n" if errors else "")


def format_cost(cost: dict[str, float]) -> str:
    """One line: what the answers and the judge cost, and how much was paid in this run."""
    return (
        f"cost: answers ${cost['answers']:.2f}, judge ${cost['judge']:.2f} "
        f"(paid in this run ${cost['paid_now']:.2f}; the rest came from the cache)\n"
    )


def compare_runs(a: SavedRun, b: SavedRun) -> str:
    """Run B against run A: metric deltas per part and category, gate, cost, and the
    questions that got worse or better on the tracked metrics."""
    lines = [f"A: {a.folder.name}", f"B: {b.folder.name}", ""]
    for part in ("retrieval", "generation"):
        lines += [f"{part} (B, change from A)", _delta_table(a.metrics[part], b.metrics[part]), ""]
    gate_a, gate_b = a.metrics["gate"]["all"]["accuracy"], b.metrics["gate"]["all"]["accuracy"]
    lines.append(f"language gate accuracy: {gate_a:.2f} -> {gate_b:.2f}")
    cost_a, cost_b = a.meta["cost_usd"], b.meta["cost_usd"]
    total_a = cost_a["answers"] + cost_a["judge"]
    total_b = cost_b["answers"] + cost_b["judge"]
    lines.append(f"cost per run (answers + judge): ${total_a:.2f} -> ${total_b:.2f}")
    worse, better = _changed_questions(a.rows, b.rows)
    lines += ["", "worse in B:", *(worse or ["  none"]), "better in B:", *(better or ["  none"])]
    return "\n".join(lines) + "\n"


def _delta_table(a: Metrics, b: Metrics) -> str:
    if not b:
        return "  not run in B"
    names = [name for name in next(iter(b.values())) if name != "n"]
    widths = [max(11, len(name)) for name in names]
    header = f"{'category':<12} {'n':>3}  " + "  ".join(
        f"{name:>{w}}" for name, w in zip(names, widths, strict=True)
    )
    rows = []
    for category, values in b.items():
        before = a.get(category, {})
        cells = [
            f"{values[name]:.2f} {values[name] - before[name]:+.2f}"
            if name in before
            else f"{values[name]:.2f}    new"
            for name in names
        ]
        rows.append(
            f"{category:<12} {int(values['n']):>3}  "
            + "  ".join(f"{cell:>{w}}" for cell, w in zip(cells, widths, strict=True))
        )
    return "\n".join([header, *rows])


def _changed_questions(
    rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    by_id = {row["id"]: row for row in rows_a}
    worse, better = [], []
    for row in rows_b:
        before = by_id.get(row["id"])
        if before is None:
            continue
        down: list[str] = []
        up: list[str] = []
        for part, names in TRACKED.items():
            old = (before.get(part) or {}).get("metrics") or {}
            new = (row.get(part) or {}).get("metrics") or {}
            for name in names:
                if name in old and name in new and old[name] != new[name]:
                    change = f"{name} {old[name]:.2f} -> {new[name]:.2f}"
                    (down if new[name] < old[name] else up).append(change)
        label = f"  {row['id']} ({row['category']}): "
        if down:
            worse.append(label + "; ".join(down))
        if up:
            better.append(label + "; ".join(up))
    return worse, better
