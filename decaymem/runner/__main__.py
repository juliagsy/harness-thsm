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
    ap.add_argument("--jobs", type=int, default=1, help="parallel cells (use 4-8 for live runs)")
    ap.add_argument("--model", help="override provider.model")
    ap.add_argument("--name", help="override experiment name (results dir)")
    ap.add_argument("--seeds", help="override seeds, comma-separated")
    ap.add_argument("--writer", help="override writer.name (llm_freeform | llm_typed)")
    ap.add_argument(
        "--compaction", help="override compaction (truncate | llm_summary | llm_summary_pinned)"
    )
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.model:
        cfg.provider["model"] = args.model
    if args.name:
        cfg.name = args.name
    if args.seeds:
        cfg.seeds = [int(x) for x in args.seeds.split(",")]
    if args.writer:
        cfg.writer["name"] = args.writer
    if args.compaction:
        cfg.compaction = args.compaction
    import sys

    results = run_matrix(
        cfg,
        write=not args.no_write,
        jobs=args.jobs,
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
