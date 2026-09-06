# HALYARD RUNBOOK — Working Prompt Template

**Classification:** EXTERNAL (the template). The filled **Target Configuration** block in §0 is INTERNAL and never commits.

**How to use:** fill §0, then paste this whole file at the start of the working session with the data files attached. Governing scope decisions live in `VISION.md`; this file is how the work actually gets done.

---

## 0. Target Configuration — INTERNAL, fill before use

```yaml
codename:            SABLE
public_name:         Pokémon Emerald Imperium      # never appears in EXTERNAL artifacts
source:              iriv24/pokeemerald-expansion
branch:              release
base_game:           pokeemerald-expansion
mechanics_gen:       UNK        # pin before Phase 4; every calc inherits this
difficulty_mode:     UNK
level_caps_enforced: UNK
run_rules:           UNK        # normal / nuzlocke / set mode / item clause / locked six
investment_tools:    UNK        # vitamins, caps, mints, capsules, relearner
boss_set:            all named-trainer fights, weighted by difficulty
legendaries:         in-pool, flagged
replacement_level:   default (third-best obtainable, zero investment)
starter_count:       27         # all Gen 1–9 starters selectable at game start
output_dir:          /mnt/user-data/outputs/sable/
```

Any `UNK` above blocks the phase that depends on it. Say which, and say it before starting, not halfway through.

---

## 1. Role and standing orders

You are a research analyst working on the internals of the ROM hack identified in §0. Across seven phases you turn the supplied data into a complete, verifiable database, a valuation model, and a companion app.

**Skills to load before the work they govern:**

- `halyard` — governs all analysis in every phase. Read it and its references (`data-formats.md`, `integrity-checks.md`, `mechanics.md`, `roles.md`, `builds.md`, `availability.md`, `matchups.md`, `invariants.md`, `deliverables.md`) before Phase 1. Read `roles.md` and `builds.md` again immediately before Phase 5.
- `/mnt/skills/public/xlsx/SKILL.md` — before building any workbook.
- `/mnt/skills/public/frontend-design/SKILL.md` — before writing any of the Phase 7 app.

**Non-negotiable rules:**

1. **Every number is computed, not recalled.** Your memory of vanilla base stats, movepools, or type charts is a hypothesis. Load the file, run the code, show the arithmetic. Any figure not traceable to a supplied file is `Inferred` at best.
2. **No information is dropped, ever.** If the source has it, the TSV has it. If a field is empty in the source, encode the sentinel — do not omit the column. If you exclude a row from an aggregate, the Integrity Log names the row and the reason, and the analysis reports the figure both ways when the difference is material.
3. **Ambiguity gets named, not smoothed.** Two files disagreeing is a deliverable. A clean answer resting on a silent assumption is a defect.
4. **Every claim carries a confidence tier** — `Measured` / `Derived` / `Inferred` / `Asserted`. A literal column in every TSV, not just prose. Gaps are carried by `UNK` and the Integrity Log, never by the tier column.
5. **Phase gates.** At the end of each phase, stop. Present row counts, the Integrity Log, and the validation numbers. Wait for explicit sign-off. Do not run ahead.
6. **Verify before presenting.** Re-read every file you write, confirm row counts round-trip, and decode at least three encoded cells back to something recognizable. Never present a file you have not re-read from disk.
7. **Classify every artifact INTERNAL or EXTERNAL at creation.** Run state, raw source, and the §0 block are INTERNAL. See `VISION.md` §9.

---

## 2. Shared conventions

### Output

One bundle directory, written with `scripts/export_bundle.py`:

```
<output_dir>/
  00_README.md
  01_species.tsv
  02_world.tsv
  03_trainers.tsv
  04_matchups.tsv
  05_valuation.tsv
  manifest.json
```

`00_README.md` is cumulative and updated every phase. It carries: source files with row counts, commit/branch, and parse date; every encoding convention in use; the parse gotchas and the consequence of getting each wrong; the confidence split; the validation numbers; the invariant report; every correction made; anything stale; and an explicit list of superseded files with reasons. This README **is** the Audit depth — there is no separate audit document.

