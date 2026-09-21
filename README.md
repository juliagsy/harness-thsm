# harness-thsm

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
prohibitions too. Phases 3 and 4 have run twenty-seven live experiments across four model families
(gpt-4o-mini, gemini-2.5-flash-lite, qwen3-coder-30b, claude-sonnet-5) and two domains
(coding harness, procurement) and one external memory system (Mem0) for about $27: THSM at zero false authority in roughly 800
cells at utility within ±0.05 of type-blind stores; pinned constraints alone leave 20–60%
false authority; revoked skills are executed 39–97% of the time from type-blind memory on every model and
66–92% even with the revocation pinned on the smaller models (3% on claude-sonnet-5);
models state the authority state correctly and act against it; labels alone hurt; types
alone violate the invariants; compaction is not the main erosion path once memory persists; Mem0 as an external store
sits between the type-blind baseline and THSM (39% false authority). The utility half is
additionally validated on Continual-ARC, an external skill-retention benchmark: decay is
free when it evicts nothing and costs 12 score points when it does, and only power-law
(ACT-R) activation evicts under realistic recurrence.
Details and open items in the results log. Read the docs in order.

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
| [docs/05-results-log.md](docs/05-results-log.md) | Every live experiment, its tables and its reading |
| [paper/](paper/) | Preprint: `draft.md` is the text, LaTeX is generated from it (`make pdf`) |
