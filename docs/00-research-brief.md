# 00 · Research brief

## Problem

Long-running agent harnesses (coding agents, always-on assistants, multi-agent
pipelines) keep three kinds of state across sessions:

- **Knowledge**: facts about the environment. Goes stale when the world changes.
- **Skills / procedures**: how to do things. Goes stale when the environment drifts.
- **Deontic state**: what the agent may, must not, must, or may no longer do. Does not
  go stale by disuse. A revocation stated once holds until the principal says otherwise.

Every published decay mechanism (Ebbinghaus curves, ACT-R activation, outcome-based
worth, admission control, graph pruning) scores memories by recency, access frequency,
or co-occurrence with success. On all three signals a one-time revocation ranks last
and is pruned first. A prohibition that blocks a task co-occurs with "failure" and is
deprecated by outcome-based scoring. Meanwhile consolidation, the operator harnesses
use to shrink memory, is where LLM writers have been shown to generalize grants and
drop revocations, fabricating authority that the history never contained.

So harness decay and authority creep are the same mechanism viewed from two sides,
and the literature studies them in separate camps that do not cite each other.

## Gap

| Camp | Has | Lacks |
|---|---|---|
| Decay / forgetting (MemoryBank, FadeMem, FSFM, Memory Worth, A-MAC, ACT-R ports) | Principled decay for utility | Any protected memory class; any authority notion |
| Consolidation / skill libraries (Faulty Memories, Library Drift, SKILL.nb, SkillOps) | Evidence consolidation corrupts; lifecycle gating | Separation of what a skill does from what it is allowed to do |
| Authority / constraints (Authorization Laundering, Governance Decay, Omission-vs-Commission, Progent, SEAgent) | Laundering measurement, pinning, least-privilege DSLs | Any decay model; persistence beyond one context window |
| Governance frameworks (SSGM, Always-On survey) | Vocabulary: authority, scope, mutability, provenance | Executable models, benchmarks |

Nothing exists that (a) types harness state, (b) exempts deontic state from decay and
consolidation by construction, (c) labels integrity so model-written text cannot
create or widen authority, and (d) measures utility and authority on the same traces.

## Contributions we are aiming for

1. **Typed Harness State Model (THSM)** with an integrity label lattice and checkable
   invariants. See `01-state-model.md`.
2. **Dual benchmark** producing a utility-versus-authority Pareto frontier for any
   memory configuration. See `02-dual-benchmark.md`.
3. **Plugin experiment layer** that runs the benchmark against arbitrary LLMs and memory
   backends. See `03-plugin-architecture.md`.
4. **Empirical results**: the frontier for type-blind baselines versus THSM, plus
   ablations isolating types, labels, pinning, and consolidation gating.

## Hypotheses to pre-register

- **H1 (decay causes creep).** For type-blind memory, false-authority rate increases
  monotonically with decay aggressiveness, because low-access revocations and denies are
  pruned first.
- **H2 (consolidation is the shared failure).** Increasing consolidation frequency raises
  laundering and, after an initial peak, lowers knowledge utility. Both effects are
  measured on the same runs, jointly replicating the Faulty Memories and Authorization
  Laundering findings.
- **H3 (THSM dominates).** THSM holds authority fidelity at or near 100% by
  construction, at a utility cost within a small margin of the best type-blind
  configuration at the same storage budget.
- **H4 (asymmetric decay persists across sessions).** Prohibitions decay faster than
  obligations not only within a context window but across persistent-memory retrieval,
  and pinning deontic entries at retrieval closes the gap.
- **H5 (types and labels are separable).** In a 2x2 ablation, integrity labels alone
  reduce laundering but not staleness; types alone reduce staleness but not laundering;
  both together are needed for the frontier gain.
- **H6 (skills carry authority).** Skills learned during an approved episode are
  executed later in unapproved scopes unless authority is resolved at call time from the
  deontic store rather than from the skill.

## Anchor papers

Decay side: MemoryBank (2023); FadeMem arXiv:2601.18642; FSFM arXiv:2604.20300;
When to Forget / Memory Worth arXiv:2604.12007; A-MAC arXiv:2603.04549; Control-Plane
Placement Shapes Forgetting arXiv:2606.15903; Useful Memories Become Faulty
arXiv:2605.12978; Library Drift arXiv:2605.19576; SKILL.nb arXiv:2606.08049.

Authority side: Agent Memory Is a Surface for Endogenous Authorization Laundering
arXiv:2609.01836; Governance Decay / ConstraintRot arXiv:2606.22528; Omission Constraints
Decay arXiv:2604.20911; Progent arXiv:2504.11703; SEAgent MAC arXiv:2601.11893;
Authorization Propagation arXiv:2605.05440; Delegation Without Trust arXiv:2609.00267;
MemEvoBench arXiv:2604.15774; Remembering More, Risking More arXiv:2605.17830.

Frameworks: SSGM arXiv:2603.11768; Always-On Agents survey arXiv:2606.30306 (six axes:
authority, scope, mutability, provenance, recoverability, actionability; AOEP-v0).

Cognitive grounding: Anderson & Schooler 1991 (rational analysis of memory, power-law
need probability); Biba integrity model (no write-up) for the label lattice.
