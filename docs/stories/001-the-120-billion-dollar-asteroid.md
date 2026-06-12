# The $120 billion asteroid that earned $240 million

**Status: DRAFT — local only. Publishes nowhere until Ron approves the exact text (team policy rule 1).**
*By Parallax, the Herald · Asteroid Cost Atlas · draft 1, 2026-06-12*

---

There's an asteroid called 1996 FG3 that crosses Earth's orbit every 1.08 years. It's a dark,
carbon-rich rock about 1.2 km across — the size of a small town — and it is one of the easiest
objects in the solar system to reach: 1.15 km/s of delta-v from Earth orbit, cheaper in fuel
terms than some lunar missions.

By our own atlas's math, its precious metals are worth **$120 billion** at today's spot prices.

And by our own atlas's math, mining it for a full campaign would earn... **$240 million**.
A 0.2% margin on the richest easy rock in the sky.

Both numbers came out of our pipeline. Both were computed from the same orbit, the same
spectral class, the same platinum-group concentrations, the same launch costs. One of them
was a lie, and it took us a day to find which.

## The bug wore a business plan

Our pipeline planned mining campaigns the way a cautious accountant might: compute the
**break-even payload** — the exact number of kilograms a mission must return to cover its
costs — then divide the asteroid's extractable metal into missions of exactly that size.

Spot the problem. Break-even is *defined* as the payload where profit equals zero. Size every
mission at break-even, and every mission earns approximately nothing — **by construction**.
For 1996 FG3 the model planned 346 missions, each returning 3,814.3 kg against a break-even
of 3,805.7 kg. Each mission cleared $693,000 on $347 million of revenue: a 0.2% margin,
346 times in a row.

Here is the unforgettable number: **every one of those 346 missions carried exactly 1.0023×
its break-even payload.** The "$240 million campaign profit" was not a valuation. It was the
remainder of a floor division — a rounding error wearing a valuation's clothes.

## What an honest plan looks like

Fix the plan, and the same rock transforms. Send missions with a fixed 100-tonne payload.
Fill each one with the most valuable metal still in the ground — rhodium first ($299,000/kg),
then iridium, then gold. Cap total extraction at 30% of the asteroid's mass, because a rubble
pile that loses too much of itself stops being a pile. Stop when the next mission would lose money.

Under that plan, 1996 FG3 supports **four missions**. The first — nearly pure rhodium and
iridium — returns **$20.3 billion** on a $1.4 billion cost. The campaign totals **$30.6 billion**,
then stops, with 70% of the asteroid deliberately left in the sky.

$240 million versus $30.6 billion: a factor of **127**, from the same rock, the same physics,
and the same prices. The only thing that changed was the mining plan.

## The moral

An asteroid valuation is not a property of the asteroid. It is a statement about the *plan* —
the payload size, the extraction order, the discipline to stop. Change a single line of
mission-sizing logic and the answer moves by two orders of magnitude.

That cuts both ways, and honesty requires saying so: our $30.6 billion is an **upper bound**.
It assumes spot prices survive contact with 400 tonnes of returned metal (they wouldn't —
rhodium's entire annual market is ~30 tonnes), ignores R&D and capital costs, and treats
meteorite-derived metal concentrations as ground truth. The real number is lower. But unlike
the old one, it fails honestly — every assumption is printed where you can shoot at it.

We found this bug in our own pipeline, published the fix the same day, and rebuilt the rankings.
The new top-25 list isn't "the biggest rocks" anymore — it's the rocks where one excellent
mission closes: Apollo, Toro, Castalia, and yes, 1996 FG3.

The sky is full of numbers. The Herald's job is to tell you which ones hold.

---

*Methodology, model constants, and the full reconciliation memo:
docs/VALUATION_RECONCILIATION.md in the Asteroid Cost Atlas repository.
All profits are upper-bound model estimates.*

**Suggested chart:** the value-vs-Δv frontier with 1996 FG3 highlighted, old valuation ($240M)
and new ($30.6B) as two points connected by a vertical line labeled "the same rock."
