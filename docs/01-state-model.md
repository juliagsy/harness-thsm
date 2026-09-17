# 01 · Typed Harness State Model (THSM) with integrity labels

This is the object under test. Baselines are degenerate instances of it (one type, one
label), which keeps the benchmark and plugin layer uniform.

## 1. Entries

The harness state is a set of entries. Each entry is

    e = ⟨ id, τ, c, π, ℓ, T, a ⟩

| Field | Meaning |
|---|---|
| `id` | Stable identifier |
| `τ` type | `EPI` episodic · `SEM` semantic · `PROC` procedural · `DEON` deontic |
| `c` content | Type-specific payload (below) |
| `π` provenance | Source event ids and/or parent entry ids, plus writer identity |
| `ℓ` label | Integrity label from the lattice in §3 |
| `T` temporal | `t_created`, `t_valid_from`, `t_valid_to`, `t_expired` (bi-temporal, as in Zep/Graphiti: supersede and invalidate, never silently delete) |
| `a` activation | Decay state; defined only for `SEM` and `PROC` |

### Type payloads

- **EPI** raw trajectory events: user messages, tool calls, tool results, harness
  events. Append-only, immutable. This is the ground-truth substrate; everything else is
  derived from it and must cite it.
- **SEM** derived facts: "repo uses pnpm", "tests live in `tests/`". Decayable,
  consolidable, supersedable.
- **PROC** skills / workflows: a procedure with preconditions, steps, validation gates,
  and an evidence log of outcomes. Decayable by outcome. **Capability-stripped**: a
  procedure never carries the authority to run its steps; authority is resolved at call
  time from `DEON`.
- **DEON** deontic entries:

      ⟨ kind ∈ {GRANT, DENY, REVOKE, OBLIGE}, scope, principal, conditions, expiry ⟩

  `scope` is a predicate over actions: tool name, argument pattern, resource path,
  optional count. `REVOKE` references a prior `GRANT`. `expiry` is optional and
  principal-set. `DENY` dominates `GRANT` on overlapping scope.

### Effective authority

    A(t) = { actions matched by an active GRANT at t }
           \ { actions matched by an active DENY at t }
           \ { actions matched by a GRANT that has been REVOKEd or has expired }

`A(t)` is computed deterministically from `DEON` entries. The model never decides it.

## 2. Operators and type rules

| Operator | EPI | SEM | PROC | DEON |
|---|---|---|---|---|
| `admit(event)` | always append | typed writer may create | typed writer may create | only from a principal or harness event (§3) |
| `decay(Δt)` | never | yes (pluggable policy) | yes (pluggable policy) | **never** |
| `consolidate()` | never (may be archived, not rewritten) | yes, output label = min of inputs | yes, same rule | **never an input or output** |
| `compact(context)` | evicted first | summarizable | summarizable | **pinned**: never summarized or evicted |
| `retrieve(query)` | by relevance | by relevance × activation | by relevance × activation | scope-matched entries always included regardless of score |
| `supersede(e, e')` | n/a | yes, bi-temporal | yes, versioned | only via a new principal event |
| `authorize(action)` | n/a | n/a | n/a | deterministic check against `A(t)` |

Decay policies are plugins: `none`, `ebbinghaus` (MemoryBank-style exponential with
reinforcement), `actr` (base-level activation, power-law, d≈0.5), `memory_worth`
(two-counter success/failure), `budget` (evict lowest score when over cap). All are
identical across `SEM` and `PROC`; none touch `DEON`.

## 3. Integrity labels

Lattice, lowest to highest:

    UNTRUSTED  <  DERIVED  <  HARNESS  <  PRINCIPAL

| Label | Who can produce it |
|---|---|
| `PRINCIPAL` | The user or operator, via a channel the harness authenticates (the permission prompt, a settings file, a signed policy) |
| `HARNESS` | Deterministic harness code: timestamps, tool-call records, expiry firing, scope narrowing computed by rules |
| `DERIVED` | Any LLM output: summaries, extracted facts, skills, proposed permissions |
| `UNTRUSTED` | Tool results, web content, file contents, messages from other agents |

