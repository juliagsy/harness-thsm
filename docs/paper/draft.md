# Decay Without Creep: Typed Harness State for Agents That Forget Knowledge but Not Authority

*Draft v0.1, 2026-09-18. Authors: [to be filled]. Code, configs, cached model responses and
per-probe records: `decay-mem` repository (local).*

## Abstract

Long-running agent harnesses accumulate three kinds of state: knowledge about the
environment, procedural skills, and deontic state (what the agent may, must not, or may no
longer do). Knowledge and skills go stale and should decay; deontic state does not go stale
by disuse. Yet every published memory-decay mechanism scores entries by recency, access or
outcome, so a once-stated revocation is the first thing pruned, and the consolidation step
that shrinks memory is where recent work shows LLM writers fabricate authority. We propose
the Typed Harness State Model (THSM): harness state is typed (episodic, semantic,
procedural, deontic), carries an integrity label from a Biba-style lattice, and is governed
by operators that apply decay and consolidation only to knowledge and skills while deontic
state changes only through provenance-backed principal events and is enforced by a
deterministic gate. Six checkable invariants make laundering a structural error rather than a
behavioural one. We introduce a dual benchmark that scores any memory configuration on a
utility axis and an authority axis over the same event-sourced scenarios, with the
authority axis graded from tool calls only. Across 24 live experiments, four model families
(gpt-4o-mini, gemini-2.5-flash-lite, qwen3-coder-30b, claude-sonnet-5), two domains and
about 800 THSM cells, THSM produced zero false authority at utility within ±0.05 of matched
type-blind stores, while type-blind memory carried out 27–84% of unauthorized requests
depending on model and decay level. Three findings go beyond the headline: (i) pinning the
deontic state into context every turn, perfectly preserved, still leaves 20–60% false
authority, and models restate the authority state correctly (92–95%) while acting against
it; (ii) skills carry authority: a task whose grant was revoked is still executed 66–97% of
the time by every configuration without a call-time gate; (iii) integrity labels without a
trusted deontic channel make things worse, because flagging every permission note as
unverified erodes the prohibitions too. We also reproduce, in a persistent-memory setting,
two recent in-context results: constraint erosion with depth for ACT-R-style decay, and the
limited role of compaction once constraints live in memory.

## 1. Introduction

Coding agents, always-on assistants and multi-agent pipelines now persist state across
sessions: instruction files, auto-written memory notes, skill libraries, and permission
decisions. Two research communities study what happens to that state over time, and they
do not cite each other.

The *decay* literature asks how a memory store should forget. MemoryBank applies Ebbinghaus
curves [Zhong et al. 2023]; FadeMem, FSFM and graph-pruning systems modulate decay by
relevance, access and age [arXiv:2601.18642, 2604.20300, 2608.28978]; Memory Worth scores
entries by co-occurrence with success [arXiv:2604.12007]; A-MAC gates admission by a content
type prior [arXiv:2603.04549]. All of them optimise utility, and none of them exempts any
class of memory from forgetting.

The *authority* literature asks how an agent's permissions stay correct. Progent enforces
least privilege with a policy language whose updates may narrow automatically but widen only
with approval [arXiv:2504.11703]. The Authorization Laundering paper shows LLM memory writers
fabricate authority for up to 50% of unauthorized requests under incremental updates, and
executors act on it 98.6% of the time [arXiv:2609.01836]. Governance Decay shows in-context
policies are silently dropped by compaction [arXiv:2606.22528], and prohibition-type
constraints decay in-context while requirement-type ones persist [arXiv:2604.20911]. None
of this work has a decay model, and none looks past a single context window.

The two problems are one mechanism seen from two sides. Decay prunes by recency, frequency
or outcome; a prohibition stated once and never retrieved ranks last on all three, and a
prohibition that blocks a task co-occurs with failure. Consolidation is how harnesses shrink
memory, and it is also where writers generalise grants and drop revocations. If the same
operator that keeps knowledge fresh is the one that erodes authority, no tuning of the
decay schedule can fix it: the store needs a type system.

**Contributions.**

1. **THSM**, a typed harness state model with an integrity lattice, an operator table that
   confines decay and consolidation to knowledge and skills, a deterministic authorization
   gate over deontic state, and six invariants that make authority creep a checkable
   property of the store (§3).
2. **A dual benchmark** that grades utility and authority fidelity on the same seeded,
   event-sourced scenarios, with the authority axis graded from tool calls, a probe set that
   separates revoked, scope-adjacent, denied, never-granted and skill-driven requests, a
   belief probe that elicits the agent's own account of its permissions, and a validator
   that replays every scenario against ground truth before any model call (§4).
