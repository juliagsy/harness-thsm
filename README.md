# decay-mem

Research project: **harness decay without authority creep**.

Agent harnesses accumulate state across sessions: facts about the project, learned
skills and workflows, and permission decisions. Knowledge and skills go stale and should
decay. Permissions, prohibitions and revocations do not go stale in the same way, and
the machinery that decays and summarizes memory is exactly where prior work shows
authority gets fabricated or widened. This project builds:

1. A **typed harness state model with integrity labels** in which decay and
   consolidation apply only to knowledge and skills, and deontic state (grants, denies,
   revocations, obligations) changes only through provenance-backed events.
2. A **dual benchmark** that scores any memory configuration on two axes at once:
   utility under decay, and authority-state fidelity over long horizons.
3. A **generic plugin layer** so the same experiments run against any existing LLM
   (API or local) and any memory backend, including third-party ones, with cached,
   reproducible results.

Status: Phases 0–2 complete and the first live experiments are in (see
[docs/05-results-log.md](docs/05-results-log.md)). On gpt-4o-mini via OpenRouter, the
H3/H5 ablation and the H1 decay sweep both ran end to end for under a dollar. THSM holds
authority fidelity at 1.00 at every decay level while type-blind stores creep from about
0.50 false authority with no decay to 0.75–0.83 at full decay; the labels-only ablation
was the worst configuration because flagging all permission notes erodes the
prohibitions too. Phase 3 has run eleven live experiments across three model families (gpt-4o-mini,
gemini-2.5-flash-lite, qwen3-coder-30b) for about $3.60: THSM at zero false authority in
roughly 500 cells with equal or better utility; pinned constraints alone leave 27–60%
false authority depending on the model; revoked skills are executed 84–97% of the time
without a call-time gate; and the belief probe shows models stating the authority state
correctly while acting against it. Details and open items in the results log. Read the docs in order.

Dev: `uv sync` then `uv run pytest`; lint with `uv run ruff check .`.
Run: `uv run python -m decaymem.runner --config configs/<name>.yaml`, then
`uv run python -m decaymem.report --experiment <name>` for the table and frontier plot.
Zero-cost configs: `smoke_dryrun`, `gen_dryrun`, `h1_dryrun`, `h3_dryrun`. Live configs:
`smoke_anthropic` (needs `uv sync --extra anthropic` and Anthropic credentials) and
`smoke_openrouter` (needs `OPENROUTER_API_KEY`). Results land in `experiments/<name>/results/`.

| Doc | Contents |
|---|---|
| [docs/00-research-brief.md](docs/00-research-brief.md) | Problem, gap in the literature, hypotheses to pre-register |
| [docs/01-state-model.md](docs/01-state-model.md) | Typed state, integrity label lattice, operators, invariants |
| [docs/02-dual-benchmark.md](docs/02-dual-benchmark.md) | Scenario generator, probes, metrics, grading |
| [docs/03-plugin-architecture.md](docs/03-plugin-architecture.md) | Interfaces, module layout, configs, run flow, reproducibility |
| [docs/04-roadmap.md](docs/04-roadmap.md) | Phases, milestones, risks, open decisions, cost model |
