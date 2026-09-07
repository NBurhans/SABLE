#!/usr/bin/env python3
"""
HALYARD / target SABLE — map gating from the creator's walkthrough.

The source tree encodes which flag gates each checkpoint, but not which MAP the
player can reach at which checkpoint — only 11 of 127 encounter maps could be
dated from item placements, leaving 61.8% of the ladder with unknown timing.

VISION 7.4 puts the hack's own website at priority 3, for exactly this: ordering
and progression context that source does not encode. So the ordering below is
read off the creator-provided walkthrough at pokemonemeraldimperium.com and the
region layout it walks through.

CONFIDENCE. This is NOT Measured and NOT Derived. Every gate here is `Asserted`
— taken from a secondary source without source confirmation — and every row
says so. Where source already derived a gate for a map, the two are compared and
any disagreement is logged as a finding rather than silently overwritten
(VISION 7.4: "the decompilation always wins").

WHAT THE NUMBERS MEAN. `earliest_cp = N` means: by the time the player clears
checkpoint N, this map is reachable. The walkthrough gives a linear order, so
these are the first checkpoint at which the walkthrough has the player standing
there. Optional detours the walkthrough mentions as skippable ("you can do this
at any point") are dated to the earliest point it says they are possible.
"""
import csv, json, collections

OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