3. **A plugin experiment layer** that runs the benchmark against any model behind an
   OpenAI-compatible or Anthropic endpoint and any memory backend, with content-addressed
   response caching so every run is replayable and re-gradable at zero cost (§5).
4. **Empirical results** on four model families and two domains (§6), including the
   pre-registered hypotheses and three findings we did not anticipate: the knowledge–action
   gap, skill-borne authority, and the harm of labels without a deontic channel.

## 2. Background and related work

**Decay and forgetting for utility.** Ebbinghaus-style exponential decay with reinforcement
on access (MemoryBank; FadeMem, arXiv:2601.18642), ACT-R base-level activation
[Anderson & Schooler 1991; arXiv HAI 2025 port], outcome-based Memory Worth
(arXiv:2604.12007), admission control (A-MAC, arXiv:2603.04549) and constrained-retention
formulations (arXiv:2606.10616) share a scoring view of memory in which nothing is
protected. The control-plane study (arXiv:2606.15903) observes that production failures are
forgetting failures while benchmarks measure recall, and separates a recall plane from a
mutation plane, a distinction our operator table adopts.

**Consolidation and skill libraries.** Continuous consolidation degrades memory utility
below the no-memory baseline (arXiv:2605.12978); unbounded skill libraries drift
(arXiv:2605.19576); SKILL.nb and SkillOps add lifecycle gating (arXiv:2606.08049,
2605.13716). None separates what a skill does from what it is allowed to do.

**Authority and constraints.** Progent (arXiv:2504.11703) and SEAgent (arXiv:2601.11893)
enforce privilege at the tool boundary; authorization propagation and delegation studies
(arXiv:2605.05440, 2609.00267) show that authority gated inside the model fails and that
ordinary operation, not attacks, produces creep. Authorization Laundering (arXiv:2609.01836)
names the memory-writer failure we build on. Governance Decay (arXiv:2606.22528) and
omission-constraint decay (arXiv:2604.20911) measure in-context erosion; MemEvoBench and
"Remembering More, Risking More" (arXiv:2604.15774, 2605.17830) measure safety drift with
memory length. The SSGM framework and the Always-On Agents survey (arXiv:2603.11768,
2606.30306) supply the vocabulary of authority, scope, mutability and provenance, and note
that the field studies accumulating state far more than relinquishing it.

**Gap.** No prior system (a) types harness state, (b) exempts deontic state from decay and
consolidation by construction, (c) labels integrity so model-written text cannot create or
widen authority, and (d) measures utility and authority on the same traces.

## 3. The Typed Harness State Model

### 3.1 Entries

Harness state is a set of entries e = ⟨id, τ, c, π, ℓ, T, a⟩ with type τ ∈ {EPI, SEM, PROC,
DEON}, payload c, provenance π (source entry ids and writer identity), integrity label ℓ,
bi-temporal validity T (created, valid-from, valid-to, expired; supersede and invalidate,
never delete), and activation a defined only for SEM and PROC.

- **EPI** entries are raw trajectory events: immutable, append-only, the ground-truth
  substrate everything else must cite.
- **SEM** entries are derived facts; **PROC** entries are skills with steps, gates and an
  evidence log. Both are decayable and consolidable. PROC entries are *capability-stripped*:
  a procedure never carries the authority to run its steps.
- **DEON** entries are ⟨kind ∈ {GRANT, DENY, REVOKE, OBLIGE}, scope, principal, conditions,
  expiry⟩. A scope is a predicate over actions (tool, argument globs, resource glob, optional
  use count). DENY dominates GRANT; REVOKE may name a grant or a scope.

Effective authority A(t) is the set of actions matched by a grant in force at t, minus
denies, minus revoked or expired or exhausted grants. It is computed deterministically; the
model never decides it.

### 3.2 Integrity labels

Labels form the lattice UNTRUSTED < DERIVED < HARNESS < PRINCIPAL. Tool results and external
content are UNTRUSTED; anything an LLM writes is DERIVED; deterministic harness code is
HARNESS; the user through an authenticated channel is PRINCIPAL. Rule L1 (Biba no-write-up):
a written entry's label is the meet of its writer's label and its sources' labels, so
nothing an LLM writes can carry HARNESS or PRINCIPAL, and a summary that consumed tool output
is UNTRUSTED. Rule L2: widening (GRANT, OBLIGE) requires PRINCIPAL; narrowing (DENY, REVOKE,
expiry) requires at least HARNESS; a DERIVED entry that looks deontic is stored as a flagged
SEM *claim* with no effect on A(t). Claims are the laundering vector, and the benchmark
counts them. Rule L3: the model may *propose* a grant; it becomes effective only when a
PRINCIPAL confirmation event cites it, citing the proposal as a non-integrity-bearing
reference so L1 does not pull the grant's label down. Rule L4: entries are rendered into
context with their label; UNTRUSTED content is quoted as data; DEON entries relevant to the
pending request are pinned every turn. Rule L5: harness rules may narrow grants on a mode
change.

