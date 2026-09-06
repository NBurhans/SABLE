# HALYARD / target SABLE — build generation and pruning rules

Phase 4 enumerates builds before anything is scored. A build that is never
generated can never be recommended, so a bad prune is invisible in the final
ladder — it just quietly removes options. These rules are therefore explicit,
recorded per species, and auditable.

**Design principle (from the player):** builds should complement each species'
stat spread and movepool. Diversity matters, but never at the cost of
usability. Some Pokemon are pure damage; some carry no damaging move at all.
Both are correct outcomes when the species supports them.

**Diversity is verified, not manufactured.** The generator picks what actually
fits each species. Invariants I1 (item ≤25%), I2 (nature ≤20%) and I7 (move
≤30%) then test whether the result collapsed. Rotating choices to spread the
distribution would pass those checks while producing worse advice, so it is
forbidden. If the invariants fail, the fix is in the scoring weights, not in
padding the build list.

---

## 1. Attack orientation — decides which builds exist at all

Computed per species-form from base stats **and** the movepool available at
that checkpoint, never from stats alone. A 130 Atk species with no physical
STAB is not a physical attacker.

Let `P` = base Attack, `S` = base Sp. Attack, and let `bestP` / `bestS` be the
highest base power damaging move of each category available at that checkpoint.

| Condition | Builds generated |
|---|---|
| `P ≥ 1.15·S` and `bestP ≥ 60` | physical only |
| `S ≥ 1.15·P` and `bestS ≥ 60` | special only |
| within 15% of each other, both `best ≥ 60` | physical, special, **and** mixed |
| both `best < 60`, or `max(P,S) < 60` | no attacking build; support track only |

The mixed build is generated only where the movepool genuinely supports it.
Mixed is a real archetype in this hack — Flygon and Infernape both appear on
boss rosters with split spreads — but it is a minority case, not a default.

## 2. Support track — builds with zero damaging moves

Explicitly permitted. A species enters the support track when **both** hold:

- it passes at least one utility-role gate at that checkpoint: reliable
  recovery, hazard setting or removal, cleric access, phazing, screens,
  redirection, or Trick Room / weather / terrain setting; **and**
- its offensive output is weak — `max(P,S) < 80`, or no STAB above 60 BP.

A support-track species generates builds with 0 to 2 damaging moves. Blissey,
Shuckle and Cofagrigus should land here; if they don't, the gates are wrong.
Species that qualify for both tracks generate both, and the matrix decides.

Note the hack's QoL changes matter here: TMs are reusable and egg moves are
relearnable from the party menu, so utility movepools are far deeper than the
level-up list suggests. Utility gates evaluate the full obtainable pool.

## 3. Nature — chosen, never defaulted

Candidate natures come from what the build is trying to do. No global default,
and no neutral-nature fallback except where the spread is genuinely symmetric.

- Boost the used offensive stat; drop the unused one. A physical build takes
  the −SpA nature, a special build the −Atk.
- Speed-boosting natures are generated **only when they change an outcome** —
  the species must cross at least one boss Pokemon's speed tier at that
  checkpoint that it would otherwise lose. Otherwise generate the
  bulk-boosting nature instead. This is the single biggest source of
  Jolly/Timid monoculture in naive generators.
- Support-track and wall builds take defensive natures, chosen against the
  damage type they are actually being asked to absorb.
- Mixed builds take a speed or neutral nature, since neither offense can be cut.

## 4. Held item — gated three ways

An item is generated only if all three hold:

1. **The species can exploit it.** No Choice items on a build with setup or
   status moves. No Eviolite unless unevolved at that checkpoint. No Life Orb
   stacked with recoil. Assault Vest only on builds with four damaging moves.
2. **Phase 2 says it is obtainable by that checkpoint** (`earliest_gate`).
3. **Scarcity.** Headline builds use reliably obtainable items only —
   purchasable, or three or more copies. One-of-a-kind items generate a
   separate flagged build, and the gap is published as item dependence.

Mega stones are their own case: a mega build is generated for the base species
and gated on its stone, with the mega form's stats and ability substituted.

## 5. Move slots

Four slots, filled from the pool obtainable at that checkpoint — level-up moves
under the cap, TMs whose gate has passed, egg moves (relearner access makes
these effectively free), tutor moves (converted to TMs in this hack).

- At least one STAB where a damaging STAB exists.
- Coverage chosen to maximise distinct super-effective matchups **against that
  checkpoint's actual boss roster**, not against the type chart in the abstract.
  This is what keeps the move distribution from collapsing onto the same four
  neutral-coverage moves.
- Remaining slots go to setup, recovery, status or utility where the species'
  role gates justify them.
- Never generate two moves of the same type and category unless the second has
  a distinct effect that changes an outcome.

## 6. Combinatorial cap

Full enumeration of ability x nature x item x four moves is not tractable
across ~1,500 species-forms and 19 checkpoints. The generator keeps, per
(species-form, checkpoint):

- every legal **ability** (ability choice is part of the build, never averaged)
- up to **3 natures** surviving section 3
- up to **4 items** surviving section 4
- up to **6 movesets** surviving section 5

Ceiling is roughly 2 x 3 x 4 x 6 = 144 builds per species-form per checkpoint,
pruned further by the gates. The two published anchors remain Floor and
Ceiling; the full enumerated set is retained internally for audit.

## 7. What gets recorded

Per species-form and checkpoint, the generator writes: the orientation verdict
and the numbers behind it, which tracks were opened, how many candidates each
stage produced and how many survived, and every rule that fired to remove a
candidate. Without that trace, section 6's cap is indistinguishable from a bug.
