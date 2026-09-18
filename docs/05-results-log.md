# 05 · Results log

Live runs, newest last. Numbers are means over seeds. Full per-run scorecards, probe
records and scenarios live under `experiments/<name>/results/` (not committed); the
response cache under `data/cache/` makes every run replayable at zero cost.

## 2026-09-18 · H3/H5 ablation, gpt-4o-mini via OpenRouter

Config `configs/h3_live.yaml`: generator scenarios, 400 events, 5 seeds, typed writer,
pinned compaction, aggressiveness 0.5, cap 40. 30 cells, 1569 model calls (1235 served
from cache because the six backends share writer prompts), about $0.22.

| backend | utility | 1-FAR | FAR | RSR | GEN | LRR | KUA | SSR | CLAIMS | INV |
|---|---|---|---|---|---|---|---|---|---|---|
| flat_ebbinghaus | 0.62 | 0.58 | 0.42 | 0.44 | 0.45 | 0.33 | 0.40 | 0.70 | 6.4 | 0 |
| labels_notypes | 0.69 | 0.32 | 0.68 | 0.23 | 0.63 | 0.00 | 0.49 | 0.79 | 24.4 | 0 |
| thsm | 0.72 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.43 | 0.85 | 23.8 | 0 |
| thsm_nogate | 0.72 | 0.73 | 0.27 | 0.90 | 0.27 | 0.00 | 0.40 | 0.82 | 23.6 | 0 |
| thsm_nopin | 0.70 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.46 | 0.79 | 23.6 | 0 |
| typed_nolabels | 0.75 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.43 | 0.90 | 8.2 | 16.2 |

![frontier](results/h3_live_gpt-4o-mini_frontier.png)

Prohibition compliance by depth since the DENY (pooled, H4 preview):

| backend | d0 | d40 | d80 | d100 | d120 | d160 | d220 | d300 |
|---|---|---|---|---|---|---|---|---|
| flat_ebbinghaus | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| labels_notypes | 1.00 | 0.75 | 1.00 | 1.00 | 0.00 | 0.00 | 0.50 | 0.00 |
| thsm (all gated variants) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

### Reading

- **H3 holds on a real model.** THSM sits at fidelity 1.00 with the highest utility
  among label-enforcing backends (0.72 vs 0.62 for the type-blind store). The exemption
  costs nothing here; it gains, because the typed store keeps skills as PROC entries
  that survive consolidation (SSR 0.85 vs 0.70).
- **The gate does the work, pinning helps but does not suffice.** With the gate off but
  deontic entries pinned in context (`thsm_nogate`), the model still acted on 27% of
  unauthorized requests, mostly never-granted and scope-adjacent actions. Pinning alone
  cut creep from 0.42 to 0.27; the gate removed it. Gate without pinning (`thsm_nopin`)
  is also at 1.00 and loses a little utility (0.70).
- **Labels alone made things worse (H5, off-diagonal).** `labels_notypes` reached the
  highest false-authority rate, 0.68, and its prohibition compliance collapsed to 0 past
  depth 120. Mechanism: with one note type and no deontic channel, the *prohibitions*
  themselves arrive as flagged "unverified claims", and the model discounts them. Labels
  protect against laundering only when a trusted deontic channel exists for the real
  permissions; flagging everything erodes the constraints you wanted to keep. This is a
  new, reportable interaction between integrity labelling and omission-constraint decay.
- **Types without labels look safe behaviourally and are not.** `typed_nolabels` shows
  FAR 0.00 on these seeds but 16.2 invariant violations per run: the LLM-written GRANTs
  were admitted and widened A(t) (I1, I2). No probe happened to exercise the widened
  scope. The invariant checker catches the creep the behavioural metrics miss, which is
  the argument for reporting `INV` alongside `FAR`.
- **Type-blind failure modes** split roughly evenly across revoked (9), scope-adjacent
  (11) and never-granted (9) requests, with one prohibition failure. The model complied
  with plain requests when memory offered no reason not to, and generalized one-time or
  narrow grants.

Caveats: one small model, one domain, 5 seeds, 400 events. A-belief probes and the
procurement domain are not yet implemented.

## 2026-09-18 · H1 decay sweep, gpt-4o-mini via OpenRouter

Config `configs/h1_live.yaml`: generator scenarios, 400 events, 5 seeds, freeform writer,
LLM-summary compaction, cap 40; four backends × five aggressiveness levels. 100 cells,
5711 model calls (5271 from cache), about $0.66.

| backend | aggr | utility | FAR | RSR | GEN | KUA | SSR | STALE |
|---|---|---|---|---|---|---|---|---|
| flat_actr | 0.00 | 0.64 | 0.50 | 0.40 | 0.46 | 0.51 | 0.73 | 0.44 |
| flat_actr | 0.50 | 0.60 | 0.65 | 0.17 | 0.63 | 0.42 | 0.69 | 0.52 |
| flat_actr | 1.00 | 0.14 | 0.83 | 0.13 | 0.71 | 0.03 | 0.27 | 0.08 |
| flat_ebbinghaus | 0.00 | 0.57 | 0.49 | 0.60 | 0.51 | 0.32 | 0.69 | 0.68 |
| flat_ebbinghaus | 0.50 | 0.55 | 0.38 | 0.57 | 0.38 | 0.37 | 0.68 | 0.63 |
| flat_ebbinghaus | 1.00 | 0.40 | 0.75 | 0.27 | 0.74 | 0.29 | 0.49 | 0.39 |
| flat_memworth | 0.00 | 0.65 | 0.50 | 0.30 | 0.44 | 0.45 | 0.78 | 0.49 |
| flat_memworth | 0.50 | 0.68 | 0.54 | 0.37 | 0.59 | 0.53 | 0.76 | 0.38 |
| flat_memworth | 1.00 | 0.14 | 0.83 | 0.13 | 0.71 | 0.03 | 0.27 | 0.08 |
| thsm | 0.00 | 0.62 | 0.00 | 1.00 | 0.00 | 0.40 | 0.76 | 0.54 |
| thsm | 0.50 | 0.61 | 0.00 | 1.00 | 0.00 | 0.35 | 0.78 | 0.62 |
| thsm | 1.00 | 0.38 | 0.00 | 1.00 | 0.00 | 0.26 | 0.47 | 0.39 |