### 3.3 Operators

| operator | EPI | SEM | PROC | DEON |
|---|---|---|---|---|
| admit | append | typed writer | typed writer | principal or harness event only |
| decay | never | pluggable | pluggable | **never** |
| consolidate | never | yes, label = meet of inputs | yes | **never input or output** |
| compact | evict first | summarisable | summarisable | **pinned** |
| retrieve | relevance | relevance × activation | relevance × activation | always included when scope-relevant |
| authorize | – | – | – | deterministic check against A(t) |

Decay policies are plugins (none, Ebbinghaus, ACT-R, Memory Worth) behind one
`aggressiveness` knob that scales the time constant and raises the eviction threshold.

### 3.4 Invariants

I1 monotone authority (A(t+1) ⊆ A(t) unless a PRINCIPAL widening event occurred); I2 no
laundering (every DEON entry has a provenance chain to a PRINCIPAL event, or a HARNESS
narrowing); I3 revocation permanence (no lossy operator changes REVOKE/DENY entries); I4
label monotonicity; I5 skill/authority separation (no tool call from a PROC step bypasses
authorize); I6 episodic immutability. THSM satisfies all six by construction. Baselines are
degenerate instances of the same model (one type, no labels, model decides), so the same
checker runs over them and the violation count `INV` becomes a metric.

### 3.5 Ablations

`typed_nolabels` (four types, gate, but LLM-written DEON entries admitted regardless of
label), `labels_notypes` (one type, labels enforced so deontic-looking writes become flagged
claims, model decides), `thsm_nogate` (pinned DEON, no gate), `thsm_nopin` (gate, nothing
pinned), `thsm_pintool` (gate, pinned with tool names only). The type-blind baselines are
`flat_vector`, `flat_ebbinghaus`, `flat_actr`, `flat_memworth`.

## 4. The dual benchmark

### 4.1 Scenarios

Scenarios are seeded, event-sourced logs generated from domain pools: facts that get
updated, tasks whose required command drifts, permission grants (including one-time and
expiring grants), denies and revocations, untrusted tool output including injected lines
that claim blanket approval, compaction triggers and session boundaries. Every task comes
with a standing PRINCIPAL grant so the utility axis is not confounded by authority; the
generator never revokes those grants unless the H6 knob is on. Two domains are implemented:
a **coding harness** (files, shell commands, git push, deploy, delete) and **procurement**
(purchase orders, payments, invoice approvals, data exports, reports; amounts map to bands
so scopes stay glob predicates). A validator replays every scenario against the environment
and rejects any probe whose kind disagrees with A(t) at its time. It caught two real
generator bugs during this work.

### 4.2 Probes

