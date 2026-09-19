"""Summaries for Continual-ARC runs of the memory learner: score, retention by gap,
cost by exposure and the learner's own memory counters, side by side per run."""

from __future__ import annotations

import json
from pathlib import Path


def load_run(run_dir: str | Path) -> dict:
    d = Path(run_dir)
    summary = json.loads((d / "summary.json").read_text())
    records = [json.loads(line) for line in (d / "records.jsonl").read_text().splitlines()]
    res = {
        "calls": 0.0,
        "tokens_in": 0.0,
        "tokens_out": 0.0,
        "rules_evicted": 0.0,
        "rules_rederived": 0.0,
        "rule_hits": 0.0,
    }
    for r in records:
        for k in res:
            res[k] += float(r.get("resources", {}).get(k, 0.0))
    stream = [r for r in records if r["phase"] not in ("epilogue",)]
    repeats = [r for r in stream if r["exposure_index"] > 0]
    return {
        "name": d.name,
        "overall": summary.get("overall", {}),
        "acquisition": summary.get("acquisition", {}),
        "retention_by_gap": summary.get("retention_by_gap", []),
        "cost_by_exposure": summary.get("cost_by_exposure", []),
        "epilogue": summary.get("epilogue", {}),
        "n": len(records),
        "solved": sum(r["solved"] for r in records),
        "solved_first": sum(r["solved"] for r in stream if r["exposure_index"] == 0),
        "n_first": sum(1 for r in stream if r["exposure_index"] == 0),
        "solved_repeat": sum(r["solved"] for r in repeats),
        "n_repeat": len(repeats),
        "resources": res,
    }


def table(run_dirs: list[str | Path]) -> str:
    runs = [load_run(d) for d in run_dirs]
    head = (
        f"{'run':28} {'score':>6} {'solve':>6} {'first':>6} {'repeat':>7} {'evict':>6} "
        f"{'rederiv':>8} {'hits':>5} {'tok_in':>8}"
    )
    lines = [head, "-" * len(head)]
    for r in runs:
        sc = r["overall"].get("score", float("nan"))
        first = r["solved_first"] / r["n_first"] if r["n_first"] else float("nan")
        rep = r["solved_repeat"] / r["n_repeat"] if r["n_repeat"] else float("nan")
        res = r["resources"]
        lines.append(
            f"{r['name']:28} {sc:6.1f} {r['solved'] / r['n']:6.2f} {first:6.2f} {rep:7.2f} "
            f"{res['rules_evicted']:6.0f} {res['rules_rederived']:8.0f} {res['rule_hits']:5.0f} "
            f"{res['tokens_in'] / 1e3:7.0f}k"
        )
    lines.append("")
    lines.append("retention by gap (solve rate / mean cost):")
    gaps = [g["gap"] for g in runs[0]["retention_by_gap"]] if runs else []
    lines.append(f"{'run':28} " + " ".join(f"{g:>14}" for g in gaps))
    for r in runs:
        cells = []
        for g in r["retention_by_gap"]:
            if g.get("n"):
                cells.append(f"{g['solve_rate']:.2f}/{g['mean_cost']:.1f} n{g['n']:<3}")
            else:
                cells.append("-")
        lines.append(f"{r['name']:28} " + " ".join(f"{c:>14}" for c in cells))
    return "\n".join(lines)
