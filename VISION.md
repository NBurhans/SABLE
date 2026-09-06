# HALYARD — Vision Document

**Status:** Draft v2 (merge of HALYARD_VISION v1 and the Imperium project prompt) · **Classification:** EXTERNAL (ships to repo root as `VISION.md`)
**Date:** 2026-09-05

---

## 0. The one-paragraph version

HALYARD is a companion system for playing difficulty-modified Pokémon ROM hacks. Its job is to answer, at any point in a playthrough: *what should I be catching, what should I be building, and what am I about to miss?* It answers those questions from the hack's own source data rather than from community consensus or from what a language model remembers about Pokémon. Underneath, it computes an exhaustive 1v1 matchup matrix; on the surface, it publishes replacement-relative value with a floor, a ceiling, and the cost of getting from one to the other. The first target is a Hoenn-based hack built on `pokeemerald-expansion`; the architecture assumes there will be a second and third target, so everything hack-specific is isolated behind an adapter and everything else is generic.

---

## 1. Codename and naming policy

| Layer | Codename | Meaning |
|---|---|---|
| Framework | **HALYARD** | The reusable engine, skill, and presentation layer |
| Target 01 | **SABLE** | The current hack (`iriv24/pokeemerald-expansion`, `release` branch) |
| Future targets | SABLE, CINDER, MARROW, … | One codename per hack, assigned on adoption |

**Repository name:** `halyard`

**Naming rules, binding on all EXTERNAL artifacts:**

1. No franchise-identifying words in the repo name, repo description, topics, README title, or commit messages.
2. The repo description is generic: *"A data-driven planning framework for turn-based RPG progression."*
3. Target folders use codenames (`targets/sable/`), never the hack's public name.
4. Species names, move names and map names inevitably appear **inside data files** — unavoidable and acceptable. The goal is that the repo is not findable by someone searching for the hack, not that the contents are obfuscated.
5. No topics or tags on the GitHub repo. No links to it from any forum, Discord, or wiki.
6. Never commit ROM files, save files, or game assets. Derived numeric tables only.

**The one seam.** The working prompt (`RUNBOOK.md`) is a template and is EXTERNAL. Its **target configuration block**, which names the hack in plain language, is INTERNAL and is never committed. The template ships with the block empty and a codename placeholder.

---

## 2. What this is, and what it is not

**It is:**
- A planning and analysis tool for a single human playthrough.
- A framework whose value compounds — each target adopted should be cheaper than the last.
- Opinionated. It makes recommendations and states its reasoning.

**It is not:**
- A wiki, a walkthrough, or a replacement for playing the game.
- A battle simulator. Damage math is a component, not the product.
- A general-audience app. It is built for one player's workflow; if others find it useful, fine.
- Live-connected to a running game. No ROM reading, no save-state parsing, no emulator hooks in v1.

---

## 3. Success criteria

HALYARD v1 succeeds if, during the SABLE playthrough, all of these hold:

1. **Pre-boss usefulness.** Before each major fight, the system names the two or three team slots most likely to fail and what to do about them, and is right more often than a coin flip.
2. **No blind misses.** Nothing one-time and high-value is missed because the system failed to flag it before the point of no return.
3. **Recommendation diversity.** Recommended builds across a full playthrough are not dominated by one item, one nature, or one move. See the invariants in §4.9.
4. **Traceability.** Any recommendation can be drilled into, down to the source file and line it derives from.
5. **No silent loss.** Every field present in the source is present in the dataset, every excluded row is named in the Integrity Log with its reason, and every gap is encoded rather than omitted.
6. **Portability, proven.** A second hack can be onboarded by writing an adapter and a checkpoint list — no changes to the scoring engine.

---

## 4. Pillar I — The ranking system

This is the bedrock. Everything else is scaffolding around it.

### 4.1 The unit being ranked

Not a species. The atom is:

> **(species-form, build, checkpoint)**

where *build* = (ability, nature, held item, four moves, EV/level assumption) and *checkpoint* = a named progression gate. The same Pokémon can be an S-tier answer at checkpoint 4 and dead weight at checkpoint 9; collapsing that into one number throws away the thing that actually matters.