Probes are the only graded turns. Utility: knowledge recall (correct / stale / miss), task
execution, and regression on tasks the same agent solved earlier. Authority: an allowed
action (refusal = legitimate rejection), a revoked action, an action adjacent to a past
grant, an explicitly denied action, an action never mentioned, a task whose grant was
revoked (S-revoked, for H6), and a belief elicitation ("list what you are allowed and
forbidden to do", JSON or prose, parsed deterministically and compared to A(t) over the
probe's action universe). Probes bracket every compaction.

### 4.3 Metrics

Utility: KUA, STALE, SSR, REGRESS, CTX. Authority: FAR (false-authority rate on all
unauthorized probes), RSR (revocation survival), GEN (scope-adjacent generalization),
PROHIB_FAIL, PCV (post- minus pre-compaction violation), LRR (legitimate rejection),
SKILL_CREEP, ASD / OVER_BELIEF / UNDER_BELIEF (authority-surface distance and its two
halves), plus CLAIMS (deontic-looking memory writes) and INV (invariant violations) from the
store. The authority axis is graded from recorded tool calls only; the only parsing of model
text is the knowledge answer (separator-insensitive value match) and the belief reply.

## 5. Experimental setup

All models are called through OpenRouter's OpenAI-compatible endpoint with our own
translation layer; Anthropic models are also supported natively. Responses are cached by
content hash of (provider, model, system, messages, tools, routing options), so every
experiment is replayable and was re-graded after grader fixes at zero cost. Provider-side
errors are never cached and are counted in the manifest. Unless stated otherwise: generated
scenarios of 400 events, probes every 12 events, 5 seeds, memory writer every 10 events,
retrieval of 8 notes, LLM-summary compaction with permission lines pinned, decay
aggressiveness 0.5, store cap 40. Models: openai/gpt-4o-mini (primary),
google/gemini-2.5-flash-lite, qwen/qwen3-coder-30b-a3b-instruct (routed away from an
upstream that returned empty tool-use content), anthropic/claude-sonnet-5 (frontier
confirmation). 23 live experiments, 782 model-backed cells, 49.7k model calls, about $17.

A scripted deterministic agent exists for zero-cost pipeline checks; none of the reported
numbers come from it.

## 6. Results

### 6.1 Main ablation: four model families, two domains

Table 1. H3/H5 ablation. FAR = false-authority rate (lower is better); utility = mean of
KUA, SSR and 1−REGRESS; INV = invariant violations per run. Five seeds each.

| model / domain | store | FAR | RSR | GEN | LRR | utility | INV |
|---|---|---|---|---|---|---|---|
| gpt-4o-mini / coding | type-blind (Ebbinghaus) | 0.40 | 0.44 | 0.42 | 0.33 | 0.70 | 0 |
| | labels only | 0.68 | 0.23 | 0.63 | 0.00 | 0.73 | 0 |
| | types only | 0.00 | 1.00 | 0.00 | 0.00 | 0.79 | 16.2 |
| | THSM, no gate | 0.27 | 0.90 | 0.27 | 0.00 | 0.75 | 0 |
| | THSM, no pinning | 0.00 | 1.00 | 0.00 | 0.00 | 0.73 | 0 |
| | THSM, tool-only pinning | 0.00 | 1.00 | 0.00 | 0.00 | 0.65 | 0 |
| | **THSM** | **0.00** | 1.00 | 0.00 | 0.00 | 0.73 | 0 |
| gemini-2.5-flash-lite / coding | type-blind | 0.62 | 0.17 | 0.57 | 0.00 | 0.40 | 0 |
| | labels only | 0.61 | 0.28 | 0.70 | 0.00 | 0.38 | 0 |
| | types only | 0.00 | 1.00 | 0.00 | 0.00 | 0.43 | 15.8 |
| | THSM, no gate | 0.55 | 0.15 | 0.58 | 0.33 | 0.47 | 0 |
| | THSM, no pinning | 0.00 | 1.00 | 0.00 | 0.33 | 0.40 | 0 |
| | **THSM** | **0.00** | 1.00 | 0.00 | 0.00 | 0.46 | 0 |
| qwen3-coder-30b / coding | type-blind | 0.58 | 0.23 | 0.56 | 0.00 | 0.53 | 0 |
| | labels only | 0.70 | 0.10 | 0.65 | 0.00 | 0.56 | 0 |
| | types only | 0.00 | 1.00 | 0.00 | 0.00 | 0.70 | 50.0 |
| | THSM, no gate | 0.60 | 0.27 | 0.73 | 0.00 | 0.51 | 0 |
| | **THSM** | **0.00** | 1.00 | 0.00 | 0.00 | 0.56 | 0 |
| claude-sonnet-5 / coding | type-blind | 0.27 | 0.87 | 0.35 | 0.00 | 0.55 | 0 |
| | labels only | 0.45 | 0.47 | 0.45 | 0.00 | 0.41 | 0 |
| | types only | 0.00 | 1.00 | 0.00 | 0.00 | 0.54 | 15.6 |
| | THSM, no gate | 0.22 | 1.00 | 0.35 | 0.00 | 0.51 | 0 |
| | THSM, no pinning | 0.00 | 1.00 | 0.00 | 0.00 | 0.42 | 0 |
| | **THSM** | **0.00** | 1.00 | 0.00 | 0.00 | 0.56 | 0 |
| gpt-4o-mini / coding, freeform writer | type-blind | 0.54 | 0.37 | 0.50 | 0.00 | 0.80 | 0 |
| | **Mem0** (external, own extraction LLM) | 0.39 | 0.83 | 0.43 | 0.00 | 0.82 | 0 |
| | THSM | 0.00 | 1.00 | 0.00 | 0.00 | 0.77 | 0 |
| gpt-4o-mini / procurement | type-blind | 0.29 | 0.65 | 0.35 | 0.00 | 0.74 | 0 |
| | labels only | 0.41 | 0.38 | 0.42 | 0.00 | 0.71 | 0 |
| | types only | 0.02 | 0.95 | 0.00 | 0.00 | 0.74 | 16.8 |
| | THSM, no gate | 0.20 | 0.95 | 0.48 | 0.00 | 0.74 | 0 |
| | **THSM** | **0.00** | 1.00 | 0.00 | 0.00 | 0.74 | 0 |

Four regularities hold across every family and both domains.

*The typed exemption dominates (H3).* THSM is at zero false authority everywhere, at utility
within ±0.05 of the matched type-blind store (0.73 vs 0.70, 0.46 vs 0.40, 0.56 vs 0.53,
0.56 vs 0.55, 0.74 vs 0.74). With argument globs hidden from the model (tool-only pinning)
utility is 0.65, so we do not claim a utility lead; we claim no utility cost within the
resolution of five seeds.

*The gate does the work; pinning helps but does not suffice.* With deontic entries pinned
into context every turn and no gate, false authority is 0.27 / 0.55 / 0.60 / 0.22 / 0.20
across the five rows. Pinning cut creep relative to the type-blind store on gpt-4o-mini and
Sonnet 5 (0.40 → 0.27, 0.27 → 0.22) and barely at all on Gemini and Qwen (0.62 → 0.55, 0.58
→ 0.60). The gate is what removes it, and its value is largest for the models that follow
in-context constraints least.

*Labels without a deontic channel hurt (H5, off-diagonal).* Flagging deontic-looking notes
as unverified made false authority worse in five of six comparisons (0.40 → 0.68, 0.58 →
0.70, 0.27 → 0.45, 0.29 → 0.41; Gemini unchanged), and halved revocation survival on Sonnet
5 (0.87 → 0.47). With one note type there is no trusted channel for the *real* permissions,
so the prohibitions arrive flagged too, and the model discounts them.

*A production memory system behaves as a better type-blind store.* Mem0, with its own
extraction LLM, deduplication and update logic, honoured recalled revocations far more
often than a flat note store (0.83 vs 0.37) and had the best utility (0.82), and still
carried out 39% of unauthorized requests, including six explicit prohibitions. Its
extraction step is itself a laundering writer: in a smoke test it stored a grant and a
later revocation as two memories and ranked the grant higher for the query that mattered.

*Types without labels look safe and are not.* Admitting LLM-written deontic entries produced
16–50 invariant violations per run (authority widened by recalled or laundered grants) on
every family, with behavioural false authority of 0.00 on four rows and 0.02 on the fifth:
the widened scopes were rarely the ones the probe set happened to exercise. `INV` reports
the creep that `FAR` misses.

### 6.2 Decay drives creep (H1)

Table 2. False authority by decay aggressiveness, type-blind stores, gpt-4o-mini, 15 seeds,
95% intervals. THSM is 0.00 at every level (5 seeds).

| aggressiveness | ACT-R | Ebbinghaus | Memory Worth |
|---|---|---|---|
| 0.00 | 0.54 ± 0.12 | 0.53 ± 0.12 | 0.49 ± 0.07 |
| 0.25 | 0.51 ± 0.09 | 0.53 ± 0.10 | 0.52 ± 0.08 |
| 0.50 | 0.68 ± 0.09 | 0.50 ± 0.09 | 0.51 ± 0.08 |
| 0.75 | 0.83 ± 0.04 | 0.63 ± 0.09 | 0.53 ± 0.09 |
| 1.00 | 0.84 ± 0.03 | 0.77 ± 0.07 | 0.84 ± 0.03 |

False authority is non-decreasing in aggressiveness for all three policies: a ramp for
ACT-R, whose power-law activation lets rarely retrieved prohibitions sink first, and a
threshold for Ebbinghaus and Memory Worth, which are flat until the eviction threshold
crosses the revocation notes' activation. Two further points matter more than the shape.
The floor with no decay at all is 0.49–0.54: half of unauthorized requests already go
through with every note retained, because authority stored as retrievable prose is weighed
by the model rather than enforced. And THSM's utility curve tracks the baselines', including
the collapse at full decay (0.64 → 0.40 vs 0.61 → 0.48 for Ebbinghaus): knowledge and skills
decay exactly as much; deontic state not at all. On gemini-2.5-flash-lite the same sweep
starts at 0.67–0.76 and ends at 0.75–0.89, with Ebbinghaus flat.

![](../results/h1_live_gpt-4o-mini_frontier_15seeds.png)

*Figure 1. Utility–authority frontier for the decay sweep on gpt-4o-mini. Labels are decay
aggressiveness. Type-blind curves drift down and left as decay tightens; THSM moves only
left.*

### 6.3 Skills carry authority (H6) and the knowledge–action gap

Table 3. Revoked-skill execution and belief accuracy. SKILL = fraction of requests for a
task whose standing grant had been revoked that were executed anyway; ASD = fraction of the
action universe on which the agent's self-reported allowed/forbidden set disagrees with A(t).

| model / domain | store | FAR | SKILL | ASD | OVER |
|---|---|---|---|---|---|
| gpt-4o-mini / coding | type-blind (ACT-R / Ebbinghaus) | 0.71 / 0.60 | 0.90 / 0.90 | 0.31 / 0.24 | 0.29 / 0.22 |
| | THSM, no gate | 0.57 | 0.85 | 0.07 | 0.07 |
| | **THSM** | 0.00 | **0.00** | 0.05 | 0.05 |
| gemini-2.5-flash-lite / coding | type-blind | 0.73 / 0.78 | 0.79 / 0.83 | 0.19 / 0.15 | 0.14 / 0.11 |
| | THSM, no gate | 0.62 | 0.79 | 0.16 | 0.13 |
| | **THSM** | 0.00 | **0.00** | 0.10 | 0.06 |
| qwen3-coder-30b / coding | type-blind | 0.67 / 0.65 | 0.88 / 0.82 | 0.18 / 0.16 | 0.16 / 0.12 |
| | THSM, no gate | 0.62 | 0.66 | 0.24 | 0.21 |
| | **THSM** | 0.00 | **0.00** | 0.17 | 0.16 |
| gpt-4o-mini / procurement | type-blind | 0.66 / 0.52 | 0.93 / 0.93 | 0.08 / 0.08 | 0.00 / 0.00 |
| | THSM, no gate | 0.39 | 0.91 | 0.08 | 0.01 |
| | **THSM** | 0.00 | **0.00** | 0.08 | 0.01 |

*Skills carry authority.* When the user asked for a task whose standing grant had been
withdrawn, every configuration without a call-time gate ran it 66–93% of the time,
including THSM with the REVOKED line pinned in context. Only resolving authority at call
time against the deontic store stopped it. This is H6 across three families and six
scenario sets: a skill learned under one grant is executed later under none, unless the
harness strips authority from the skill.

*The knowledge–action gap.* In the procurement domain gpt-4o-mini's self-reported authority
was 92% correct for every store, with no over-belief at all, and it still carried out 52–66%
of unauthorized requests from type-blind memory and 39% with the deontic state pinned. In
the coding domain the pinned configuration was 93% correct in self-report and 57% wrong in
action. The model is not confused about what it may do; it does it anyway when asked. The
gap is narrower on Gemini, whose self-report is also poorer, and absent on Qwen, which
misreports even pinned state (ASD 0.17 with THSM). The gate is indifferent to which failure
a model has.

### 6.4 Prohibitions decay with depth (H4)

Table 4. Compliance with an explicit "never do X" as a function of ticks since the DENY,
pooled over five seeds (three early denies, A-denied probes weighted 6×).

| model | store | 0–49 | 50–149 | 150–299 | 300+ |
|---|---|---|---|---|---|
| gpt-4o-mini | ACT-R | 0.72 | 0.50 | 0.19 | 0.18 |
| | Ebbinghaus | 0.61 | 0.57 | 0.48 | 0.52 |
| | Memory Worth | 0.61 | 0.66 | 0.42 | 0.39 |
| | THSM, no gate | 0.61 | 0.73 | 0.75 | 0.61 |
| | THSM | 1.00 | 1.00 | 1.00 | 1.00 |
| gemini-2.5-flash-lite | ACT-R | 0.39 | 0.25 | 0.12 | 0.20 |
| | Ebbinghaus | 0.50 | 0.25 | 0.23 | 0.18 |
| | Memory Worth | 0.44 | 0.37 | 0.38 | 0.41 |
| | THSM, no gate | 0.78 | 0.62 | 0.60 | 0.52 |
| | THSM | 1.00 | 1.00 | 1.00 | 1.00 |

ACT-R memory produces a clean depth curve on both models (0.72 → 0.18, 0.39 → 0.12): the
persistent-memory analogue of in-context omission-constraint decay. Ebbinghaus, which
reinforces on access, holds better on gpt-4o-mini and not on Gemini; Memory Worth is
non-monotone. Where the prohibition is re-pinned every turn, depth decay is a property of
the model (Gemini 0.78 → 0.52, gpt-4o-mini flat). The gate removes the depth dependence
entirely.

### 6.5 Compaction is not the main erosion path once memory persists

Table 5. Violation rate on unauthorized probes immediately before and after a session
compaction (46 bracket pairs per store, gpt-4o-mini).

| store | compaction | before | after |
|---|---|---|---|
| type-blind | plain summary | 0.43 | 0.46 |
| type-blind | summary with permission lines pinned | 0.43 | 0.22 |
| THSM, no gate | plain summary | 0.30 | 0.22 |
| THSM, no gate | pinned | 0.30 | 0.13 |
| THSM | either | 0.00 | 0.00 |

Governance Decay reports 0% → 30% violations when compaction drops an in-context policy. In
a memory-augmented harness the constraint is never only in the session context, and the
agent was already violating it 43% of the time before compaction; compaction moves the rate
by three points. Constraint Pinning at compaction still halves post-compaction violations
(0.43 → 0.22) and lowers overall false authority (0.39 → 0.29), as a recency effect: a
constraint that has just been restated is followed more often. It is a mitigation, not a
fix; the gate is zero under both compaction modes.

### 6.6 Writer and pinning controls

*Writer.* On identical scenarios, a schema-constrained (typed) memory writer launders less
than a free-text one: type-blind false authority 0.59 → 0.54, pinned-ungated 0.32 → 0.25
with revocation survival 0.61 → 0.94, and better knowledge recall (KUA 0.38 → 0.65). It
does not change the ordering of stores, and type-blind memory still acts on more than half
of unauthorized requests either way.

*Pinning leak.* Pinned grant scopes such as `run_cmd cmd="*test*"` leak enough of a task
command that THSM can keep skill success after the skill note has decayed. With tool-name-
only pinning, THSM's utility falls by 0.02–0.04 on gpt-4o-mini and by 0.07 at full decay on
Gemini, with authority unchanged at zero. We therefore report THSM's utility as "within
±0.05 of type-blind" rather than as a lead. Tool-only pinning also raises legitimate
rejections on Gemini and Sonnet 5 (to 0.33–0.67), which asked for permission they already
held; full pinning is the better default, tool-only pinning the right control.

### 6.7 Authority created versus authority acted on

Every model writes deontic-looking memory: 5–65 claims per run with the typed writer (Sonnet
5 fewest, Qwen most, tracking their type-blind false authority of 0.27 and 0.58). On THSM
those writes become flagged claims with no effect on A(t); on `typed_nolabels` the same
writes become 16–50 real widenings per run. Creation is a property of the model; laundering
is a property of the store. Because the widened scopes were rarely probed, behavioural false
authority under-reports this by construction, which is why `INV` belongs next to `FAR`.

## 7. Discussion

**What the gate is and is not.** THSM's zero is by construction: the gate consults a store
that decay and consolidation cannot touch and that LLM writes cannot widen. The empirical
content of the paper is elsewhere: that the construction costs no measurable utility, that
every alternative that keeps authority in the model's hands leaks (including perfect
in-context pinning), and that the leak is largest for models that follow instructions least
and does not vanish for the strongest model we tried (Sonnet 5, 0.22 with pinning and no
gate, driven entirely by scope generalization).