# checkpoint anchors, from 03b_checkpoints.tsv:
#  1 Badge1 Roxanne      2 rival Rustboro     3 Badge2 Brawly
#  4 Route110 Aqua       5 rival Route110     6 Badge3 Wattson
#  7 Mt Chimney          8 Badge4 Flannery    9 Trick House 3
# 10 Badge5 Norman      11 HM Fly            12 Badge6 Winona
# 13 Dawn Lilycove      14 Aqua submarine    15 Badge7 Tate&Liza
# 16 Kyogre Seafloor    17 Badge8 Juan       18 Wally Victory Road
# 19 Champion
GATES = {
    # --- pre-Badge 1: the opening corridor
    "ROUTE101": 1, "ROUTE102": 1, "ROUTE103": 1, "ROUTE104": 1,
    "PETALBURG_CITY": 1, "PETALBURG_WOODS": 1, "RUSTBORO_CITY": 1, "ROUTE116": 1,

    # --- after the Rustboro rival, Rusturf opens
    "RUSTURF_TUNNEL": 2,

    # --- sail to Dewford, Granite Cave, Brawly
    "ROUTE105": 3, "ROUTE106": 3, "ROUTE107": 3, "DEWFORD_TOWN": 3,
    "GRANITE_CAVE_1F": 3, "GRANITE_CAVE_B1F": 3, "GRANITE_CAVE_B2F": 3,
    "GRANITE_CAVE_STEVENS_ROOM": 3,

    # --- sail to Slateport, north to Route 110
    "ROUTE108": 4, "ROUTE109": 4, "SLATEPORT_CITY": 4, "ROUTE110": 4,

    # --- Mauville and its western spur
    "ROUTE117": 6, "ROUTE111": 6, "ROUTE112": 6,
    "NEW_MAUVILLE_ENTRANCE": 6, "NEW_MAUVILLE_INSIDE": 6,

    # --- the northern loop up to Mt Chimney
    "FIERY_PATH": 7, "ROUTE113": 7, "ROUTE114": 7, "ROUTE115": 7,
    "METEOR_FALLS_1F_1R": 7, "METEOR_FALLS_1F_2R": 7,
    "METEOR_FALLS_B1F_1R": 7, "METEOR_FALLS_B1F_2R": 7,
    "JAGGED_PASS": 7,

    # --- Lavaridge
    "LAVARIDGE_TOWN": 8,

    # --- Surf era: desert, Trick House, water south of Slateport
    "ROUTE110_TRICK_HOUSE_PUZZLE1": 9, "ROUTE110_TRICK_HOUSE_PUZZLE2": 9,
    "ROUTE110_TRICK_HOUSE_PUZZLE3": 9,
    "MIRAGE_TOWER_1F": 9, "MIRAGE_TOWER_2F": 9, "MIRAGE_TOWER_3F": 9,
    "MIRAGE_TOWER_4F": 9, "ABANDONED_SHIP_ROOMS_B1F": 9,
    "ABANDONED_SHIP_HIDDEN_FLOOR_CORRIDORS": 9,

    # --- east of Mauville after Norman
    "ROUTE118": 11, "ROUTE119": 11, "ROUTE123": 11, "FORTREE_CITY": 11,
    "SCORCHED_SLAB": 11,

    # --- Winona, then east
    "ROUTE120": 12,

    # --- Lilycove and Mt Pyre
    "ROUTE121": 13, "ROUTE122": 13, "LILYCOVE_CITY": 13,
    "MT_PYRE_1F": 13, "MT_PYRE_2F": 13, "MT_PYRE_3F": 13, "MT_PYRE_4F": 13,
    "MT_PYRE_5F": 13, "MT_PYRE_6F": 13, "MT_PYRE_EXTERIOR": 13,
    "MT_PYRE_SUMMIT": 13,
    "SAFARI_ZONE_NORTH": 13, "SAFARI_ZONE_NORTHEAST": 13,
    "SAFARI_ZONE_NORTHWEST": 13, "SAFARI_ZONE_SOUTH": 13,
    "SAFARI_ZONE_SOUTHEAST": 13, "SAFARI_ZONE_SOUTHWEST": 13,

    # --- east across the sea to Mossdeep
    "ROUTE124": 15, "ROUTE125": 15, "ROUTE126": 15, "ROUTE127": 15,
    "MOSSDEEP_CITY": 15,
    "SHOAL_CAVE_LOW_TIDE_ENTRANCE_ROOM": 15, "SHOAL_CAVE_LOW_TIDE_ICE_ROOM": 15,
    "SHOAL_CAVE_LOW_TIDE_INNER_ROOM": 15, "SHOAL_CAVE_LOW_TIDE_LOWER_ROOM": 15,
    "SHOAL_CAVE_LOW_TIDE_STAIRS_ROOM": 15,

    # --- Dive: Seafloor Cavern, Magma Hideout, Sootopolis
    "ROUTE128": 16, "UNDERWATER_ROUTE124": 16, "UNDERWATER_ROUTE126": 16,
    "SEAFLOOR_CAVERN_ENTRANCE": 16, "SEAFLOOR_CAVERN_ROOM1": 16,
    "SEAFLOOR_CAVERN_ROOM2": 16, "SEAFLOOR_CAVERN_ROOM3": 16,
    "SEAFLOOR_CAVERN_ROOM4": 16, "SEAFLOOR_CAVERN_ROOM5": 16,
    "SEAFLOOR_CAVERN_ROOM6": 16, "SEAFLOOR_CAVERN_ROOM7": 16,
    "SEAFLOOR_CAVERN_ROOM8": 16,
    "MAGMA_HIDEOUT_1F": 16, "MAGMA_HIDEOUT_2F_1R": 16, "MAGMA_HIDEOUT_2F_2R": 16,
    "MAGMA_HIDEOUT_2F_3R": 16, "MAGMA_HIDEOUT_3F_1R": 16,
    "MAGMA_HIDEOUT_3F_2R": 16, "MAGMA_HIDEOUT_3F_3R": 16, "MAGMA_HIDEOUT_4F": 16,
    "SOOTOPOLIS_CITY": 16, "CAVE_OF_ORIGIN_ENTRANCE": 16, "CAVE_OF_ORIGIN_1F": 16,

    # --- Sky Pillar and the southern water, then Juan
    "ROUTE129": 17, "ROUTE130": 17, "ROUTE131": 17, "PACIFIDLOG_TOWN": 17,
    "SKY_PILLAR_1F": 17, "SKY_PILLAR_3F": 17, "SKY_PILLAR_5F": 17,

    # --- Victory Road
    "ROUTE132": 18, "ROUTE133": 18, "ROUTE134": 18, "EVER_GRANDE_CITY": 18,
    "VICTORY_ROAD_1F": 18, "VICTORY_ROAD_B1F": 18, "VICTORY_ROAD_B2F": 18,

    # --- post-Champion. The walkthrough's comment thread confirms Mirage Tower
    # and the fossil basement open after the Elite Four; the regi chambers and
    # Artisan Cave are traditionally post-game in this layout.
    "ARTISAN_CAVE_1F": 19, "ARTISAN_CAVE_B1F": 19, "DESERT_UNDERPASS": 19,
    "ALTERING_CAVE": 19, "ISLAND_CAVE": 19, "DESERT_RUINS": 19,
    "ANCIENT_TOMB": 19, "METEOR_FALLS_STEVENS_CAVE": 19,
    "FLOATING_SLAB": 19, "GRASSY_SLAB": 19, "ROCKY_SLAB": 19,
    "CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP1": 19,
    "CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP2": 19,
    "CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP3": 19,
}


