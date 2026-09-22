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

Dev: `uv sync` then `uv run pytest`; lint with `uv run ruff check .`.
Run: `uv run python -m decaymem.runner --config configs/<name>.yaml`, then
`uv run python -m decaymem.report --experiment <name>` for the table and frontier plot.
Zero-cost configs: `smoke_dryrun`, `gen_dryrun`, `h1_dryrun`, `h3_dryrun`. Live configs:
`smoke_anthropic` (needs `uv sync --extra anthropic` and Anthropic credentials) and
`smoke_openrouter` (needs `OPENROUTER_API_KEY`). Results land in `experiments/<name>/results/`.
