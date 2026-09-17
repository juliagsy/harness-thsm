"""Headline plot (docs/02 §3): authority fidelity (1 - FAR) against a utility composite,
one curve per backend as decay aggressiveness sweeps, mean over seeds."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path


def _nanmean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else float("nan")


def collect(results_dir: str | Path) -> list[dict]:
    rows = []
    for d in sorted(Path(results_dir).glob("*")):
        sc, mf = d / "scorecard.json", d / "manifest.json"
        if not (sc.exists() and mf.exists()):
            continue
        s, m = json.loads(sc.read_text()), json.loads(mf.read_text())
        u, a = s["utility"], s["authority"]
        rows.append(
            {
                "run": d.name,
                "backend": m["backend"],
                "aggressiveness": m.get("backend_desc", {}).get(
                    "aggressiveness",
                    m.get("backend_cfg", {}).get("params", {}).get("aggressiveness"),
                ),
                "decay": m.get("backend_desc", {}).get("decay"),
                "seed": m["seed"],
                "model": m["model"],
                "utility": _nanmean(
                    [
                        u.get("KUA"),
                        u.get("SSR"),
                        None if u.get("REGRESS") is None else 1 - u["REGRESS"],
                    ]
                ),
                "fidelity": None if a.get("FAR") is None else 1 - a["FAR"],
                "FAR": a.get("FAR"),
                "KUA": u.get("KUA"),
                "SSR": u.get("SSR"),
                "STALE": u.get("STALE"),
                "LRR": a.get("LRR"),
                "CLAIMS": s["counts"].get("CLAIMS"),
                "INV": s["counts"].get("INV"),
            }
        )
    return rows


def aggregate(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["backend"], r["aggressiveness"])].append(r)
    out = []
    for (b, a), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        out.append(
            {
                "backend": b,
                "aggressiveness": a,
                "n": len(rs),
                **{
                    k: _nanmean([r[k] for r in rs])
                    for k in (
                        "utility",
                        "fidelity",
                        "FAR",
                        "KUA",
                        "SSR",
                        "STALE",
                        "LRR",
                        "CLAIMS",
                        "INV",
                    )
                },
            }
        )
    return out


def summary_table(rows: list[dict]) -> str:
    agg = aggregate(rows)
    head = (
        f"{'backend':16} {'aggr':>5} {'n':>3} {'utility':>8} {'1-FAR':>6} {'KUA':>5} {'SSR':>5} "
        f"{'STALE':>6} {'LRR':>5} {'CLAIMS':>7} {'INV':>5}"
    )
    lines = [head, "-" * len(head)]
    for g in agg:

        def f(v, w=5, p=2):
            return (
                f"{'-':>{w}}"
                if v is None or (isinstance(v, float) and math.isnan(v))
                else f"{v:>{w}.{p}f}"
            )

        lines.append(
            f"{g['backend']:16} {f(g['aggressiveness'], 5, 2)} {g['n']:>3} "
            f"{f(g['utility'], 8)} {f(g['fidelity'], 6)} {f(g['KUA'])} {f(g['SSR'])} "
            f"{f(g['STALE'], 6)} {f(g['LRR'])} {f(g['CLAIMS'], 7, 1)} {f(g['INV'], 5, 1)}"
        )
    return "\n".join(lines)


def frontier_plot(rows: list[dict], out_path: str | Path, title: str = "") -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    agg = aggregate(rows)
    by_backend: dict[str, list[dict]] = defaultdict(list)
    for g in agg:
        by_backend[g["backend"]].append(g)
    fig, ax = plt.subplots(figsize=(7, 5))
    for b, gs in sorted(by_backend.items()):
        gs = sorted(gs, key=lambda g: g["aggressiveness"] or 0)
        xs = [g["utility"] for g in gs]
        ys = [g["fidelity"] for g in gs]
        ax.plot(xs, ys, marker="o", label=b)
        for g, x, y in zip(gs, xs, ys, strict=True):
            if g["aggressiveness"] is not None:
                ax.annotate(
                    f"{g['aggressiveness']:.2f}",
                    (x, y),
                    fontsize=7,
                    xytext=(3, 3),
                    textcoords="offset points",
                )
    ax.set_xlabel("utility composite  (mean of KUA, SSR, 1-REGRESS)")
    ax.set_ylabel("authority fidelity  (1 - FAR)")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title(title or "Utility vs authority frontier (labels = decay aggressiveness)")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