**Species-form, not species.** Regional variants, mega and gigantamax forms, and hack-specific forms each get their own row and their own builds, linked by a shared lineage key. A mega is a separate build of the same lineage, gated on its stone's availability.

A "rank" surfaced to the player is always a projection of this atom — most often *"best build of species X, at checkpoint M."* Say which projection is being shown.

### 4.2 The primitive: 1v1, exhaustively computed

**Decision: the 1v1 matchup matrix is the primitive. Everything the player sees is derived from it.**

Rationale: 1v1 outcomes are exhaustively computable — every candidate build against every Pokémon on every boss roster. Team evaluation is combinatorially explosive and cannot be exhaustive. Building teams on top of a complete 1v1 matrix gives both, and keeps the expensive layer honest because it rests on measured numbers.

For each (build, opposing Pokémon) pair, compute:
- damage rolls both directions, including ability, item, weather/terrain, and hazard effects
- speed order, including priority and speed-modifying items and abilities
- turns-to-KO both directions, and therefore the outcome from full HP
- outcome from a realistic partial-HP state (the "already chipped" case)
- status and setup interactions where they change the outcome

Output: a win / loss / marginal verdict plus a margin, never a bare binary.

**The engine.** Damage, KO ranges and survivability come from the `@smogon/calc` fork at `RadicalRedShowdown/damage-calc` (MIT, npm-installable), used through the `adaptable` entry point with a **custom data layer built from the Phase 1 species table**. This is a deliberate amendment to the source hierarchy in §7: the calculator supplies *mechanics*, never *data*. Its bundled Radical Red data layer is never used, and any species, move, ability or item present in the target but absent from the calculator is added to the custom layer or flagged — never silently substituted.

Two consequences, stated once and inherited everywhere:
- The generation whose mechanics the target uses is **pinned and named in the README**. Every cell inherits that assumption.
- A matrix cell is therefore **Derived**, not Measured, however solid its inputs. Only a figure confirmed in-game is Measured.
- Every calc is stored with its full input set — both Pokémon's level, nature, EVs, IVs, ability, item, boosts, field state, and move. A damage range without its inputs is not evidence.

### 4.3 Build generation, and how the explosion is contained

Naively, ability × nature × item × four moves is astronomically large. It is contained by generating builds **from the species' own profile**, never by applying a template across a role:

- A species with 130 Attack and 45 Special Attack does not get a special build generated at all.
- A species with an unevolved form and Eviolite-compatible bulk gets that build; one with no recovery gets Assault Vest considered.
- Move slots are filled from the pool **available at that checkpoint**, not the lifetime pool.

The item, nature and move slots are filled by the species. This is what makes invariant I6 (§4.9) a meaningful test rather than a formality.

The full enumerated set is retained internally. What is *published* per (species-form, checkpoint) are two anchor builds — the floor and the ceiling of §4.4.

### 4.4 What the player sees: floor, ceiling, ROI, and VORP

The matrix is the engine. The published output is replacement-relative value, expressed at two anchors:

- **Floor** — the zero-investment build: neutral nature, 0 EVs, 31 IVs, the more common ability, no held item, level-up moves only. What you get if you simply catch it and use it.
- **Ceiling** — best nature, best EV spread, best ability, best held item, best available moves, **gated by what Phase 2 confirms is obtainable by that checkpoint.** A ceiling resting on an item the player cannot hold for two more badges is a fiction; cap it at what is reachable and name the gate.
- **`investment_cost`** — a documented composite of what the ceiling requires: breeding for an egg move or ability, EV training time, a contested TM, a one-of-a-kind item, a specific nature, an evolution item.
- **`ROI = (Ceiling − Floor) / investment_cost`**
- The ceiling's exact build is stored, so it can be reproduced and argued with.

A hyper-specialist that needs perfect setup lands with a modest floor, a high ceiling, and high ROI. A naturally excellent species lands with a high floor and lower ROI. Both patterns must be visible in the table without reading the prose.

**Replacement baseline.** VORP is meaningless until replacement level is defined. Default construction, overridable in the target config:

> For a given (checkpoint, role) cell, replacement level is the performance of the **third-best obtainable species-form for that role at that checkpoint under zero investment.** "Obtainable" means Phase 1 availability places it in the player's hands by that checkpoint.

