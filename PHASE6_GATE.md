# HALYARD / target SABLE — Phase 6 evaluation

No new dataset. Everything re-read from disk and attacked. Every check below is written to fail if the pipeline is wrong.

**Result: I6 passes decisively. Round-trip and referential integrity are clean. One silent data-loss defect found that requires a regeneration pass before Phase 7.**

---

## 1. Invariant I6 — the last untested invariant: PASS

Perturb base stats by ±15 and re-run build generation on a stratified sample; require the recommended build to change for ≥20%.

| | |
|---|---|
| Sample | 150 species-forms, 8 strata (BST quartile × evolution stage) |
| Seed | `20260907`, recorded with the sample in `INT_i6_sample.json` |
| Checkpoints | 3, 10, 19 |
| Cells changed | 280 of 438 (63.9%) |
| **Species-forms changed** | **125 of 146 (85.6%)** |
| Threshold | ≥ 20% |
| **Result** | **PASS** |

Base stats genuinely drive build generation — scrambling a spread changes what gets recommended for the large majority of the sample.

**One caught error worth recording:** the first I6 run returned exactly 0.0%. That is not a plausible result, so I did not report it — both the true and perturbed species tables were being written to the same temp path, so the test was comparing the perturbed file against itself. After separating the paths, 111 of 150 sampled rows show a genuinely different BST (e.g. Venusaur 82/100 BST 525 → 67/115 BST 555) and the test discriminates.

## 2. Round-trip: clean

| file | rows × cols | ragged |
|---|---|---|
| 01_species | 1,523 × 43 | 0 |
| 01b_moves | 938 × 15 | 0 |
| 02_world | 1,128 × 20 | 0 |
| 03_trainers | 859 × 19 | 0 |
| 04a_candidates | 152,865 × 12 | 0 |
| 04c_build_scores | 152,865 × 29 | 0 |
| 05_roles | 152,865 × 20 | 0 |
| 05_valuation | 19,217 × 31 | 0 |

**0 ragged rows across all files.** Sentinel discipline holds: `NONE` (7,984) and `UNK` (899) remain distinct in the species table.

## 3. Cross-phase referential integrity: clean, with one known exclusion

| check | result |
|---|---|
| Roster moves resolving against Phase 1b | **0 failures** |
| Ceiling moves existing in Phase 1b | **0 failures** |
| Ceiling items placed in Phase 2 | **0 failures** |
| **Ceiling movepool legality** (sampled 6,000 slots) | **0 illegal** — no build uses a move its species cannot learn |
| Scored species marked obtainable | **0 failures** |
| Roster species resolving | 8 unresolved (the known Imperium-custom forms) |
| Level-scaled rival slots | 153 excluded by decision |

The movepool-legality check is the one most likely to have caught a fabricated recommendation. It found none.

## 4. DEFECT — silent movepool loss (requires regeneration)

The species parser and the move parser disagree on three move constants; source carries both legacy and current spellings.

| legacy constant | actual constant | references |
|---|---|---|
| `MOVE_BUBBLEBEAM` | `MOVE_BUBBLE_BEAM` | 53 |
| `MOVE_THUNDERPUNCH` | `MOVE_THUNDER_PUNCH` | 34 |
| `MOVE_VICE_GRIP` | `MOVE_VISE_GRIP` | 19 |

106 level-up references failed to resolve and were **silently dropped** from the movepool — precisely what non-negotiable #2 forbids. 34 are recovered via TM, leaving **72 genuinely lost**.

Impact is not cosmetic: **194 species-checkpoint pairs would have a higher best-BP move**, and some change the *orientation verdict* outright — Poliwrath goes from 0 special BP to 65, which means a special track that was never generated at all.

An alias map is now registered in the generator. **The published Phase 1/4/5 artifacts still carry the defect** and need a regeneration pass to clear it.

## 5. Sensitivity pass — what would most change the rankings

Ordered by how much of the ladder each assumption moves.

**A3 — availability timing. 11,191 of 18,137 rows (61.7%).** Most rows are scored at checkpoints their species may not actually be reachable by, because only 11 of 127 encounter maps carry a gated world row. **666 S/S+ rows rest on unknown timing** — Drowzee, Mandibuzz, Cleffa, Camerupt-Mega, Manaphy, Musharna among them. This is the single largest source of ranking uncertainty and is **not recoverable from the supplied files**; it needs map connectivity data or a progression order.

**A2 — the scarcity gate. 2,443 rows (13.5%).** If one-of-a-kind items were treated as freely available, this many rows change tier. Rockruff moves D → S. The gate is load-bearing, so if the hack's item economy is more generous than `02_world.tsv` implies, the ladder shifts materially.

**A1 — tier boundary fragility. 1,698 rows (9.4%)** sit within 0.01 VORP of a tier boundary. Any weight change moves them. Tier labels should be read as bands, not verdicts.

**A4 — borrowed rosters. 2,070 rows.** Checkpoints 2 and 4 have no roster of their own and are scored against the next boss ahead. Correct per VISION §8, but their scores answer "how ready are you for the next fight," not "how strong are you now."

## 6. Consolidated UNK sweep

| file | column | UNK count | recoverable? |
|---|---|---|---|
| 01c_availability | `earliest_cp` | 1,126 | **No** — needs map connectivity or a user-supplied progression order |
| 02_world | `earliest_gate` | 628 | **Partially** — flag anchors cover some; rest needs connectivity |
| 02_world | `prerequisites`, `missable` | 1,128 each | No — never parsed; a Phase 2 gap |
| 01_species | `availability_channels` | 710 | Follows from `earliest_cp` |
| 01_species | `gender_ratio_pct_female` | 189 | Likely recoverable from source; unused by scoring |

## 7. Recommendation

**Do not proceed to Phase 7 yet.** One regeneration pass clears the §4 defect:

1. Re-run generator → matrix → summarize → roles → valuation with the alias map (the code fix is already in).
2. Confirm the 194 affected species-checkpoint pairs change as predicted, and re-check I1–I5, I7.
3. Then Phase 7.

`02_world`'s unparsed `prerequisites` and `missable` columns should also be filled before the app's route checklist is built — the checklist's whole purpose is answering "what have I passed that I shouldn't have," and `missable` is currently 100% UNK.