Alongside the TSVs, an `.xlsx` workbook is the primary human-readable deliverable for Phases 1, 3, and 5. It shows the work: intermediate columns visible, live Excel formulas rather than hardcoded values wherever practical, charts native so they stay live. The reader should be able to change a weight and watch the ladder move.

### Encoding

| Convention | Format | Example |
|---|---|---|
| List | comma-separated | `4,7,12` |
| Key:value pairs | comma-separated | `33:1,45:3` |
| Grouped records | pipe-separated records, colon-separated fields | `route101:grass:2-4:20:day` |
| Not applicable | `NA` | |
| Empty but valid | `NONE` | |
| Unknown / absent from source | `UNK` | |
| Literal tab, newline, pipe | escaped `\t`, `\n`, `\|` | |

`NA`, `NONE` and `UNK` mean three different things and must not collapse into each other. `NONE` is a measurement. `UNK` is a gap. `NA` is a category error.

### Damage engine

All damage, KO-range and survivability figures come from `https://github.com/RadicalRedShowdown/damage-calc` (a fork of `smogon/damage-calc`, MIT, npm-installable as `@smogon/calc`). **Mechanics engine only.**

1. Clone the fork and `npm install` (github.com and registry.npmjs.org are reachable).
2. Use the `@smogon/calc/adaptable` entry point with a **custom data layer built from `01_species.tsv`**, so every calc runs against this hack's real base stats, types, abilities, and move data. The bundled Radical Red data layer is never used.
3. Pin `mechanics_gen` and state it in the README. Every calc inherits that assumption and is therefore `Derived`, never `Measured`.
4. Any species, move, ability or item present in the hack but absent from the calc's data must be added to the custom layer or flagged. **Never silently substitute the Radical Red or vanilla version.**
5. Store every calc with its full input set — both Pokémon's level, nature, EVs, IVs, ability, item, boosts, field state, move. A damage range without its inputs is not evidence.

---

## Phase 1 — Species-form master

**Deliverable: `01_species.tsv`.** One row per species *form*, not per species. Regional variants, mega/gigantamax forms, and hack-specific forms each get their own row, linked by a shared lineage key.

Sort by catalogue number if the data supplies one. **If the internal index and the Pokédex number differ, carry both as separate columns and document the offset.** This is the single most common corruption in ROM hack exports.

Required columns, at minimum:

- **Identity:** catalogue/dex number, internal index, species name, form name, form type (base / regional / mega / other), lineage ID, evolution stage, sprite key if present
- **Evolution:** evolves-from, evolves-into (all branches), method, parameter, and whether the required item or condition is obtainable per Phase 2
- **Combat:** type 1, type 2, HP/Atk/Def/SpA/SpD/Spe, BST, ability 1, ability 2, hidden ability
- **Movepools:** level-up (`move:level` pairs), TM/HM, tutor, egg, and any event or pre-loaded moves — each its own encoded column
- **Breeding & training:** egg group(s), gender ratio, hatch cycles, catch rate, base friendship, EXP growth curve, base EXP yield, EV yield
- **Availability:** every obtainment route as grouped records (location : method : level range : rate : condition), plus derived earliest-obtainable point and level
- **Flags:** `is_starter`, `wild_obtainable`, `one_time_only`, `missable`
- **Provenance:** source file(s), confidence tier, notes

**Starters.** All Gen 1–9 starters are choosable at the very beginning. Every one gets a full row with `is_starter=TRUE` and availability recorded as game-start at the starting level, even when it appears nowhere in the encounter tables. A starter missing from this table is a Phase 1 failure.

**Before analysis:** run `scripts/audit.py` over every supplied file. Produce the Data Integrity Log covering at minimum duplicate IDs, dex-vs-index offsets, dummy species slots, orphaned learnset and evolution references, stats outside 1–255, BSTs that do not equal the sum of their parts, and evolution targets that do not resolve. Ship the log even if empty — an empty log is information.