**Percentile-normalize within the obtainable pool at each checkpoint**, never min-max across the whole dex, or legendaries flatten everyone else.

### 4.5 Roles, not one ladder

A single ranked list collapses into a DPS list. Every build is scored against a fixed set of **roles**, and rankings are published per role. The taxonomy lives in `references/roles.md`:

| Family | Roles |
|---|---|
| Offense | Wallbreaker (physical / special) · Setup Sweeper · Revenge Killer · Trick Room Attacker · Priority Abuser · Mixed Attacker |
| Defense | Physical Wall · Special Wall · Mixed Wall · Regenerator Pivot · Tank |
| Utility | Hazard Setter · Hazard Remover · Cleric · Status Spreader · Screen Setter · Phazer · Trapper · Weather / Terrain Setter · Speed Control · Suicide Lead |
| Enabler | Sacrificial Pivot · Redirection · Baton Passer |

Three rules govern scoring:

**Gates before scores.** Every role has binary requirements. Fail one and the build is disqualified regardless of stats — a wall without recovery is not a wall. Gates evaluate against the moves and abilities **available at that checkpoint**, not the lifetime pool. A wall whose recovery move is learned at level 52 under a level-40 cap does not pass the recovery gate yet.

**Fight fit.** `role_fit = w_stat·S + w_tool·T + w_type·Y + w_fight·F`, weights summing to 1, with all four components reported alongside the total. `F` is the boss-relative term and is what distinguishes this from a generic tier list. A hazard setter is near-worthless against a three-Pokémon gym and excellent against a six-Pokémon Elite Four member with three Stealth Rock weaknesses. Where a role's `F` is zero at a checkpoint, say so — "no hazard setter is worth a slot against this gym" is a real finding.

**Report the top three, not the winner.** Many species-forms are genuinely hybrid. Emit a ranked list of role fits; name the top one `primary_role`, and where the runner-up is within ~0.05, mark it a hybrid and name both. Species-forms that fail every gate are a finding, not a bug — report the count and name a sample. Do not invent a "generalist" bucket to absorb them.

### 4.6 Lineage: scored forward, with a dead-weight penalty

A species' value includes what it becomes. Mudkip is not scored as Mudkip.

For each checkpoint, determine which form the lineage is realistically in at that point, given the evolution level or item and its Phase 2 gate, and score **that form**. The lineage-adjusted score is the checkpoint-weighted aggregate across the whole line, with an explicit **dead-weight penalty** for checkpoints where the line is stuck in an underperforming form.

Store the per-checkpoint form used, the raw score, and the penalty separately, so the adjustment is auditable rather than a black box. Store both the form's own score and its lineage-adjusted score in the same row.

A weak species that becomes a top-3 answer two checkpoints later is flagged as an **investment**, with the payoff checkpoint and the cost to get there stated explicitly. This is the mechanism that makes the route checklist (§5) a list of what to catch rather than a list of what is strong right now.

### 4.7 Team layer

Team value is a **marginal contribution** measure, computed by beam search over teams of six drawn from the checkpoint's available pool:

- A team's fit against a boss = coverage of that boss's threat set, weighted by how badly each unanswered threat loses the fight.
- A build's team score = how often it appears in the top-N teams, and how much the best team degrades when it is removed.

This enforces diversity structurally rather than by fiat: six copies of the same wallbreaker cover one threat six times, so the search selects complements. **Team recommendations must be simultaneously feasible** — two members cannot both hold the game's single Choice Scarf.

### 4.8 Inputs to a build's score

In roughly descending order of impact:

| Input | Treatment |
|---|---|
| Base stats | Drive which builds are even generated (§4.3) |
| Typing | Offensive coverage and defensive matchup vs. the specific boss roster |
| Ability | Enumerated per slot; ability choice is part of the build, never averaged |
| Learnset — level-up | Gated by the level the species is at that checkpoint |
| Learnset — TM/HM | Gated by whether that TM is *obtainable* by that checkpoint, and by copy count |
| Learnset — egg / tutor / event | Gated by whether the parent chain or tutor is obtainable |
| Nature | Enumerated; scored, not assumed |
| Held item | Gated per species by whether it can exploit the item, and by scarcity |
| Lineage | Evolution stage, method, and the level/item/gate required |
| Availability | Which channel, where, and when |

