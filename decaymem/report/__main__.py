import argparse
from pathlib import Path

from decaymem.report.frontier import collect, frontier_plot, summary_table


def main() -> None:
    ap = argparse.ArgumentParser(prog="decaymem.report")
    ap.add_argument("--experiment", required=True, help="name under experiments/")
    ap.add_argument("--root", default="experiments")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    results = Path(args.root) / args.experiment / "results"
    rows = collect(results)
    if not rows:
        raise SystemExit(f"no results under {results}")
    print(summary_table(rows))
    if not args.no_plot:
        out = frontier_plot(
            rows,
            Path(args.root) / args.experiment / "frontier.png",
            title=f"{args.experiment}: utility vs authority",
        )
        print(f"\nplot -> {out}")


if __name__ == "__main__":
    main()
