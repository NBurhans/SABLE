#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 4d.1: the held-item catalogue.

The generator previously drew from a hand-written 13-item list, so Leftovers
(47.6%) and Life Orb (42.2%) took 90% of published ceilings and I1 failed by a
wide margin. The world table actually carries 194 items with a hold effect, 90
of them reliably obtainable, including a complete set of 18 type-boost items and
18 resist berries that never entered the generator at all.

This derives the catalogue from `hold_effect` in `02_world.tsv` rather than from
a list written by hand, so an item added to the hack appears automatically and
the diversity is a property of the data, not of my typing.

Per builds.md s4 an item is generated only if all three hold:
  1. the species can exploit it        -> `class` + predicate, below
  2. Phase 2 says it is obtainable     -> presence in 02_world.tsv
  3. scarcity                          -> purchasable, or >= 3 copies

Diversity here is VERIFIED, not manufactured. Nothing rotates items to spread
the distribution; the catalogue simply stops hiding 90% of the real options.
"""
import csv, json, collections, re

OUT = "/home/claude/out"
WORK = "/home/claude/work"

# hold_effect -> (class, parameter). The class drives the exploitability
# predicate in the generator; the parameter carries the type where relevant.
TYPE_POWER = {
    "FIGHTING_POWER": "Fighting", "DARK_POWER": "Dark", "FIRE_POWER": "Fire",
    "DRAGON_POWER": "Dragon", "FAIRY_POWER": "Fairy", "ROCK_POWER": "Rock",
    "ELECTRIC_POWER": "Electric", "STEEL_POWER": "Steel", "GRASS_POWER": "Grass",
    "WATER_POWER": "Water", "ICE_POWER": "Ice", "POISON_POWER": "Poison",
    "FLYING_POWER": "Flying", "NORMAL_POWER": "Normal", "BUG_POWER": "Bug",
    "GROUND_POWER": "Ground", "GHOST_POWER": "Ghost", "PSYCHIC_POWER": "Psychic",
}

# resist berries: the type each one halves. Taken from the berry's own name,
# which is stable across generations; the calculator applies the mechanic.
BERRY_RESIST = {
    "Occa Berry": "Fire", "Passho Berry": "Water", "Wacan Berry": "Electric",
    "Rindo Berry": "Grass", "Yache Berry": "Ice", "Chople Berry": "Fighting",
    "Kebia Berry": "Poison", "Shuca Berry": "Ground", "Coba Berry": "Flying",
    "Payapa Berry": "Psychic", "Tanga Berry": "Bug", "Charti Berry": "Rock",
    "Kasib Berry": "Ghost", "Haban Berry": "Dragon", "Colbur Berry": "Dark",
    "Babiri Berry": "Steel", "Chilan Berry": "Normal", "Roseli Berry": "Fairy",
}

# hold effects with no damage-formula or survivability consequence this model
# reads. Listed explicitly rather than omitted, so a future gap is visible.
NO_BUILD_EFFECT = {
    "CAN_ALWAYS_RUN", "PREVENT_EVOLVE_ITEM", "REPEL", "MACHO_BRACE",
    "EXP_SHARE", "AMULET_COIN", "CLEANSE_TAG", "SHED_SHELL", "SMOKE_BALL",
    "LUCKY_EGG", "SOOTHE_BELL", "EVERSTONE", "QUICK_POWDER", "IRON_BALL",
    "FLOAT_STONE", "TERRAIN_EXTENDER", "DOUBLE_PRIZE", "FRIENDSHIP_UP",
    "RANDOM_STAT_UP", "CONFUSE_SPICY", "CONFUSE_SOUR",
}

CLASS_BY_EFFECT = {
    "LEFTOVERS": "longevity", "RESTORE_PCT_HP": "longevity",
    "RESTORE_HP": "longevity", "BLACK_SLUDGE": "longevity_poison",
    "LIFE_ORB": "allout", "EXPERT_BELT": "coverage", "WIDE_LENS": "accuracy",
    "CHOICE_BAND": "choice_phys", "CHOICE_SPECS": "choice_spec",
    "CHOICE_SCARF": "choice_speed", "ASSAULT_VEST": "spdef_novstatus",
    "PREVENT_EVOLVE": "eviolite", "FOCUS_SASH": "sash", "FOCUS_BAND": "sash",
    "ROCKY_HELMET": "contact_punish", "AIR_BALLOON": "ground_immune",
    "TOXIC_ORB": "self_poison", "FLAME_ORB": "self_burn",
    "THICK_CLUB": "species_locked", "LIGHT_BALL": "species_locked",
    "DEEP_SEA_TOOTH": "species_locked", "DEEP_SEA_SCALE": "species_locked",
    "SOUL_DEW": "species_locked", "MEGA_STONE": "mega",
    "PRIMAL_ORB": "primal", "GRISEOUS_ORB": "species_locked",
    "HEAT_ROCK": "weather_ext", "DAMP_ROCK": "weather_ext",
    "ICY_ROCK": "weather_ext", "SMOOTH_ROCK": "weather_ext",
    "LIGHT_CLAY": "screen_ext", "SEEDS": "terrain_seed",
    "POWER_HERB": "charge", "MENTAL_HERB": "utility_misc",
    "WHITE_HERB": "utility_misc", "RESTORE_STATS": "utility_misc",
    "ABSORB_BULB": "utility_misc", "CELL_BATTERY": "utility_misc",
    "CURE_PSN": "status_cure", "CURE_PAR": "status_cure", "CURE_SLP": "status_cure",
    "CURE_FRZ": "status_cure", "CURE_BRN": "status_cure",
    "CURE_CONFUSION": "status_cure", "CURE_STATUS": "status_cure",
    "HEAVY_DUTY_BOOTS": "hazard_immune", "OGERPON_MASK": "species_locked",
    "FLINCH": "flinch",
    # effect codes this hack uses that the first mapping pass missed. Each was
    # visible in the unmapped counter, which is why the counter exists.
    "EVIOLITE": "eviolite", "MUSCLE_BAND": "band_phys", "WISE_GLASSES": "band_spec",
    "PUNCHING_GLOVE": "punch_boost", "KICKING_SHOES": "kick_boost",
    "SCOPE_LENS": "crit", "CRITICAL_UP": "crit", "LEEK": "species_locked",
    "SHELL_BELL": "longevity", "BIG_ROOT": "drain_boost",
    "LOADED_DICE": "multihit_boost", "WEAKNESS_POLICY": "weakness_policy",
    "THROAT_SPRAY": "sound_boost", "BOOSTER_ENERGY": "paradox_boost",
    "PLATE": "type_plate", "DRIVE": "type_plate", "MEMORY": "type_plate",
    "SAFETY_GOGGLES": "utility_misc", "PROTECTIVE_PADS": "utility_misc",
    "EJECT_BUTTON": "utility_misc", "QUICK_CLAW": "utility_misc",
    "METRONOME": "metronome", "EVASION_UP": "utility_misc",
}


def main():
    world = list(csv.DictReader(open(f"{OUT}/02_world.tsv"), delimiter="\t"))
    qty, mart, he, name = collections.defaultdict(int), set(), {}, {}
    for r in world:
        if r["entity_type"] == "mart_stock":
            mart.add(r["item_const"])
        else:
            try: qty[r["item_const"]] += int(r["quantity"])
            except ValueError: qty[r["item_const"]] += 1
        if r["hold_effect"] not in ("NONE", "UNK", "", "NA"):
            he[r["item_const"]] = r["hold_effect"]
        name[r["item_const"]] = r["item_name"]

    cat, skipped = {}, collections.Counter()
    for const, effect in sorted(he.items()):
        nm = name.get(const, const)
        if nm in ("NONE", "UNK", ""):
            nm = const.replace("ITEM_", "").replace("_", " ").title()
        reliable = const in mart or qty.get(const, 0) >= 3
        copies = "unlimited" if const in mart else qty.get(const, 0)

        if effect in NO_BUILD_EFFECT:
            skipped["no_build_effect"] += 1
            continue
        if effect in TYPE_POWER:
            cls, param = "type_boost", TYPE_POWER[effect]
        elif effect == "RESIST_BERRY":
            param = BERRY_RESIST.get(nm)
            if param is None:
                skipped["berry_type_unknown"] += 1
                continue
            cls = "resist_berry"
        else:
            cls = CLASS_BY_EFFECT.get(effect)
            param = None
            if cls is None:
                skipped[f"unmapped:{effect}"] += 1
                continue

        cat[const] = {"name": nm, "hold_effect": effect, "class": cls,
                      "param": param, "reliable": reliable, "copies": copies}

    json.dump(cat, open(f"{WORK}/item_catalog.json", "w"), indent=1)
    by_cls = collections.Counter(v["class"] for v in cat.values())
    rel = sum(1 for v in cat.values() if v["reliable"])
    print(f"catalogue: {len(cat)} held items ({rel} reliable, {len(cat)-rel} scarce)")
    print(f"  previous hand-written list: 13 items")
    for k, v in by_cls.most_common():
        r = sum(1 for x in cat.values() if x["class"] == k and x["reliable"])
        print(f"  {k:<20} {v:>3}  ({r} reliable)")
    print()
    print("not catalogued, by reason:")
    for k, v in skipped.most_common():
        print(f"  {k:<28} {v}")

if __name__ == "__main__":
    main()