**Scarcity gate.** An item only counts toward a build's headline score if it is *reliably obtainable* — purchasable, or present in at least three copies. The gap between "best item overall" and "best reliably-obtainable item" is published as **item dependence**, per build. A build whose whole case rests on the game's single Life Orb is labeled as such, not quietly credited with it.

### 4.9 The anti-degeneracy invariants

The requirement — *no one item, nature, or moveset should ever be the dominant recommendation* — is a **hard constraint with falsifiable tests**, not an aspiration.

| # | Invariant | Threshold | Checked at |
|---|---|---|---|
| I1 | No single held item in more than 25% of recommended builds | ≤ 0.25 | Phase 5 |
| I2 | No single nature in more than 20% of recommended builds | ≤ 0.20 | Phase 5 |
| I3 | Correlation between final rank score and BST | \|r\| ≤ 0.60 | Phase 5 |
| I4 | Every role at every checkpoint has ≥ 3 species-forms within 10% of the leader | ≥ 3 | Phase 5 |
| I5 | Recommended teams are simultaneously equippable given copy counts | 100% | Phase 5 |
| I6 | Perturbing base stats by ±15 changes the recommended build for ≥ 20% of species | ≥ 0.20 | Phase 6 |
| I7 | No move in more than 30% of recommended movesets (obligatory STAB fillers excluded and reported separately) | ≤ 0.30 | Phase 5 |

**All seven block release.** A failure is not a note; it stops the export.

**I3 has a floor as well as a ceiling.** Correlation with BST should be *moderate*, not zero — strong Pokémon are strong. Near-1.0 means the model is an expensive way to sort by BST. Below about 0.25 it is probably broken in the other direction; that gets **reported, not blocked**. The prior modelling pass on SABLE landed at r ≈ 0.46, which is the target band and the reason 0.60 is the ceiling rather than the looser 0.70 used elsewhere. Report the coefficient with its n every time.

**I6 runs on a stratified sample of ~150 species-forms, once, at Phase 6.** It is the direct test of "base stats determine the build" — if stat spreads can be scrambled without changing recommendations, the build generator is not reading them. It is also the only invariant that requires re-running the pipeline, so it is sampled and run once rather than on every export. Sampling is stratified across BST quartiles and across evolution stages; the sample and its seed are recorded so the run is reproducible.

### 4.10 Availability gating

An S-tier build requiring a TM found after the fight it would win is worth nothing. Every score is computed at a checkpoint, with:

- **Level cap** applied — read it from source, never assume one
- **TM/HM availability** derived from actual placement in map data, ground items, scripts and mart tables
- **Item copy counts** literal — a script granting ten copies grants ten; mart stock is unlimited supply
- **Species availability** across all channels: wild slots, gifts, eggs, in-game trades, static encounters, starters, boss rewards
- **Evolution feasibility** — a trade evolution with no trade partner is not feasible

### 4.11 Published outputs

- Per-role, per-checkpoint ladders
- Per-species-form dossier: floor, ceiling, ROI, item dependence, investment payoff, per-checkpoint curve, and the boss Pokémon it beats and loses to
- Per-boss threat sheet: the roster, its threats ranked, and the current-pool answers to each
- Tier assignment (S+ / S / A / B / C / D / F) with thresholds stated numerically and the resulting distribution reported. **Do not force a curve.** If the hack genuinely has fourteen S-tier options, that is the finding.
- `cant_miss` flag — high value combined with one-time or missable availability. This is the app's priority marker, so its rule is written down, not vibed.
- The full 1v1 matrix as a machine-readable artifact, partitioned per checkpoint where row counts demand it

---

## 5. Pillar II — Route and encounter checklist

### 5.1 Model

The world is a **progression graph**: maps as nodes, gated by checkpoint. Each node carries encounters (with slot rates), ground items, hidden items, TMs, trainers, NPCs, shops, and one-time events.

### 5.2 Route priority scoring

Each location gets a grade with a stated reason, from four terms:

| Term | Question it answers |
|---|---|
| **Immediate value** | Does anything here improve the team for the *next* boss? |
| **Lineage value** | Does anything here evolve into a top answer for a *later* boss, and is the investment cost worth it? |
| **Scarcity** | Is anything here unavailable or much harder to get elsewhere? |
| **Missability** | Is anything here permanently lost if I walk past it? |

