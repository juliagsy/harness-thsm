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

Status: Phase 0 (foundations) complete: `decaymem/core/` holds the schemas, label lattice,
scope predicates, effective authority, deontic admission rules, and the I1–I6 invariant
checker, with 35 passing tests. Phase 1 (pipeline) is next. Read the docs in order.

Dev: `uv sync` then `uv run pytest`; lint with `uv run ruff check .`.

| Doc | Contents |
|---|---|
| [docs/00-research-brief.md](docs/00-research-brief.md) | Problem, gap in the literature, hypotheses to pre-register |
| [docs/01-state-model.md](docs/01-state-model.md) | Typed state, integrity label lattice, operators, invariants |
| [docs/02-dual-benchmark.md](docs/02-dual-benchmark.md) | Scenario generator, probes, metrics, grading |
| [docs/03-plugin-architecture.md](docs/03-plugin-architecture.md) | Interfaces, module layout, configs, run flow, reproducibility |
| [docs/04-roadmap.md](docs/04-roadmap.md) | Phases, milestones, risks, open decisions, cost model |