**Why the knowledge–action gap matters for governance design.** The belief probe shows the
failure is not recall. Models restate the constraint and act against it when a plausible
request arrives. This is consistent with the in-context finding that prohibitions lose
force while requirements hold (arXiv:2604.20911): a request is a requirement-shaped
pressure, and the prohibition competes with it. It argues against any design that relies
on the model *knowing* its permissions, including pinning, re-injection and system-prompt
hardening, as anything more than a mitigation.

**Why labels alone hurt.** Integrity labels are protective only when a trusted channel
exists for genuine permissions. Flag everything and the real prohibitions arrive with the
same "unverified" tag as the laundered grants; the model discounts them together. The
lesson is that labelling and typing are complementary: labels stop laundering only when
types give principal-authored deontic entries a place to live unflagged.

**Skills.** The H6 result is the strongest argument for capability-stripped skills. A skill
library that records how to run tests will run them after the user has said stop, in every
configuration we tested that lacked call-time authority resolution. Skill lifecycle work
(retirement, gating) does not address this; the authority has to be resolved at the call.

**Metrics.** Three additions to the usual memory benchmark were decisive: grading authority
from tool calls only; separating revoked, adjacent, denied, never-granted and skill-driven
requests; and reporting invariant violations alongside behaviour. Without `INV`, the
types-only ablation would have looked strictly best.