Scarcity and missability weigh hardest, because they are the only irreversible ones. A route full of good-but-common encounters is a B; a route with one one-time gift that becomes a top-5 answer at the Elite Four is an A regardless of what else it holds.

### 5.3 Per-route breakdown

- Encounter table with slot rates, level ranges, and each species' current and projected role ranks
- A **catch priority** ordering with a one-line reason each
- Items and TMs, flagged with which species they unlock a build for
- Trainers worth fighting for a specific reason
- Explicit **missable list**, with the gate after which each is lost
- A "safe to skip" verdict when that is the honest answer

### 5.4 Checklist behavior

The route view is stateful for a single run — caught / obtained / skipped, with the ability to ask *"what have I passed that I shouldn't have?"* It ships as a tab in the companion app (§6). **Run state lives in an INTERNAL file and never in the repo**, and the app holds it in memory only.

---

## 6. Pillar III — Presentation

Three depths, always all three. A verdict without a drill-down is unfalsifiable; a spreadsheet without a verdict is homework.

| Depth | Form | Purpose | Test of success |
|---|---|---|---|
| **Glance** | One screen. A verdict and three bullets. | Mid-session, in-game decisions | Readable on a phone between battles |
| **Working** | Sortable tables, workbook, filterable app, charts | Planning between sessions | Every recommendation is comparable against its alternatives |
| **Audit** | Full derivation, source file and line references, integrity log, invariant results | Trusting the above | Any single number traces to the file it came from |

**Depths are layers of the same artifacts, not three separate files.** Working is the companion app plus the xlsx workbook. Audit is the bundle's `00_README.md` with the Integrity Log and invariant report folded in. Glance is a tab in the app. Nothing ships as a standalone depth document.

The Glance layer is the one most often skipped and the one actually read most. Write it last, from the finished analysis, and make it commit. "It depends" is not a Glance answer; "lead with X, your weak slot is Y, don't skip the gift on Route 116" is.

Rules:
- Every displayed number carries a confidence tier (§7). A number without one is a bug.
- Charts serve a decision. If you can't name the decision a chart informs, cut it.
- Deliverables are self-contained: the app is a single HTML file that opens offline, with no build step and no CDN dependency.
- Data ships **human-readable and machine-readable**: TSV bundle + README for whole databases, CSV + JSON for single results.
- The primary human-readable deliverable for a modelling pass is an **xlsx workbook that shows the work** — intermediate columns visible, live Excel formulas rather than hardcoded values wherever practical, so a weight can be changed and the ladder watched to move.

---

## 7. Data discipline

### 7.1 Non-negotiables

1. **Every number is computed, not recalled.** Memory of vanilla base stats, movepools, or type charts is a hypothesis. Load the file, run the code, show the arithmetic. This matters more here than in most analysis, because difficulty hacks exist precisely to break the assumptions that would otherwise be imported.
2. **No information is dropped, ever.** If the source has it, the dataset has it. If a field is empty in the source, encode the sentinel; do not omit the column. If a row is excluded from an aggregate, the Integrity Log names the row and the reason, and the analysis reports the figure both ways where the difference is material.
3. **Ambiguity gets named, not smoothed.** Two sources disagreeing is a deliverable. A clean answer resting on a silent assumption is a defect.
4. **Verify before presenting.** Re-read every file written, confirm row counts round-trip, and decode at least three encoded cells back to something recognizable. Never present a file that has not been re-read from disk.

### 7.2 Encoding conventions

| Convention | Format | Example |
|---|---|---|
| List | comma-separated | `4,7,12` |
| Key:value pairs | `key:value`, comma-separated | `33:1,45:3` (move 33 at level 1) |
| Grouped records | pipe-separated records, colon-separated fields | `route101:grass:2-4:20:day` |
| Not applicable | `NA` | |
| Empty but valid | `NONE` | |
| Unknown / absent from source | `UNK` | |
| Literal tab, newline or pipe in a value | escaped `\t`, `\n`, `\|` | |

`NA`, `NONE`, and `UNK` mean three different things and must never be collapsed. `NONE` is a measurement — this species has no egg moves. `UNK` is a gap — the source does not say. `NA` is a category error — a legendary has no egg group.

