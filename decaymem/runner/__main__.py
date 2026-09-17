import argparse
import math

from decaymem.runner.config import load_config
from decaymem.runner.run import run_matrix


def _fmt(v: float) -> str:
    return "  -  " if isinstance(v, float) and math.isnan(v) else f"{v:5.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(prog="decaymem.runner")
    ap.add_argument("--config", required=True)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    results = run_matrix(cfg, write=not args.no_write)
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
        if r.out_path:
            print(f"  -> {r.out_path}")


if __name__ == "__main__":
    main()
