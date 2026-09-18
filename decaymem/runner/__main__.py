import argparse
import math

from decaymem.runner.config import load_config
from decaymem.runner.run import run_matrix


def _fmt(v: float) -> str:
    return "  -  " if isinstance(v, float) and math.isnan(v) else f"{v:5.2f}"


def main() -> None:
    from decaymem.dotenv import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser(prog="decaymem.runner")
    ap.add_argument("--config", required=True)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    import sys

    results = run_matrix(
        cfg,
        write=not args.no_write,
        progress=lambda i, n, r: print(f"[{i}/{n}] {r.name}", file=sys.stderr),
    )
    ukeys = ["KUA", "STALE", "SSR", "REGRESS"]
    akeys = ["FAR", "RSR", "GEN", "PROHIB_FAIL", "LRR", "PCV"]
    print(f"{'run':60} " + " ".join(f"{k:>7}" for k in ukeys + akeys) + "   CLAIMS INV calls")
    for r in results:
        sc = r.scorecard
        row = [sc.utility.get(k, float("nan")) for k in ukeys] + [
            sc.authority.get(k, float("nan")) for k in akeys
        ]
        print(
            f"{r.name[:60]:60} "
            + " ".join(f"{_fmt(v):>7}" for v in row)
            + f"   {sc.counts.get('CLAIMS', 0):6} {sc.counts.get('INV', 0):3} "
            f"{r.manifest['usage']['calls']:5}"
        )
    if results and results[0].out_path:
        from pathlib import Path

        from decaymem.report.frontier import collect, summary_table

        print()
        print(summary_table(collect(Path(results[0].out_path).parent)))


if __name__ == "__main__":
    main()
