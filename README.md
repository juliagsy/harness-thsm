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

Status: Phase 2 (THSM) complete. `decaymem/core/` holds the typed state model and the
I1–I6 invariant checker. The plugin layer has type-blind baselines (`flat_vector`,
`flat_ebbinghaus`, `flat_actr`, `flat_memworth`), the THSM backend and its ablations
(`thsm`, `thsm_nopin`, `thsm_nogate`, `typed_nolabels`, `labels_notypes`), four decay
policies behind one `aggressiveness` knob, freeform and typed writers, pinned compaction,
and providers for Anthropic, any OpenAI-compatible endpoint (OpenRouter, OpenAI, Ollama,
vLLM presets) plus a zero-cost scripted agent. The H1 sweep (100 runs) and H3/H5 ablation
(30 runs) execute end to end and render the frontier plot, so far only with the scripted
agent: no live model has been run yet for lack of credentials in the dev environment.
Phase 3 (full matrix with real models) is next. Read the docs in order.

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