### 7.3 Confidence tiers

Four tiers, applied to every published field:

- **Measured** — parsed directly from source; the file and line can be named
- **Derived** — computed from Measured inputs by a stated formula (this includes every damage calculation)
- **Inferred** — reasoned from context, including interpretive prose such as a boss's win condition
- **Asserted** — taken from a secondary source without source confirmation

There is no `Unresolved` tier and no `Speculative` tier. **Gaps are carried by the `UNK` sentinel in the data and by the Integrity Log in prose**, not by the confidence column — the tier says *how we know*, never *whether we know*. Anything that would otherwise be Recalled is either verified into one of the four tiers, or encoded `UNK` and logged. It is never silently omitted.

In tables the tier is a column. In prose it is a clause. In the workbook it is a header note or a README legend. On a Glance card, one tier may cover the whole card if every number shares it — and the exceptions must be named.

The tiers exist so a reader can accept the measurements and reject the interpretation independently. That only works if the seam is visible everywhere, not just in the audit layer.

### 7.4 Source hierarchy

| Priority | Source | Use |
|---|---|---|
| 1 | Hack source repo (`release` branch) | All numeric data, all placements, all rosters |
| 2 | `@smogon/calc` fork | **Mechanics engine only.** Its bundled data layer is never used |
| 3 | Hack's website pages | Ordering, prose context, things genuinely absent from source |
| 4 | Model knowledge | Hypothesis generation only. Never a value in a shipped artifact |

The decompilation always wins. Website pages are useful for knowing *what to go look for in source* and for progression ordering that source doesn't encode. Where site and source disagree, source is used and **the disagreement is logged as a finding.**

---

## 8. Framework portability

The line between HALYARD and a target is the **adapter**. A new hack is onboarded by supplying:

1. **Source binding** — repo and branch, or a directory of exported data
2. **Parser bindings** — where species, moves, abilities, items, learnsets, encounters, trainers, evolutions and maps live in *that* codebase's layout
3. **Checkpoint list** — the ordered progression gates and the flag or map that gates each
4. **Boss roster mapping** — which trainer entries count as bosses at which checkpoint
5. **Mechanics config** — generation-dependent switches, read from the hack's own config headers where possible
6. **House rules** — the player's own run constraints

Everything else — build generation, matchup computation, role scoring, valuation, team search, invariant checks, exports, the app — is target-agnostic and lives in the core.

**Portability test:** onboarding target 02 must require zero edits to files outside `targets/`.

**Checkpoints are any progression gate, not only bosses.** A mid-region HM unlock changes the available pool and often the level cap, so it is a real checkpoint. Gates without a roster of their own are **scored against the roster of the next boss ahead of them** — the fight they are preparing you for. Every checkpoint constrains availability; not every checkpoint has its own fight.

---

## 9. INTERNAL vs EXTERNAL

Classify at creation, not at publication. Retrofitting a classification onto a folder is how private run state ends up in a public repo.

**INTERNAL — local disk only.** Cloned hack source and raw dumps; snapshots of scraped pages; intermediate parse artifacts; weight-tuning worksheets and calibration notes; **personal run state** — the actual team, checklist progress, house rules, save data; the filled target configuration block; anything that only makes sense with the target's source tree present.
Naming: `INT_<topic>_<version>.<ext>`.

**EXTERNAL — ships to the repo.** The engine, parsers, adapters, and the analysis skill; processed self-describing datasets; the rendered app; documentation including this file and the `RUNBOOK.md` template; integrity logs and invariant reports.
Naming: `EXT_<topic>_<version>.<ext>`, or conventional repo names once the layout is in place.

**The test:** can this artifact be used by someone who doesn't have the source tree? If yes, EXTERNAL.

**The one deliberate exception:** parsers and the engine are EXTERNAL although they consume source. The strict test would push them INTERNAL, but the reusable engine *is* the product, and needing a target to run against is the point of the portability goal. Raw source stays INTERNAL; code that reads it ships.

When something genuinely fits neither bucket, ask rather than guess. The cost is asymmetric — an over-cautious INTERNAL classification costs nothing but a conversation.

---

## 10. Repository layout