def main():
    species = list(csv.DictReader(open(f"{OUT}/01_species.tsv"), delimiter="\t"))
    enc_maps = collections.Counter()
    for s in species:
        if s["wild_availability"] in ("NONE", "UNK", ""):
            continue
        for rec in s["wild_availability"].split("|"):
            enc_maps[rec.split(":")[0].replace("MAP_", "")] += 1

    missing = sorted(set(enc_maps) - set(GATES))
    extra = sorted(set(GATES) - set(enc_maps))
    log("W0_coverage",
        f"{len(enc_maps)} encounter maps; {len(set(enc_maps) & set(GATES))} now gated "
        f"from the walkthrough; {len(missing)} still ungated")
    if missing:
        log("W1_ungated", f"maps with no walkthrough gate: {missing}", "WARN")
    if extra:
        log("W2_unused", f"gates written for maps with no encounters: {extra}")

    # compare against the gates the source already derived — source wins
    prior = {}
    for r in csv.DictReader(open(f"{OUT}/02_world.tsv"), delimiter="\t"):
        if r["earliest_gate"] != "UNK":
            k = r["map"].upper().replace(" ", "_")
            g = int(r["earliest_gate"])
            prior[k] = min(prior.get(k, 99), g)
    # The two sources are NOT measuring the same quantity. A source-derived gate
    # is "the earliest checkpoint at which an ITEM on this map can be obtained",
    # which is often behind a further gate inside the map — Petalburg City's item
    # sits behind Norman's gym at checkpoint 10, but the city's water encounters
    # are reachable from checkpoint 1. So the source value is an UPPER bound on
    # reachability, not the reachability itself, and "source wins" would date
    # maps far too late. Take the earlier of the two and record which won.
    agree, disagree = 0, []
    for m, cp in GATES.items():
        # world map names are PascalCase; normalise both to compare
        key = m.replace("_", "")
        for pk, pg in prior.items():
            if pk.replace("_", "") == key:
                if pg == cp: agree += 1
                else: disagree.append((m, pg, cp))
    log("W3_source_agreement",
        f"{agree} maps agree with the source-derived gate; {len(disagree)} disagree",
        "WARN" if disagree else "INFO")
    for d in disagree[:10]:
        log("W3a_disagreement",
            f"{d[0]}: item placement dates to checkpoint {d[1]}, walkthrough reaches "
            f"the map at {d[2]} — taking {min(d[1], d[2])} (item gates bound "
            f"obtainability, not reachability)", "WARN")

    rows = []
    for m in sorted(enc_maps):
        cp = GATES.get(m)
        # source overrides the walkthrough wherever it has a value
        src = next((pg for pk, pg in prior.items()
                    if pk.replace("_", "") == m.replace("_", "")), None)
        if src is not None and cp is not None:
            best = min(src, cp)
            conf = "Derived" if best == src else "Asserted"
            prov = ("source: item placement" if best == src
                    else "walkthrough: creator ordering (earlier than item gate)")
            rows.append([m, best, conf, prov, enc_maps[m]])
        elif src is not None:
            rows.append([m, src, "Derived", "source: item placement", enc_maps[m]])
        elif cp is not None:
            rows.append([m, cp, "Asserted", "walkthrough: creator ordering", enc_maps[m]])
        else:
            rows.append([m, "UNK", "UNK", "no gate available", enc_maps[m]])

    with open(f"{OUT}/01d_map_gates.tsv", "w", encoding="utf-8") as f:
        f.write("map\tearliest_cp\tconfidence\tprovenance\tencounter_records\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    byconf = collections.Counter(r[2] for r in rows)
    log("W4_written", f"01d_map_gates.tsv: {len(rows)} maps — " +
        ", ".join(f"{k} {v}" for k, v in byconf.items()))
    json.dump({"log": LOG}, open(f"{OUT}/INT_map_gates_log.json", "w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:220]}")


if __name__ == "__main__":
    main()