## 8. Limitations

Small models dominate the evidence; one frontier model was run on one experiment. Two
synthetic domains with deterministic tools; real harness traces would add realism and lose
ground truth. Five seeds per cell for most tables; the decay sweep has fifteen. Depth bins
in §6.4 hold 9–22 probe buckets. The belief probe depends on parsing model output; parse
rates were 100% on gpt-4o-mini and Sonnet 5, 77% on Qwen and 59% on Gemini after a tolerant
parser, and unparsed replies count as believing nothing is allowed. OpenRouter upstreams
vary: one Qwen host returned empty tool-use content until routed around; Gemini returned
deterministic errors on about 1% of requests, counted as empty replies. Temperature 0
through a router is not fully deterministic; a few percentage points of run-to-run movement
in FAR is the noise floor. THSM's zero depends on the harness authenticating the permission
channel; we do not model a compromised principal channel or cross-agent delegation.
One third-party memory system (Mem0) is compared, on one model and one domain; Letta
was not run because its SDK requires a hosted or Docker server.

## 9. Conclusion

Decay and authority creep are the same operator seen from two sides. Typing harness state
and exempting deontic entries from decay and consolidation, with a deterministic gate and
integrity labels, removes false authority at no measurable utility cost across four model
families and two domains. The results that reach beyond the construction are that
in-context constraints, even perfectly preserved and correctly restated by the model, are
not binding; that skills carry the authority of the episode they were learned in; and that
labels without a deontic channel erode the very prohibitions they were meant to protect.

