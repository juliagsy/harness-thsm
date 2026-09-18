# 03 · Plugin experiment layer

Goal: run the dual benchmark against **any existing LLM** and **any memory backend**
with one config file, deterministic replay, and cached model calls. The layer is
model-agnostic and harness-agnostic; THSM is one plugin among the backends.

## 1. Interfaces

All plugins are small Python protocols registered by entry-point name. A run is a
composition of one instance of each.

| Plugin | Responsibility | v1 implementations |
|---|---|---|
| `ModelProvider` | Chat completion with tool calling; returns text + structured tool calls; reports token usage | `anthropic` (Messages API), `openai_compat` with presets `openrouter`, `openai`, `ollama`, `vllm` (any OpenAI-shaped chat-completions endpoint; OpenRouter gives one key for many vendors' models), `scripted` (deterministic zero-cost stand-in), `cached` (wraps any provider) |
| `MemoryBackend` | Implements `admit`, `decay`, `consolidate`, `compact`, `retrieve`, `supersede`, `authorize`, `snapshot` | `flat_vector`, `flat_ebbinghaus`, `flat_actr`, `flat_memworth`, `typed_nolabels`, `labels_notypes`, `thsm` |
| `DecayPolicy` | `activation(entry, now) -> float` and `on_access(entry)` | `none`, `ebbinghaus`, `actr`, `memory_worth`, `budget_evict` |
| `ConsolidationPolicy` | When and how to merge/summarize; returns new entries with provenance | `never`, `on_cap`, `every_n_events`, `gated` (only after validation) |
| `CompactionPolicy` | Context-window compaction; may pin entries | `truncate`, `llm_summary`, `llm_summary_pinned` |
| `RetrievalPolicy` | Scoring and selection into context | `topk_cosine`, `topk_activation`, `topk_activation_pinned_deon` |
| `Writer` | Turns recent EPI events into SEM/PROC/DEON candidates | `llm_freeform` (one prompt, untyped output), `llm_typed` (JSON lines, one object per entry; labelled DERIVED by L1). The deterministic deontic channel (permission events → PRINCIPAL DEON entries) lives in the THSM backend's `admit_event`, not in a writer |
| `AuthorizationGate` | Decides whether a proposed tool call executes | `model_decides` (baseline: no gate), `deon_deterministic` |
| `Environment` | Deterministic tools with recorded traces and scripted outputs | `coding_harness`, later `procurement` |
| `ScenarioSource` | Yields events and probes | `generator` (seeded), `replay` (from JSONL) |
| `Grader` | Computes metrics from traces, store snapshots, and ground truth | `deterministic`, `llm_judge` (belief parsing only) |
| `Embedder` | Optional vectors for retrieval | `local_minilm`, `provider_embeddings`, `hash_bow` (no-dependency fallback) |

The `Writer` is deliberately separate from the `MemoryBackend` because the writer is the
laundering vector under test; we want to swap writers while holding the store fixed.

## 2. Module layout

    decay-mem/
      docs/                     this plan
      decaymem/
        core/                   Event, Entry, Label lattice, Type enum, Scope predicates,
                                effective-authority computation, invariant checker
        providers/              ModelProvider implementations + response cache
        memory/                 MemoryBackend implementations
        policies/               decay, consolidation, compaction, retrieval, authz
        writers/                freeform, typed, rule_based
        envs/                   coding_harness (mock fs, mock shell, git, deploy)
        scenarios/              generator, probe scheduler, JSONL replay
        grading/                metric implementations, judge prompts, calibration set
        runner/                 config loading, matrix expansion, run loop, manifests
        adapters/               (phase 4) mem0, letta/memgpt, zep; claude_code_files
        report/                 Pareto plots, tables, per-run drilldown
      configs/                  YAML experiment definitions
      experiments/              one folder per registered experiment: config + results
      data/scenarios/           generated JSONL event logs (seeded)
      tests/                    unit tests for core, invariants, envs, graders

Stack: Python 3.12, `uv` for env, `pydantic` schemas, SQLite for the event log and
store snapshots (inspectable with any client), `numpy` for activation math,
`pyarrow` for results, `matplotlib` for plots, `pytest`. No framework dependency
(no LangChain etc.) so the loop is fully visible.

## 3. Run loop

    for event in scenario:
        env.apply(event)                          # ground truth advances
        backend.admit(event)                      # EPI append; writer may fire
        if writer.due(): backend.admit_many(writer.write(recent_epi))
        backend.decay(now)
        if consolidation.due(): backend.consolidate()
        if event.kind == compaction_trigger: context = compaction.compact(context)
        if event.is_probe:
            ctx = retrieval.select(backend, event.query, context)
            reply = provider.complete(system + ctx + event.query, tools=env.tools)
            for call in reply.tool_calls:
                if authz.allow(call, backend): env.execute(call)
                else: env.record_refusal(call)
            grader.record(event, reply, env.trace, backend.snapshot())
        invariants.check(backend)                 # log violations with operator name

Every step writes to the run's SQLite file, so any turn can be reconstructed
afterwards.

## 4. Configuration

One YAML per experiment; lists expand into a matrix.

    name: h1_decay_causes_creep
    scenario: { source: generator, domain: coding_harness, horizon: 1000, seeds: [0,1,2,3,4] }
    provider: { name: anthropic, model: claude-sonnet-5, temperature: 0, cache: true }
    backend: [flat_ebbinghaus, flat_actr, flat_memworth, thsm]
    decay:   { aggressiveness: [0.0, 0.25, 0.5, 0.75, 1.0] }
    writer:  llm_freeform
    consolidation: on_cap
    compaction: llm_summary
    authz: model_decides         # overridden to deon_deterministic by thsm
    probes: { every_n_events: 50, around_compaction: true }
    budget: { max_store_entries: 500 }

The runner writes `manifest.json` (resolved config, git hash, provider versions, cache
hit rate, cost) next to results.

## 5. Reproducibility and cost control

- **Response cache** keyed by hash of (provider, model, params, full message list,
  tools). Re-running an experiment after a grader fix costs nothing.
- **Temperature 0** everywhere; seeds control the generator, not the model.
- **Two-tier sweeps.** Sweep the matrix with a small model, confirm the frontier on
  the headline configs with frontier models. Report both.
- **Probe-only inference.** Non-probe events do not call the model except through the
  `Writer`, whose cadence is a knob. A 1000-event run at writer cadence 10 and probes
  every 50 is roughly 100 writer calls plus about 120 probe calls.
- **Dry-run mode** replays a scenario with a scripted provider to test the pipeline at
  zero cost.

## 6. Status (Phase 2)

Implemented: all providers above except `anthropic` has not yet been exercised live;
backends `flat_vector`, `flat_ebbinghaus`, `flat_actr`, `flat_memworth`, `thsm`,
`thsm_nopin`, `thsm_nogate`, `typed_nolabels`, `labels_notypes`; decay policies `none`,
`ebbinghaus`, `actr`, `memory_worth` with one `aggressiveness` sweep knob; writers
`llm_freeform`, `llm_typed`; compaction `truncate`, `llm_summary`, `llm_summary_pinned`
(constraint pinning); the scripted provider's `naive`, `memory_aware`, `refuse_all`
policies; `decaymem.report` for the summary table and frontier plot. Config `sweep:`
expands backends × parameter grids. Phase 3 added `S-revoked` and `A-belief` probes with generator knobs
(`early_deny`, `denied_weight`, `task_revoke_prob`, `belief_every`,
`belief_after_compaction`) and runner overrides `--model/--name/--seeds/--jobs`. Phase 4 added the
procurement domain (`envs/procurement.py`, `scenarios/domains/`). Not yet: third-party
memory adapters.

## 7. Running existing systems through it

Third-party memory systems plug in as `MemoryBackend` adapters that ignore operators
they do not support (they report `unsupported`, which the grader records). A
`claude_code_files` adapter loads a real harness's instruction file, auto-memory
directory, and permission settings as a store snapshot so the invariant checker and
`CLAIMS` metric can be run over real harness state as a case study.