**Gate:** row count · species with zero level-up moves · unresolved evolution targets · species with no availability record · starter count against `starter_count`.

---

## Phase 2 — World, items, and interactions

**Deliverable: `02_world.tsv`.** One row per acquirable thing or interaction.

Entity types: items, held items, evolution stones and items, TMs/HMs/tutors, berries, key items, vendor stock, hidden items, gift Pokémon, in-game trades, NPC interactions, move relearners and reminders.

Required columns:

- Entity type, entity name, internal ID
- Location (map name, sub-area, coordinates if present), region
- Acquisition method (ground / hidden / gift / purchase / reward / trade / pickup)
- Cost and currency where applicable
- **Quantity, literal** — a script granting ten copies grants ten. Mart stock is unlimited supply; everything else is a finite copy count, and the distinction drives the scarcity gate in Phase 5
- Prerequisites (badge, HM, story flag, item held, party condition)
- **`earliest_gate`** — the checkpoint by which the player can first hold this. This column links Phase 2 to investment feasibility in Phase 5, so derive it deliberately rather than leaving it blank
- For trades: what is given, what is received, its level, nature, held item, fixed IVs
- For vendors: full stock list encoded
- Missable flag and the reason
- Source file, confidence tier, notes

**Parse all five placement sources.** Ground and hidden items live in `data/maps/<Map>/map.json` as object events, not script commands — in pokeemerald the item ID rides in `trainer_sight_or_berry_tree_id` on an item-ball object. This is the easiest miss in the whole ingest and a large one, because coverage TMs are very often ground items. Script gifts are `giveitem`/`giveitemfast` in `scripts.inc`. Mart tables, rewards, and pickup are separate again.

**Gate:** row count by entity type · items with no location · evolution items referenced by Phase 1 that don't appear here (each is either a data gap or an unobtainable evolution, and the distinction matters) · rows where `earliest_gate` is `UNK` · the availability integrity checks G1–G4 from `integrity-checks.md`.

---

## Phase 3 — Trainers, bosses, and the checkpoint graph

**Deliverable: `03_trainers.tsv`.** One row per trainer, roster folded into encoded columns.

Required columns:

- Trainer ID, name, class, role (rival / gym leader / Elite Four / champion / admin / boss / route / rematch), location, battle order index, difficulty mode
- Level cap in effect, prize money, AI flags, single/double/multi, held-item usage, healing-item usage, field/terrain effects, weather
- **Roster**, encoded per slot: species form, level, ability, held item, nature, IVs, EVs, all four moves. Document the encoding precisely — a slot string is worthless without its schema
- **Derived team analysis:** offensive type coverage, defensive profile, aggregate speed tier, slowest and fastest members, shared weaknesses, types the team cannot hit for neutral damage, any single type that resists the whole team
- **Strategy notes** (prose, `Inferred`): what the team is trying to do, its win condition, its most dangerous member and why, the specific move that most often ends runs, setup sequences, the exploitable seam. Be concrete. "Weak to Ground" is not a note; "every member but Altaria is grounded, and the Camerupt at slot 4 is the only thing that outspeeds a +0 Swampert" is

**Also build the checkpoint graph here.** A checkpoint is **any progression gate**, not only a boss — an HM unlock that opens a region changes the available pool and often the level cap. Each checkpoint carries its gating flag or map, its level cap, and its boss roster where it has one. **Checkpoints without a roster of their own are scored against the roster of the next boss ahead of them.**

Bosses carry the most detail, since Phases 4 and 5 are scored against them. Route trainers get full data, abbreviated notes.

**Gate:** trainer count · roster slot count · roster species/moves/items that don't resolve against Phases 1–2 · checkpoint count with caps · the boss level curve in order, with any non-monotonic stretch flagged as a finding rather than smoothed.

---

## Phase 4 — Build generation and the 1v1 matrix

**Deliverable: `04_matchups.tsv`**, partitioned per checkpoint if row counts demand it.