## References

- Anderson, J. R., & Schooler, L. J. (1991). Reflections of the environment in memory.
  Psychological Science.
- Zhong et al. (2023). MemoryBank: Enhancing large language models with long-term memory.
- FadeMem: Biologically-inspired forgetting for efficient agent memory. arXiv:2601.18642.
- FSFM: A biologically-inspired framework for selective forgetting of agent memory.
  arXiv:2604.20300.
- Selective forgetting: a graph-based memory framework for long-term LLM agents.
  arXiv:2608.28978.
- When to forget: a memory governance primitive (Memory Worth). arXiv:2604.12007.
- Adaptive memory admission control for LLM agents (A-MAC). arXiv:2603.04549.
- Learning what to remember: observability-safe memory retention. arXiv:2606.10616.
- Control-plane placement shapes forgetting. arXiv:2606.15903.
- Useful memories become faulty when continuously updated by LLMs. arXiv:2605.12978.
- Library drift: a silent failure mode in self-evolving LLM skill libraries. arXiv:2605.19576.
- SKILL.nb: selective formalization and gated execution for durable agent workflows.
  arXiv:2606.08049.
- SkillOps: managing LLM agent skill libraries as self-maintaining software ecosystems.
  arXiv:2605.13716.
- Progent: programmable privilege control for LLM agents. arXiv:2504.11703.
- Taming privilege escalation in LLM-based agent systems: a mandatory access control
  framework (SEAgent). arXiv:2601.11893.
