# HALYARD / target SABLE — availability timing restored

The walkthrough closed the largest open gap in the project.

## What it fixed

The source tree encodes which flag gates each checkpoint but not which **map** the player can reach when. Only 11 of 127 encounter maps could be dated from item placements, leaving most of the ladder with unknown timing.

The creator's published walkthrough supplies exactly the ordering the decomp does not — and VISION §7.4 places the hack's own website at priority 3 for precisely this purpose.

| | before | after |
|---|---|---|
| encounter maps with a gate | 11 of 127 | **127 of 127** |
| wild forms with a dated gate | 116 | **647** |
| in-pool forms carrying `earliest_cp = UNK` | 1,126 | **0** |
| ladder rows with unknown timing | 11,872 (61.8%) | **0** |
| S/S+ rows resting on unknown timing | 666 | **0** |

The obtainable pool is unchanged at 1,044 forms, so no scoring re-run was needed — only the availability columns refreshed. **I3 still passes at 0.502.**

## A merge rule I got wrong and corrected

My first pass applied VISION's "the decompilation always wins" and let source override the walkthrough on the 4 maps where they disagreed. That produced Petalburg City dated to checkpoint 10.

The two sources are not measuring the same quantity. A source-derived gate is *the earliest checkpoint at which an item on that map can be obtained* — often behind a further gate inside the map. Petalburg City's item sits behind Norman's gym; the city's water encounters are reachable from checkpoint 1. The source value is an **upper bound on reachability, not reachability itself**.

So the rule is now the earlier of the two, with every disagreement logged:

| map | item placement | walkthrough | taken |
|---|---|---|---|
| Petalburg City | 10 | 1 | **1** |
| Rustboro City | 2 | 1 | **1** |
| Route 110 | 5 | 4 | **4** |
| Sootopolis City | 17 | 16 | **16** |

"Source wins" still holds where both measure the same thing. It does not apply across two different quantities.

## Confidence is not hidden

120 of 127 gates are **Asserted** — read off a secondary source, not confirmed in the game files. 7 remain Derived from item placements. That distinction rides with the number everywhere:

- ladder confidence spread: Asserted 8,598 · Derived 7,399 · Inferred 1,915 · Measured 1,303
- the app shows a "Caught by" column, with asserted timings in amber and the tier named on hover
- the species card states the confidence in words next to the checkpoint
- the Method tab says plainly that amber timings follow the creator's route order, which the game files do not encode

## App

`halyard_sable.html`, 2.17 MB, still a single offline file — 0 network references, 0 browser storage. All five views and the species card re-verified rendering against the new payload. The availability filter is back: *caught by checkpoint N*.

## Still open

The site has pages that would close the remaining Phase 2 gaps — in-game trades, gift Pokémon and eggs, TM/HM locations, mega stone locations. Those would fix the 58 mega forms currently inheriting their base form's timing, and the 6 unresolved evolution items.
