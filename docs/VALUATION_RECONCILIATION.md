# Reconciliation memo: the 100× campaign-profit discrepancy

**Author:** Parallax (the Herald) · **Date:** 2026-06-12 · **Status:** finding confirmed, fix proposed
**Assigned:** Meeting #1, by Fable. **Scope:** local analysis only; nothing here publishes without Ron's approval.

## The discrepancy

For 175706 (1996 FG3), the atlas's two models disagree about campaign profit by **127×**:

| | Pipeline (`campaign_profit_usd`, `scoring/economic.py`) | Web (`campaignProjection`, `web/src/utils/mining.ts`) |
|---|---|---|
| Campaign profit | **$239.8M** | **$30.55B** |
| Missions | 346 × ~3.8 t | 4 × 100 t |
| Campaign revenue | $120.0B | $36.0B |
| Profit margin | 0.20% | ~85% |
| Extraction cap | none (100% of extractable) | f_max = 30% |

Same rock, same spot prices, same transport model ($2,700 × e^(2Δv/Ve)), same $300M fixed cost.
Both numbers were reproduced independently to the dollar (script below).

## Root cause: the pipeline's mission sizing makes profit ≈ 0 *by construction*

`economic.py` sizes missions as:

```
n_missions      = floor(total_extractable / break_even_kg)        # 346
mission_payload = total_extractable / n_missions                  # 3,814.3 kg
```

But `break_even_kg` (3,805.7 kg) is *defined* as the payload at which profit = 0. So every
mission carries `payload / break_even = 1.0023×` its break-even mass — each mission clears
**$693k on $347M of revenue**. `campaign_profit_usd` therefore measures only the **remainder
of the floor division**, not the asteroid's economics. It is an artifact with the units of money.

Evidence that this is accidental, not a modeling choice: `MISSION_CAPACITY_KG = 1_000.0` is
defined at `economic.py:70` and **never used**. The intended fixed mission size was dropped.

Three secondary (legitimate) modeling differences amplify the gap:

1. **Greedy vs averaged value.** The web fills payloads highest-$/kg first (rhodium $299k/kg →
   iridium → gold…), so mission 1 alone nets $20.35B. The pipeline values every kg at the
   mass-averaged `specimen_value_per_kg` ($90.9k/kg).
2. **Extraction limit.** The web caps mineable inventory at min(f_rotation, 40%, 30%) = 30%
   (Sanchez & Scheeres 2014 + engineering cap). The pipeline mines 100% of extractable — *more*
   generous, yet still 127× lower, which shows how completely the sizing artifact dominates.
3. **Optimal stopping.** The web stops when the next mission would be unprofitable; the
   pipeline's stopping rule is implicit in the (broken) sizing.

## Which number should we believe?

Neither is the truth — both are upper bounds — but only the **web model is internally
meaningful**: missions of a stated size, filled in a stated order, capped by stated physics,
stopped by a stated rule. The pipeline's campaign columns (`campaign_profit_usd`,
`mission_profit_usd`, `missions_supported`) are not usable as published.

Interim mitigation already shipped: the web UI (Spotlight headline, detail drawer) computes
campaign profit client-side from `campaignProjection` and no longer displays the pipeline field.

## Proposed fix (pipeline)

Port the web model's semantics into `add_economic_score`:

1. Fixed mission capacity (suggest 100 t to match the web's `DEFAULT_MISSION_KG`; or actually
   use `MISSION_CAPACITY_KG` after deciding its value).
2. Greedy per-metal fill by spot $/kg (the per-metal columns already exist).
3. Extraction-limit fraction min(f_rotation, 0.40, 0.30) — rotation and gravity columns exist.
4. Stop when the next mission's profit ≤ 0.

Until then: mark the three campaign columns deprecated in `DATA_DICTIONARY.md`, or drop them
from `api/schemas.py` so no consumer trusts them.

## Story candidate (drafting approved; publication pending Ron)

*"The $120 billion asteroid that earned $240 million."* Same rock, same physics, same prices —
the valuation moves 127× on a single line of mission-sizing code. The unforgettable number:
**every one of the pipeline's 346 missions returns exactly 1.0023× its break-even payload.**
The honest moral: an asteroid valuation is a statement about the *mining plan*, not the rock.

## Reproduction

```bash
curl -s http://localhost:8000/api/asteroids/20175706   # atlas fields used below
```

Pipeline: margin = 90,936.61 − 5,628.70 − 5,000 = $80,307.91/kg; fixed = $305.63M;
be = 3,805.7 kg; n = floor(1,319,762/3,805.7) = 346; payload = 3,814.3 kg;
per-mission profit = $693,129; campaign = **$239.8M** ✓ (matches stored column).

Web: f_rotation = 0.578 → f_max = 0.30 → inventory 395,929 kg; greedy 100 t missions:
$20.35B, $4.91B, $4.03B, $1.26B → **$30.55B** over 4 missions ✓ (matches UI).