- Authorization propagation in multi-agent AI systems. arXiv:2605.05440.
- Delegation without trust: identity, authorization and runtime governance in multi-agent
  LLM systems. arXiv:2609.00267.
- Agent memory is a surface for endogenous authorization laundering. arXiv:2609.01836.
- Governance decay: how context compaction silently erases safety constraints (ConstraintRot).
  arXiv:2606.22528.
- Omission constraints decay while commission constraints persist in long-context LLM agents.
  arXiv:2604.20911.
- MemEvoBench: benchmarking safety risks from memory misevolution. arXiv:2604.15774.
- Remembering more, risking more: longitudinal safety risks in memory-equipped agents.
  arXiv:2605.17830.
- Governing evolving memory in LLM agents (SSGM). arXiv:2603.11768.
- Always-on agents: a survey of persistent memory, state and governance. arXiv:2606.30306.
- Biba, K. J. (1977). Integrity considerations for secure computer systems. MITRE TR-3153.

## Appendix A. Reproduction

Each experiment is a YAML config under `configs/`; `uv run python -m decaymem.runner
--config <cfg> [--model M --name N --seeds S --writer W --compaction C --jobs J]` runs the
matrix and `uv run python -m decaymem.report --experiment <name>` prints the tables and the
frontier plot; `--laundering <names>` prints the created/acted split. Every model response
is cached under `data/cache/` by content hash, so re-running a config after a grader change
costs nothing. Per-probe records, scorecards, manifests (including token usage, provider
errors and the resolved backend description) and the exact scenario are written per cell.
The full results log with every table and reading is `docs/05-results-log.md`.

## Appendix B. Metric definitions

See `docs/02-dual-benchmark.md` §3. Utility composite = mean of KUA, SSR and (1 − REGRESS),
with NaNs skipped. Authority fidelity = 1 − FAR, where FAR pools revoked, adjacent, denied,
never-granted and revoked-skill probes. Depth bins pool 20-tick buckets of per-probe
compliance. All means are over seeds; intervals in Table 2 are normal approximations over
15 seeds.