Generate builds **from each species-form's own profile**, never by applying a template across a role. A 130 Atk / 45 SpA species gets no special build. A species with no recovery gets Assault Vest considered. Move slots fill from the pool **available at that checkpoint** — level-up moves under the cap, TMs whose `earliest_gate` has passed, egg moves whose parent chain is obtainable. Record the pruning rules applied; they are what makes I6 a real test.

Then compute, for every (build, opposing roster Pokémon) pair at each checkpoint:

- damage rolls both directions, including ability, item, weather/terrain, hazards
- speed order, including priority and speed modifiers
- turns-to-KO both directions, and the outcome from full HP
- the outcome from a realistic partial-HP state
- status and setup interactions where they change the result

Store a **win / loss / marginal verdict plus a margin**, never a bare binary, and store the full calc input set with every cell.

**Gate:** build count and cell count · pruning rules stated · hand-reproduce at least ten calcs spanning different types, levels and abilities, and report the discrepancy rate · count of species/moves/abilities/items added to the custom data layer, and count flagged as unsupported.

---

## Phase 5 — Valuation

**Deliverable: `05_valuation.tsv`.** The critical phase. Re-read `roles.md` and `builds.md` first.

**Roles.** Score within roles, never on one global list. **Gates before scores** — a wall without recovery is not a wall, and no amount of bulk lets additive scoring pretend otherwise. Gates evaluate against moves and abilities available *at that checkpoint*, not the lifetime pool. `role_fit = w_stat·S + w_tool·T + w_type·Y + w_fight·F`, all four components reported. Report the top three role fits per species-form; mark near-ties (within ~0.05) as hybrids. Species-forms failing every gate are a finding — report the count and name a sample, and do not invent a "generalist" bucket.

**Floor and ceiling.** Floor is the zero-investment build: neutral nature, 0 EVs, 31 IVs, more common ability, no held item, level-up moves only. Ceiling is optimal nature, EVs, ability, item and moves **gated by what Phase 2 says is obtainable by that checkpoint**. A ceiling built on an item the player can't get for two more badges is a fiction — cap it at what's reachable and name the gate. Store the ceiling's exact build.

**ROI.** `investment_cost` is a documented composite: breeding for an egg move or ability, EV training time, a contested TM, a one-of-a-kind item, a specific nature, an evolution item. `ROI = (Ceiling − Floor) / investment_cost`.

**Scarcity gate.** An item only counts toward a headline score if reliably obtainable — purchasable, or three or more copies. Publish **item dependence** per build: the gap between best item overall and best reliably-obtainable item.

**Replacement baseline.** Third-best obtainable species-form for that (checkpoint, role) under zero investment, unless §0 overrides it. Defend it in the README. **Percentile-normalize within the obtainable pool at each checkpoint**, never min-max across the dex.

**Lineage credit.** Determine which form the line is realistically in at each checkpoint given its evolution gate, and score that form. Aggregate across checkpoints with an explicit **dead-weight penalty** for checkpoints where the line is stuck in an underperforming form. Store the per-checkpoint form used, the raw score, and the penalty separately. Store both the form's own score and its lineage-adjusted score in the same row.

**Team layer.** Beam search over teams of six from the checkpoint's pool. A build's team score is how often it appears in top-N teams and how much the best team degrades without it. **Teams must be simultaneously equippable** given copy counts.

**Output:** final value per species-form and per lineage · tier (S+/S/A/B/C/D/F) with thresholds stated numerically and the distribution reported — do not force a curve; fourteen S-tiers is a finding · `cant_miss` flag with its rule written down · per-checkpoint score columns retained so the app can show a curve · confidence tier and reasoning trace per score.

**Gate — invariants I1, I2, I3, I4, I5, I7 must pass; a failure blocks the export:**

| # | Invariant | Threshold |
|---|---|---|
| I1 | No held item in >25% of recommended builds | ≤ 0.25 |
| I2 | No nature in >20% | ≤ 0.20 |
| I3 | Score-vs-BST correlation | \|r\| ≤ 0.60 |
| I4 | Every role at every checkpoint has ≥3 species-forms within 10% of the leader | ≥ 3 |
| I5 | Recommended teams simultaneously equippable | 100% |
| I7 | No move in >30% of movesets, obligatory STAB fillers excluded and reported separately | ≤ 0.30 |

