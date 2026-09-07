# HALYARD / target SABLE — Phase 5 gate report (rev 2)

Supersedes rev 1. Both rev-1 defects fixed; full pipeline rebuilt and verified.

**Status: I3 and I7 pass. I1, I2, I4, I5 fail — all four narrowly or for a stated structural reason. Recommendation: sign off on the model, not yet on the ladder.**

---

## 0. Scope decision — rivals excluded, permanently

Level-scaled rival battles carry no concrete roster (levels encoded 0 or -1), so they are **excluded from scoring by decision, not by omission**. All valuation is measured against trainers with real stats: gym leaders, Elite Four, champion, admins and team bosses. 153 slots are excluded on this basis and the exclusion is recorded in every matrix report.

## 1. Data consistency

All 19 checkpoints rebuilt and verified before use — no repeat of the stale-file failure:

| | value |
|---|---|
| matrix cells | **4,248,276** |
| checkpoints stale or empty | **0** |
| distinct natures reaching the matrix | **12** (was 6) |
| candidate builds | 152,865 (19,665 floor + 133,200 ceiling) |

## 2. Defect 1 — nature collapse: FIXED

Candidates were bucketed by `(track, item_class)` only, and the picker ignored nature, so it always took the first entry. Jolly and Timid were generated in the full 2.4M-build set but reached the matrix **zero times**.

Candidates now vary item class and nature independently (2×2 factorial per track):

| nature | before | now (candidates) |
|---|---|---|
| Adamant | 40.2% | 20.1% |
| Jolly | **0%** | 11.5% |
| Timid | **0%** | 8.5% |

The speed-tier rule from `builds.md` §3 was always firing; the candidate selection was discarding it before the matrix could see it.

## 3. Defect 2 — empty replacement baseline: FIXED

Rev 1 produced **Slakoth (BST 280) as an S+ physical wall at the Elite Four**. Diagnosis and correction took two passes:

- First hypothesis — thin roles inflating VORP — was **wrong**: r(VORP, occupancy) = 0.006.
- Real cause, part one: replacement level is the third-best **floor** build; roles gated on tool moves have almost no floor occupants, so the baseline sat near zero.
- Real cause, part two, found only after the first fix failed: cells with **zero** floor occupants never entered the `undefined` set at all and fell through `replacement.get(..., 0.0)` to a silent baseline of zero — the exact artifact the fix was meant to remove.
- Also corrected: replacement was drawn only from floors whose *primary* role matched. VISION says the third-best obtainable form **for that role**, so a floor that walls well but ranks status-spreader higher still counts. Replacement now reads each floor's fit in that specific role.

Result:

| | rev 1 | rev 2 |
|---|---|---|
| cells with replacement = 0.000 | many (silent) | **0** |
| S+ rows | 1,193 (6.6%) | **622 (3.4%)** |
| S+ mean BST | 483 (min 190) | **526 (min 210)** |
| Slowpoke-Galar, cp19 physical wall | **S+** | **C** |
| Slakoth, cp19 physical wall | **S+** | gone from the ladder |

1,080 rows are now `NR` — replacement undefined — and are excluded from tiers, `cant_miss` and every invariant rather than scored against nothing.

## 4. Invariants

| # | Metric | Value | Threshold | Result |
|---|---|---|---|---|
| I1 | max item share | 0.277 (Berry Juice) | ≤ 0.25 | FAIL (narrow) |
| I2 | max nature share | 0.281 (Calm) | ≤ 0.20 | FAIL |
| I3 | mean \|r\| VORP vs BST within (checkpoint, role) | **0.502** | ≤ 0.60 | **PASS** |
| I4 | cells with <3 forms within 10% of leader | 116 | 0 | FAIL |
| I5 | top-6 teams needing more copies than exist | 1 | 0 | FAIL |
| I7 | max move share | 0.129 (Focus Punch) | ≤ 0.30 | **PASS** |

**I3 is the result that matters.** Phase 4's global ladder ran at 0.751 and failed 18 of 19 checkpoints. Role-relative VORP now sits at **0.502** — inside the band and close to the r ≈ 0.46 the prior modelling pass reached. Decorrelation came from the binary gates and the tool term, as predicted.

**I1 and I2 are much improved but still fail.** Item share went 0.549 → 0.277; nature share 0.463 → 0.281, and the dominant nature flipped from offensive (Adamant) to defensive (Calm), which is what the fix should do. Both are now single-item/single-nature concentration in the *support and wall* population, not a global monoculture — Berry Juice is the only cheap reliable longevity item in the catalogue, and Calm is the default defensive nature for special-facing walls.

**I4's 116 failures are mostly genuine role scarcity.** The failing cells are dominated by roles with 1–5 total occupants (cleric, mixed_wall, phazer, hazard_remover). A role with two obtainable occupants cannot have three within 10% of its leader. This is a finding about the hack's role depth, not a scoring bug — but the invariant as written cannot distinguish the two.

**I5's single failure** is Choice Specs at checkpoint 4: the top-6 team wants 3 copies and only 1 exists.

## 5. Remaining gaps

- **647 of 1,044 in-pool forms carry `earliest_cp = UNK`** — only 11 of 127 encounter maps have a gated world row
- 9 Imperium-custom boss forms absent from Phase 1
- Gift Pokémon and in-game trades absent from `02_world.tsv`
- **I6 has never been run** — it is the Phase 6 sensitivity test and the only invariant still untested

## 6. Next

1. I1/I2: widen the reliable longevity-item and defensive-nature options, or accept and document if the hack genuinely offers no alternative. Do **not** rotate choices to spread the distribution — `builds.md` forbids it.
2. I4: split the invariant into "role has ≥3 occupants" (a pool fact) and "top 3 are within 10%" (a scoring fact), so scarcity stops being reported as a scoring failure.
3. I5: enforce copy counts during team selection, not only in the audit.
4. Then Phase 6: round-trip, cross-phase referential integrity, I6, and the sensitivity pass.