```
halyard/
├── README.md                  # generic description, no franchise terms
├── VISION.md                  # this document
├── RUNBOOK.md                 # working prompt template, target block empty
├── core/
│   ├── ingest/                # format-agnostic parsers
│   ├── model/                 # build generation, 1v1 matrix, roles, valuation, team search
│   ├── invariants/            # the I1–I7 checks
│   └── export/                # dataset + bundle writers
├── targets/
│   └── sable/
│       ├── adapter.py         # parser bindings for this codebase layout
│       ├── checkpoints.yaml   # progression gates, level caps, boss mapping
│       └── mechanics.yaml     # generation config overrides
├── skill/                     # the analysis skill
├── datasets/sable/            # processed EXTERNAL bundle
└── app/                       # single self-contained HTML companion
```

---

## 11. Phases

Seven phases, each ending in a hard gate. At a gate: present row counts, the Integrity Log, and the validation numbers, then **stop and wait for explicit sign-off.** Do not run ahead.

| Phase | Deliverable | Gate |
|---|---|---|
| **1** | `01_species.tsv` — species-form master | Row count, starter count, zero-movepool count, unresolved evolution targets |
| **2** | `02_world.tsv` — items, TMs, vendors, trades, gates | Row count by entity type, items with no location, `earliest_gate` = `UNK` count |
| **3** | `03_trainers.tsv` — trainers, bosses, checkpoint graph | Trainer and slot counts, unresolved roster references, boss level curve |
| **4** | `04_matchups.tsv` — build generation + 1v1 matrix | Cell count, calc reproducibility spot-check, unsupported-mechanic count |
| **5** | `05_valuation.tsv` — roles, floor/ceiling/ROI, VORP, teams | I1–I5, I7 pass; tier distribution; BST correlation with n |
| **6** | Evaluation — no new dataset | I6 passes; round-trip; sensitivity pass; consolidated Integrity Log |
| **7** | Companion app | Opens offline; every number traces to a dataset row |

Portability proof — onboarding target 02 with zero edits outside `targets/` — is the v1 exit criterion, run after Phase 7.

---

## 12. What the framework needs from the user before Phase 1

If anything here is missing, say exactly what is missing and what it blocks.

1. **The data files** — species/base stats, movepools (level-up, TM, tutor, egg), evolutions, abilities, moves, items, encounter tables, trainer rosters, map/location data, TM/HM list.
2. **Base and mechanics.** What the hack derives from, and which generation's mechanics it uses. Physical/special split, Fairy type, crit rates, EXP share behavior, damage formula generation. Every calc inherits this.
3. **Custom content.** Moves, abilities, items or species unique to the hack that will not exist in the calculator's data layer.
4. **Difficulty mode.** If the hack has several, which one is canonical. Boss rosters usually differ.
5. **Level caps and obedience.** Whether enforced, and at what values.
6. **The rules of the run.** This defines "viability" and materially changes role weights — nuzlocke rules make survivability and revenge-killing far more valuable than raw damage. Normal / nuzlocke / set mode / item clause / species clause / box-swapping or a locked six.
7. **Investment tools available.** Vitamins, bottle caps, mints, ability capsules and patches, EV-reducing berries, the move relearner. These set the ceiling and change ROI significantly.
8. **EV/IV assumption** for the ceiling, if not the default.
9. **Boss set.** Gyms only, or gyms + rivals + Elite Four + admins + optional superbosses. Default: all named-trainer fights, weighted by difficulty.
10. **Legendaries and mythicals** — in-pool or excluded. Default: in-pool but flagged, since availability gating already handles most of the distortion.
11. **A vanilla dump**, if a base-game comparison is wanted. Without one, any vanilla baseline is Inferred and labeled so.
12. **Replacement-level definition**, if the default third-best-obtainable construction is not what is wanted.

---

## 13. Non-goals for v1

- Live game-state integration
- Multiplayer, PvP, or competitive metagame analysis
- A hosted web app or any public deployment
- Breeding/IV optimization tooling
- Speedrun routing
- Supporting hacks outside the `pokeemerald-expansion` and Essentials families

---

*This document is the reference point for scope disputes. When a proposed feature isn't covered here, either it's out of scope or this document is out of date — resolve which before building it.*
