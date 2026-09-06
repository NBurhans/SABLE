#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 2c: HM-aware earliest_gate.

Replaces the topological-reach approximation, which was a lower bound because it
ignored HM locks (it placed Meteor Falls TMs at checkpoint 1 when they need Surf).

Solved as a FIXPOINT rather than a single pass, because reachability and HM
acquisition unlock each other:

    reachable maps -> HMs found in them -> more reachable maps -> ...

Each iteration is a "wave". A map's wave is the first iteration in which it
becomes reachable from Littleroot. Waves are then mapped onto the 19-gate
checkpoint ladder using boss-anchored maps, so an item's gate is the checkpoint
of the wave it first becomes reachable in.

Gating signal comes from source, not from guesswork:
    MAP_TYPE_OCEAN_ROUTE (11 maps)  -> requires Surf
    MAP_TYPE_UNDERWATER  (14 maps)  -> requires Dive
    requires_flash flag  (3 maps)   -> requires Flash

This is still Inferred, not Measured: it models HM locks but not badge locks or
story flags, and warps inside a building are treated as free movement.
"""
import csv, glob, json, os, re, collections

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def norm(x): return re.sub(r"[^a-z0-9]", "", x.replace("MAP_", "").lower())

HM_FOR_TYPE = {"MAP_TYPE_OCEAN_ROUTE": "SURF", "MAP_TYPE_UNDERWATER": "DIVE"}

def main():
    g = collections.defaultdict(set)
    need = {}          # map -> HM required to enter
    for f in glob.glob(f"{SRC}/data/maps/*/map.json"):
        name = norm(f.split("/")[-2])
        try: d = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        req = HM_FOR_TYPE.get(d.get("map_type"))
        if d.get("requires_flash"): req = req or "FLASH"
        if req: need[name] = req
        for c in (d.get("connections") or []):
            t = norm(c.get("map", ""))
            if t: g[name].add(t); g[t].add(name)
        for w in (d.get("warp_events") or []):
            t = w.get("dest_map", "")
            if t and "NONE" not in t and "DYNAMIC" not in t:
                g[name].add(norm(t)); g[norm(t)].add(name)
    log("H1_graph", f"{len(g)} nodes; {len(need)} maps HM-locked "
                    f"({collections.Counter(need.values())})")

    # which HMs live in which map (from the Phase 2 placements)
    world = list(csv.DictReader(open(f"{OUT}/02_world.tsv", encoding="utf-8"), delimiter="\t"))
    hm_in = collections.defaultdict(set)
    for r in world:
        m = re.match(r"ITEM_HM_([A-Z]+)", r["item_const"])
        if m:
            hm_in[norm(r["map"])].add(m.group(1))
    log("H2_hm_placements", f"{sum(len(v) for v in hm_in.values())} HM placements across "
                            f"{len(hm_in)} maps: "
                            f"{sorted({h for v in hm_in.values() for h in v})}")

    start = norm("LittlerootTown")
    have, reached, wave_of = set(), {start}, {start: 0}
    have |= hm_in.get(start, set())
    wave = 0
    while True:
        wave += 1
        frontier = set()
        for m in list(reached):
            for n in g.get(m, ()):
                if n in reached: continue
                req = need.get(n)
                if req and req not in have: continue
                frontier.add(n)
        if not frontier:
            break
        for n in frontier:
            reached.add(n); wave_of[n] = wave
            have |= hm_in.get(n, set())
        if wave > 60:
            log("H3_wave_cap", "wave limit hit", "WARN"); break
    log("H4_fixpoint", f"{len(reached)} of {len(g)} maps reachable in {wave} waves; "
                       f"HMs acquired: {sorted(have)}")
    blocked = [m for m in g if m not in reached]
    log("H5_unreachable", f"{len(blocked)} maps never reached (secret bases, "
                          f"multiplayer, unused); sample {blocked[:5]}")

    # anchor waves to checkpoints using boss maps
    tr = list(csv.DictReader(open(f"{OUT}/03_trainers.tsv", encoding="utf-8"), delimiter="\t"))
    boss_cp = {}
    for r in tr:
        if r["role"] == "route" or r["checkpoint"] in ("DYNAMIC", "NA"): continue
        nm = re.sub(r"\d+$", "", r["trainer_base"]).split()[-1].lower()
        boss_cp[nm] = min(boss_cp.get(nm, 99), int(r["checkpoint"]))
    anchors = {}
    for f in glob.glob(f"{SRC}/data/maps/*/scripts.inc"):
        m = norm(f.split("/")[-2])
        txt = open(f, encoding="utf-8", errors="replace").read()
        cps = [boss_cp[c] for c in
               {re.sub(r"_\d+$", "", t).replace("_", "").lower()
                for t in re.findall(r"TRAINER_([A-Z0-9_]+)", txt)} if c in boss_cp]
        if cps and m in wave_of:
            anchors.setdefault(wave_of[m], []).append(min(cps))
    wave_cp = {w: min(v) for w, v in anchors.items()}
    log("H6_wave_anchors", f"{len(wave_cp)} waves anchored to checkpoints: "
                           + ", ".join(f"w{w}->cp{c}" for w, c in sorted(wave_cp.items())))

    # monotone fill: a wave inherits the checkpoint of the nearest anchored wave <= it
    known = sorted(wave_cp)
    def cp_for(w):
        prev = [x for x in known if x <= w]
        if prev: return wave_cp[prev[-1]]
        return wave_cp[known[0]] if known else None

    hit = miss = 0
    for r in world:
        w = wave_of.get(norm(r["map"]))
        cp = cp_for(w) if w is not None else None
        if cp:
            r["earliest_gate"] = cp
            r["earliest_gate_confidence"] = "Inferred"
            r["access_wave"] = w
            hit += 1
        else:
            r["earliest_gate"] = "UNK"; r["earliest_gate_confidence"] = "NA"
            r["access_wave"] = "UNK"; miss += 1
    log("H7_coverage", f"{hit} world rows gated, {miss} UNK")
    dist = collections.Counter(r["earliest_gate"] for r in world if r["earliest_gate"] != "UNK")
    log("H8_distribution", ", ".join(f"cp{k}={v}" for k, v in
                                     sorted(dist.items(), key=lambda x: int(x[0]))))
    log("H9_limits",
        "Models HM locks (Surf/Dive/Flash) but NOT badge locks or story flags; "
        "building-internal warps are free movement. Still Inferred.", "FINDING")

    cols = list(world[0].keys())
    with open(f"{OUT}/02_world.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in world:
            f.write("\t".join(str(r.get(c, "UNK")) for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase2c.json", "w"), indent=2)
    print(f"world {len(world)} x {len(cols)}")
    for e in LOG: print(f"  [{e['severity']}] {e['check']}: {e['detail'][:175]}")

if __name__ == "__main__":
    main()
