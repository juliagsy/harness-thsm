"""Paper figures: vector output (PDF + SVG + PNG) with one fixed categorical assignment per
store across every figure, thin marks, direct labels that are pushed apart when they
collide, recessive axes."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from decaymem.report.frontier import COARSE_BINS, _nanmean, aggregate, collect

# fixed hue per store (identity, never rank); validated 6-slot palette + neutrals
COLORS = {
    "flat_ebbinghaus": "#2a78d6",
    "flat_actr": "#eb6834",
    "flat_memworth": "#1baf7a",
    "thsm_nogate": "#eda100",
    "thsm": "#008300",
    "labels_notypes": "#4a3aa7",
    "typed_nolabels": "#8c8b86",
    "thsm_nopin": "#6fa86f",
    "thsm_pintool": "#a3c9a3",
    "mem0": "#e34948",
}
LABELS = {
    "flat_ebbinghaus": "type-blind (Ebbinghaus)",
    "flat_actr": "type-blind (ACT-R)",
    "flat_memworth": "type-blind (Memory Worth)",
    "thsm_nogate": "THSM, no gate (pinned only)",
    "thsm": "THSM",
    "labels_notypes": "labels only",
    "typed_nolabels": "types only",
    "thsm_nopin": "THSM, no pinning",
    "thsm_pintool": "THSM, tool-only pinning",
    "mem0": "Mem0 (external)",
}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _style(ax, xlabel: str, ylabel: str, title: str, pad: float = 6.0) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8, length=3)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    if title:
        ax.set_title(title, color=INK, fontsize=10, loc="left", pad=pad)


def _spread(items: list[tuple[float, str]], gap: float) -> list[tuple[float, str]]:
    """Nudge label y-positions apart so end labels never overlap."""
    items = sorted(items, key=lambda t: t[0])
    out: list[tuple[float, str]] = []
    for y, text in items:
        if out and y - out[-1][0] < gap:
            y = out[-1][0] + gap
        out.append((y, text))
    return out


def _end_labels(
    ax, x: float, items: list[tuple[float, str]], gap: float, dx: int = 5, size: float = 7.5
) -> None:
    for y, text in _spread(items, gap):
        ax.annotate(
            text,
            (x, y),
            xytext=(dx, 0),
            textcoords="offset points",
            fontsize=size,
            color=INK2,
            va="center",
        )


def _save(fig, out: Path, stem: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "svg", "png"):
        p = out / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor=SURFACE)
        paths.append(p)
    return paths


def fig_far_by_family(
    experiments: dict[str, str],
    stores: list[str],
    out: Path,
    title: str,
    stem: str,
    root: str | Path = "experiments",
) -> list[Path]:
    """Grouped thin bars: FAR per store, one group per model family / domain."""
    plt = _plt()
    fams = list(experiments)
    data: dict[str, dict[str, float]] = {}
    for fam, exp in experiments.items():
        by: dict[str, list[float]] = defaultdict(list)
        for r in collect(Path(root) / exp / "results"):
            by[r["backend"]].append(r["FAR"])
        data[fam] = {b: _nanmean(v) for b, v in by.items()}
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    n = len(stores)
    width = 0.8 / n
    for i, s in enumerate(stores):
        xs = [j + (i - (n - 1) / 2) * width for j in range(len(fams))]
        ys = [data[f].get(s, float("nan")) for f in fams]
        ax.bar(
            xs,
            ys,
            width=width * 0.86,
            color=COLORS.get(s, INK2),
            label=LABELS.get(s, s),
            linewidth=0,
        )
        for x, y in zip(xs, ys, strict=True):
            if not math.isnan(y):
                ax.text(
                    x, y + 0.012, f"{y:.2f}", ha="center", va="bottom", fontsize=6.5, color=INK2
                )
    ax.set_xticks(range(len(fams)))
    ax.set_xticklabels(
        [f.replace(", ", ",\n").replace("-2.5-", "-2.5-\n") for f in fams], fontsize=7.5, color=INK2
    )
    ax.set_ylim(0, 0.9)
    _style(ax, "", "false-authority rate", title, pad=22)
    ax.grid(False, axis="x")
    ax.legend(
        fontsize=7,
        frameon=False,
        ncol=4,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        labelcolor=INK2,
    )
    return _save(fig, out, stem)


def fig_decay_sweep(results_dir: str | Path, out: Path, title: str, stem: str) -> list[Path]:
    """FAR vs decay aggressiveness, one line per store, direct-labelled at the right end."""
    plt = _plt()
    by: dict[str, list[dict]] = defaultdict(list)
    for g in aggregate(collect(results_dir)):
        by[g["backend"]].append(g)
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    ends: list[tuple[float, str]] = []
    for b, gs in by.items():
        gs = sorted(gs, key=lambda g: g["aggressiveness"] or 0)
        xs = [g["aggressiveness"] for g in gs]
        ys = [g["FAR"] for g in gs]
        ax.plot(
            xs,
            ys,
            color=COLORS.get(b, INK2),
            linewidth=2,
            marker="o",
            markersize=4,
            markerfacecolor=SURFACE,
            markeredgewidth=1.6,
        )
        ends.append((ys[-1], LABELS.get(b, b)))
    _end_labels(ax, 1.0, ends, gap=0.06)
    ax.set_xlim(-0.03, 1.6)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    _style(ax, "decay aggressiveness", "false-authority rate", title)
    return _save(fig, out, stem)


def fig_frontier(results_dir: str | Path, out: Path, title: str, stem: str) -> list[Path]:
    """Utility vs authority fidelity, one curve per store over decay levels; legend + the
    two extreme aggressiveness values annotated."""
    plt = _plt()
    by: dict[str, list[dict]] = defaultdict(list)
    for g in aggregate(collect(results_dir)):
        by[g["backend"]].append(g)
    fig, ax = plt.subplots(figsize=(4.8, 3.6))
    for b, gs in by.items():
        gs = sorted(gs, key=lambda g: g["aggressiveness"] or 0)
        xs = [g["utility"] for g in gs]
        ys = [g["fidelity"] for g in gs]
        ax.plot(
            xs,
            ys,
            color=COLORS.get(b, INK2),
            linewidth=1.6,
            marker="o",
            markersize=5.5,
            markerfacecolor=COLORS.get(b, INK2),
            markeredgecolor=SURFACE,
            markeredgewidth=1.2,
            label=LABELS.get(b, b),
        )
        for g, x, y in zip(gs, xs, ys, strict=True):
            if g["aggressiveness"] in (0.0, 1.0):
                ax.annotate(
                    f"a={g['aggressiveness']:.0f}",
                    (x, y),
                    xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=6.5,
                    color=INK2,
                )
    ax.set_xlim(0, 1.02)
    ax.set_ylim(-0.03, 1.06)
    _style(ax, "utility composite (KUA, SSR, 1 − REGRESS)", "authority fidelity (1 − FAR)", title)
    ax.legend(fontsize=7, frameon=False, loc="lower right", labelcolor=INK2)
    return _save(fig, out, stem)


def fig_depth(
    experiments: dict[str, str], out: Path, title: str, stem: str, root: str | Path = "experiments"
) -> list[Path]:
    """Small multiples: prohibition compliance by depth bin, one panel per model."""
    plt = _plt()
    labels = [f"{lo}–{hi - 1}" if hi < 10**9 else f"{lo}+" for lo, hi in COARSE_BINS]
    fig, axes = plt.subplots(
        1, len(experiments), figsize=(3.3 * len(experiments), 3.0), sharey=True
    )
    if len(experiments) == 1:
        axes = [axes]
    for k, (ax, (fam, exp)) in enumerate(zip(axes, experiments.items(), strict=True)):
        pooled: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for r in collect(Path(root) / exp / "results"):
            for depth, comp in r.get("pcd") or []:
                if comp is None or (isinstance(comp, float) and math.isnan(comp)):
                    continue
                for i, (lo, hi) in enumerate(COARSE_BINS):
                    if lo <= int(depth) < hi:
                        pooled[r["backend"]][i].append(comp)
        ends: list[tuple[float, str]] = []
        for b, curve in pooled.items():
            ys = [_nanmean(curve.get(i, [])) for i in range(len(COARSE_BINS))]
            ax.plot(
                range(len(labels)),
                ys,
                color=COLORS.get(b, INK2),
                linewidth=2,
                marker="o",
                markersize=4,
                markerfacecolor=SURFACE,
                markeredgewidth=1.6,
            )
            short = LABELS.get(b, b).replace("type-blind ", "").replace(" (pinned only)", "")
            ends.append((ys[-1], short))
        _end_labels(ax, len(labels) - 1, ends, gap=0.075, dx=4, size=6.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7, rotation=25)
        ax.set_ylim(-0.03, 1.05)
        ax.set_xlim(-0.3, len(labels) + 1.4)
        _style(ax, "ticks since the DENY", "compliance" if k == 0 else "", fam)
    fig.suptitle(title, color=INK, fontsize=10, x=0.02, ha="left")
    fig.subplots_adjust(top=0.78, wspace=0.10)
    return _save(fig, out, stem)


def make_all(
    root: str | Path = "experiments", out: str | Path = "paper/figures"
) -> list[Path]:
    root, out = Path(root), Path(out)
    paths: list[Path] = []
    paths += fig_far_by_family(
        {
            "gpt-4o-mini": "h3_live",
            "gemini-2.5-flash-lite": "h3_live_gemini",
            "qwen3-coder-30b": "h3_live_qwen",
            "claude-sonnet-5": "h3_live_frontier",
            "gpt-4o-mini, procurement": "h3_proc_live",
        },
        ["flat_ebbinghaus", "labels_notypes", "thsm_nogate", "thsm"],
        out,
        "False authority by store, four model families and two domains",
        "fig1_far_by_family",
        root,
    )
    paths += fig_decay_sweep(
        root / "h1_live" / "results",
        out,
        "Decay drives creep in type-blind memory (gpt-4o-mini, 15 seeds)",
        "fig2_decay_sweep",
    )
    paths += fig_frontier(
        root / "h1_live" / "results",
        out,
        "Utility–authority frontier under decay (gpt-4o-mini)",
        "fig3_frontier",
    )
    paths += fig_depth(
        {
            "gpt-4o-mini": "h4_live",
            "gemini-2.5-flash-lite": "h4_live_gemini",
            "qwen3-coder-30b": "h4_live_qwen",
        },
        out,
        "Prohibition compliance decays with depth for time-based memory",
        "fig4_depth",
        root,
    )
    return paths
