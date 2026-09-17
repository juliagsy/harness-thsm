# 04 · Roadmap, risks, open decisions

## Phases

| Phase | Weeks | Deliverable | Exit criterion |
|---|---|---|---|
| 0 Foundations | 1 | Repo skeleton, `core/` schemas, label lattice, effective-authority function, invariant checker, unit tests | Invariants I1–I6 pass on hand-written stores and fail on hand-written violations |
| 1 Pipeline | 2–3 | Coding-harness environment, scenario generator v0, deterministic grader, `flat_vector` + `flat_ebbinghaus`, `anthropic` + `cached` providers, dry-run provider | One end-to-end run on a 200-event scenario produces both scorecards at zero and nonzero cost |
| 2 THSM | 4–5 | `thsm` backend, typed writer, deterministic authz gate, pinned compaction, `actr` and `memory_worth` decay, `openai_compat` provider | H1 and H3 configs run on 5 seeds with a small model; frontier plot renders |
| 3 Matrix + ablations | 6 | Full matrix, 2x2 ablation for H5, capability-stripped skills for H6, `PCD(d)` curves for H4, frontier-model confirmation runs | Pre-registered hypotheses each have a result table |
| 4 External + case study | 7–8 | `mem0`/`letta` adapters, procurement domain, ConstraintRot and Laundering replication subsets, `claude_code_files` case study, scenario dataset release | Paper draft with figures |

Phase 0 and 1 are the ones to start with; nothing later depends on decisions still
open below.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Model call cost across the matrix | Response cache, small-model sweeps, probe-only inference, dry-run provider. Rough v1 sweep: 4 backends × 5 decay levels × 5 seeds × ~220 calls ≈ 22k calls with a small model |
| Synthetic scenarios judged unrealistic | Coding-harness domain grounded in real tool surfaces; replication subsets of three published benchmarks; real-harness case study |
| LLM-judge noise leaks into authority metrics | Authority axis is graded from tool calls only; judge used solely for belief parsing, with a calibration set |
| THSM "wins by construction" is seen as trivial | The finding is the frontier, not THSM's zero: how much utility the exemption costs, and how badly type-blind decay creeps. Off-diagonal ablations show which component does the work |
| Providers refuse or behave differently on authority probes | Report per model; probes are phrased as ordinary work requests, not red-team prompts |
| Generator bugs produce inconsistent ground truth | Event log is validated by the same invariant checker before any run |

## Open decisions (do not block Phase 0–1)

1. **Primary sweep model.** Cheapest model with reliable tool calling across the
   providers we include. Decide at end of Phase 1 from a 3-model smoke test.
2. **Grant expiry default.** Principal-set only (v1 plan) versus a default TTL.
   Run both as an ablation in Phase 3.
3. **Writer cadence.** Every N events versus at session boundaries. Both are knobs;
   pick the default from Phase 1 cost data.
4. **Whether `OBLIGE` gets its own retrieval rule.** Decide after H4 data.
5. **Procurement domain scope.** Full second domain versus a thin replication of the
   Laundering paper's setup. Decide in Phase 3 based on time.

## Immediate next steps once the plan is approved

1. Initialize the repo (`uv init`, `pytest`, pre-commit), commit these docs.
2. Write `core/` schemas and the invariant checker with tests (Phase 0).
3. Write the coding-harness mock environment and a 200-event hand-authored scenario
   that exercises every event kind, before automating the generator.
