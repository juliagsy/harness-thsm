import argparse
from pathlib import Path

from decaymem.report.frontier import (
    authority_table,
    collect,
    frontier_plot,
    pcd_coarse_table,
    pcd_table,
    summary_table,
)


def main() -> None:
    ap = argparse.ArgumentParser(prog="decaymem.report")
    ap.add_argument("--experiment", help="name under experiments/")
    ap.add_argument("--root", default="experiments")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument(
        "--laundering",
        nargs="+",
        metavar="EXP",
        help="print the CLAIMS-vs-FAR split across these experiments and exit",
    )
    args = ap.parse_args()
    if args.laundering:
        from decaymem.report.frontier import laundering_table

        print(laundering_table(args.root, args.laundering))
        return
    if not args.experiment:
        raise SystemExit("--experiment or --laundering is required")
    results = Path(args.root) / args.experiment / "results"
    rows = collect(results)
    if not rows:
        raise SystemExit(f"no results under {results}")
    print(summary_table(rows))
    print()
    print(authority_table(rows))
    print()
    print(pcd_table(rows))
    print()
    print(pcd_coarse_table(rows))
    if not args.no_plot:
        out = frontier_plot(
            rows,
            Path(args.root) / args.experiment / "frontier.png",
            title=f"{args.experiment}: utility vs authority",
        )
        print(f"\nplot -> {out}")


if __name__ == "__main__":
    main()