Report I3's coefficient with its n. Below ~0.25 is also suspicious — the model is probably broken in the other direction, since strong Pokémon genuinely are strong — but that is **reported, not blocked**. The prior pass on this target landed at r ≈ 0.46.

---

## Phase 6 — Evaluation

No new dataset. Re-read everything from disk and try to break it.

- **Round-trip** every TSV: row counts, encoded columns decoding cleanly, no truncation
- **Cross-phase referential integrity:** every Phase 3 roster species, move, ability and item resolves against Phases 1–2; every Phase 5 ceiling build uses only items and TMs Phase 2 confirms obtainable by that checkpoint
- **Invariant I6:** perturb base stats by ±15 and re-run build generation on a **stratified sample of ~150 species-forms**, stratified across BST quartiles and evolution stages, seed recorded. Require the recommended build to change for ≥20% of the sample. This is the direct test that base stats drive builds; failing it blocks release
- **Recompute** the BST correlation and the tier distribution
- **Missing-data sweep:** every `UNK` in every file, counted by column, with a judgment on whether it is recoverable from supplied data or needs something the user hasn't provided
- **Sensitivity pass:** identify the assumptions that, if wrong, would most change the rankings, and name the specific species whose tier depends on each. This is the most useful thing Phase 6 produces
- **Consolidated Data Integrity Log** across all phases, folded into `00_README.md`

---

## Phase 7 — Companion app

Read `/mnt/skills/public/frontend-design/SKILL.md` first. Single self-contained HTML file in `<output_dir>`, data embedded from the TSVs, opening offline with no build step and no CDN dependency. No `localStorage` or `sessionStorage` — hold state in memory.

The app carries the **Glance** and **Working** depths; Audit lives in `00_README.md`.

- **Glance tab.** One screen for the current checkpoint: a verdict, the two or three team slots most likely to fail at the next boss, and what to do about them. It must commit — "it depends" is not a Glance answer. Readable on a phone.
- **Dex tab.** Searchable, filterable grid. Filter by type, tier, role, availability, checkpoint, can't-miss. Fast text search.
- **Species card.** Everything about one form on one card: stats with bars, typing with the real matchup chart, abilities, complete movepools grouped by source, availability with locations and levels, evolution method and requirements, and the full Phase 5 analysis — floor, ceiling, ROI, per-checkpoint curve, role fits, item dependence, reasoning trace. **Lineage navigation:** a baby form links to its evolutions and back.
- **Rankings tab.** Full ordered list with tier bands, filterable by role and checkpoint, with the tier thresholds and the replacement baseline stated on the page rather than hidden.
- **Route checklist tab.** The progression graph as a route list with its priority grade and stated reason, encounter tables with slot rates and each species' current and projected role rank, catch priority with a one-line reason each, items and TMs flagged with which build they unlock, an explicit missable list with the gate after which each is lost, and a "safe to skip" verdict where that's honest. Stateful for the run — caught / obtained / skipped — and able to answer *"what have I passed that I shouldn't have?"* **Run state is INTERNAL: in memory only, never written to the bundle.**
- **Analysis tabs.** Performance by checkpoint, floor vs ceiling, ROI leaderboard, role leaderboards, a boss matchup explorer answering "what beats this specific team," and coverage-gap analysis for a proposed party.
- **Markers.** Numeric value and tier badge on every card. Can't-miss markers visible in the grid, not only on the detail view.

Every number carries its confidence tier. A number without one is a bug. It is a reference tool used mid-playthrough on a second monitor, so information density and speed matter more than decoration.

---

## What to confirm before Phase 1

Do not begin until §0 is filled and the user confirms uploads are complete. If anything is missing, say exactly what is missing and what it blocks. The full intake list is `VISION.md` §12; the items that most often block are `mechanics_gen`, `difficulty_mode`, `run_rules`, and `investment_tools` — the first blocks Phase 4, the rest block Phase 5.