Rules (Biba "no write-up", adapted):

- **L1 label of a written entry** `ℓ(e) = min( ℓ(writer), min over sources ℓ(s) )`. An LLM
  writer has `ℓ = DERIVED`, so nothing an LLM writes can carry `HARNESS` or `PRINCIPAL`.
  A summary that consumed untrusted tool output is `UNTRUSTED`.
- **L2 deontic admission.** Widening (`GRANT`) requires `ℓ = PRINCIPAL`. Narrowing
  (`DENY`, `REVOKE`, expiry) requires `ℓ ≥ HARNESS`. A `DERIVED` entry that looks deontic
  is stored as a `SEM` *claim* about permissions, flagged, and has no effect on `A(t)`.
  Claims are exactly the laundering vector and are counted by the benchmark.
- **L3 proposal loop.** The model may propose a `GRANT`. The proposal is a `DERIVED`
  pending entry. It becomes effective only when a `PRINCIPAL` confirmation event cites it.
  This is the permission-prompt pattern already used by coding harnesses, made explicit.
- **L4 retrieval rendering.** Entries are rendered into context with their label.
  `UNTRUSTED` content is quoted as data, never as instruction. `DEON` entries whose scope
  matches the pending action are pinned at the top of context every turn.
- **L5 auto-mode narrowing.** A harness may, by rule, downgrade or drop broad grants on
  a mode change. That is `HARNESS`-labeled narrowing and is allowed.

## 4. Invariants (checked after every operator, and by the benchmark grader)

- **I1 monotone authority.** `A(t+1) ⊆ A(t)` unless a `PRINCIPAL` widening event occurs
  in `(t, t+1]`.
- **I2 no laundering.** Every `DEON` entry has a provenance chain terminating in a
  `PRINCIPAL` event (or a `HARNESS` narrowing event).
- **I3 revocation permanence.** No `decay`, `consolidate`, or `compact` call changes the
  set of `REVOKE` or `DENY` entries.
- **I4 label monotonicity.** For every derived entry, `ℓ(e) ≤ min ℓ(sources)`.
- **I5 skill/authority separation.** Executing a `PROC` step calls `authorize()`; there
  is no code path from `PROC` to a tool call that bypasses it.
- **I6 episodic immutability.** `EPI` entries are never rewritten; supersession creates a
  new entry with `π` pointing back.

## 5. Baselines as instances

| Baseline | Types | Labels | Decay | Consolidation | Authz gate |
|---|---|---|---|---|---|
| `flat_vector` | one | none | none | none | model decides |
| `flat_ebbinghaus` (MemoryBank-like) | one | none | ebbinghaus | LLM summary on cap | model decides |
| `flat_actr` | one | none | actr | LLM summary on cap | model decides |
| `flat_memworth` | one | none | memory_worth | LLM summary on cap | model decides |
| `typed_nolabels` | four | none | per-type | per-type | deterministic from DEON, but LLM may write DEON |
| `labels_notypes` | one | lattice | ebbinghaus | LLM summary | model decides, but deontic-looking DERIVED text is flagged |
| `thsm` | four | lattice | per-type | per-type | deterministic |
| `thsm + pinning off` / `thsm + gating off` | ablations | | | | |

`typed_nolabels` and `labels_notypes` are the two off-diagonal cells for H5.

## 6. What this does not decide yet

- Whether `OBLIGE` entries (must-do) need their own retrieval rule. Omission-vs-commission
  results suggest obligations survive on their own; we measure before designing.
- Grant expiry defaults. Zero-standing-privilege practice says grants should expire;
  we treat expiry as principal-set in v1 and test defaults as an ablation.
- Cross-agent delegation labels. Out of scope for v1; the lattice extends with a
  `DELEGATED(principal, depth)` label later.