(Intermediate levels are in `experiments/h1_live/`; run `decaymem.report` for all rows.)

![frontier](results/h1_live_gpt-4o-mini_frontier.png)

### Reading

- **H1 holds for ACT-R and at the extremes for all three type-blind policies.** ACT-R
  false authority climbs monotonically with aggressiveness, 0.50 → 0.53 → 0.65 → 0.80
  → 0.83, and revocation survival falls 0.40 → 0.13. Ebbinghaus and Memory Worth are flat
  or slightly non-monotone through the middle and then jump to 0.75 and 0.83 at full
  aggressiveness. The mechanism at the top end is the one predicted: once revocation and
  prohibition notes are gone the model has no reason not to comply, so scope-adjacent
  generalization (GEN 0.71–0.76) and revoked actions (RSR 0.13–0.27) both surge.
- **Even with no decay at all, type-blind memory sits at FAR ≈ 0.50.** Half of the
  unauthorized requests were carried out with every note still in the store. Decay makes
  it worse; it is not the root cause. The root cause is that authority lives in
  retrievable prose the model may or may not weigh.
- **THSM is flat at 1.00 across the whole sweep, and its utility curve tracks the
  baselines' curve, including the collapse at aggressiveness 1.0** (0.62 → 0.38, versus
  0.57 → 0.40 for Ebbinghaus). That is the decoupling the model was built for: knowledge
  and skills decay exactly as much as in the baseline, deontic state not at all.
- **Utility is not monotone in aggressiveness for the baselines** either; moderate decay
  sometimes helps (ACT-R 0.25, Memory Worth 0.50) by pruning stale notes, which is the
  motivation for decay in the first place. The frontier plot shows the trade: the
  type-blind curves drift down and left as decay tightens, THSM moves only left.

Caveats as above: one small model, one domain, 5 seeds. The Ebbinghaus mid-range dip
(FAR 0.38 at 0.50) is within seed noise and needs more seeds before reading anything
into it.

## 2026-09-18 · H3/H5 ablation, gemini-2.5-flash-lite via OpenRouter (second model family)

Same config as the gpt-4o-mini run (`--model google/gemini-2.5-flash-lite`). 30 cells,
1505 calls, about $0.15.

| backend | utility | FAR | RSR | GEN | LRR | KUA | SSR | CLAIMS | INV |
|---|---|---|---|---|---|---|---|---|---|
| flat_ebbinghaus | 0.39 | 0.62 | 0.17 | 0.57 | 0.00 | 0.38 | 0.46 | 7.0 | 0 |
| labels_notypes | 0.38 | 0.61 | 0.28 | 0.70 | 0.00 | 0.27 | 0.43 | 33.0 | 0 |
| thsm | 0.46 | 0.00 | 1.00 | 0.00 | 0.00 | 0.38 | 0.50 | 30.6 | 0 |
| thsm_nogate | 0.47 | 0.56 | 0.15 | 0.58 | 0.33 | 0.35 | 0.52 | 30.6 | 0 |
| thsm_nopin | 0.40 | 0.00 | 1.00 | 0.00 | 0.33 | 0.30 | 0.48 | 30.6 | 0 |
| typed_nolabels | 0.43 | 0.00 | 1.00 | 0.00 | 0.00 | 0.27 | 0.54 | 14.8 | 15.8 |

![frontier](results/h3_live_gemini-2.5-flash-lite_frontier.png)

### Reading

- **Replicates the shape, with a weaker model.** Type-blind false authority is higher
  than on gpt-4o-mini (0.62 vs 0.42) and revocation survival is worse (0.17 vs 0.44).
  THSM is again at 0.00 with the best utility (0.46 vs 0.39).
- **Pinning helps this model much less.** With deontic entries pinned in context but no
  gate, gemini-2.5-flash-lite still acted on 56% of unauthorized requests (gpt-4o-mini:
  27%). It reads the FORBIDDEN / REVOKED lines and proceeds anyway. This is the strongest
  argument so far that in-context constraints, even perfectly preserved, are not a
  substitute for a deterministic gate: the gate's value is model-dependent and largest
  for the models that follow instructions least.
- **Labels alone are no better than nothing here** (0.61 vs 0.62), rather than worse as
  on gpt-4o-mini. Either way they do not help without a trusted deontic channel.
- **Types alone again pass behaviourally and fail the invariants** (INV 15.8 per run).
- **Without pinning the gate costs utility**: `thsm_nopin` refused a third of legitimate
  requests (LRR 0.33) because the model, not seeing its grants, asked for permission it
  already had. Pinning is what makes the gate cheap.
