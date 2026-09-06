#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 2b: earliest_gate derivation.

Phase 5 caps a build's ceiling at what is obtainable by a checkpoint, so every
item needs the checkpoint at which the player can first hold it. Source does not
encode that directly, so it is DERIVED here and tagged Inferred — never Measured.

Method:
  1. Build an undirected map graph from `connections` and `warp_events` in
     data/maps/*/map.json.
  2. Anchor maps that contain a boss battle: grep TRAINER_ constants out of each
     map's scripts.inc, match them to the boss->checkpoint assignment from
     Phase 3c, and stamp that map with the lowest checkpoint fought there.
  3. Propagate: every other map takes the lowest anchor checkpoint reachable
     within N hops. A map adjacent to the Rustboro gym inherits checkpoint 1.
  4. Items inherit their map's checkpoint. Mart stock inherits the mart's map.

Known limitation, recorded rather than hidden: this models topological reach,
NOT HM or badge gating. A water route adjacent to an early town is reachable in
the graph long before Surf exists, so derived gates are a LOWER BOUND — they can
be too early, never too late. That bias is the safe direction for a ceiling cap
(it never claims something is unavailable when it is available), but it must be
stated wherever these values are used.
"""
import csv, glob, json, os, re, collections

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def build_graph():
    g = collections.defaultdict(set)
    maps = set()
    for f in glob.glob(f"{SRC}/data/maps/*/map.json"):
        name = f.split("/")[-2]
        maps.add(name)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        def norm(mc):
            return mc.replace("MAP_", "").replace("_", "").lower()
        for c in (d.get("connections") or []):
            g[norm(name)].add(norm(c.get("map", "")))
            g[norm(c.get("map", ""))].add(norm(name))
        for w in (d.get("warp_events") or []):
            t = w.get("dest_map", "")
            if t and "NONE" not in t and "DYNAMIC" not in t:
                g[norm(name)].add(norm(t))
                g[norm(t)].add(norm(name))
    log("G1_graph", f"{len(maps)} maps, {sum(len(v) for v in g.values())//2} edges "
                    f"from connections and warps")
    return g, maps

def anchor_maps(bosses_by_name):
    """map -> lowest checkpoint of any boss fought there."""
    anchors = {}
    for f in glob.glob(f"{SRC}/data/maps/*/scripts.inc"):
        name = f.split("/")[-2]
        txt = open(f, encoding="utf-8", errors="replace").read()
        cps = []
        for tc in set(re.findall(r"TRAINER_([A-Z0-9_]+)", txt)):
            base = re.sub(r"_\d+$", "", tc).replace("_", "").lower()
            cp = bosses_by_name.get(base)
            if cp:
                cps.append(cp)
        if cps:
            anchors[name.replace("_", "").lower()] = min(cps)
    log("G2_anchors", f"{len(anchors)} maps anchored by a boss battle")
    return anchors

def main():
    tr = list(csv.DictReader(open(f"{OUT}/03_trainers.tsv", encoding="utf-8"), delimiter="\t"))
    bosses_by_name = {}
    for r in tr:
        if r["role"] == "route" or r["checkpoint"] in ("DYNAMIC", "NA"):
            continue
        # "Leader Roxanne2" -> roxanne
        nm = re.sub(r"\d+$", "", r["trainer_base"]).split()[-1].lower()
        cp = int(r["checkpoint"])
        bosses_by_name[nm] = min(bosses_by_name.get(nm, 99), cp)
    log("G0_boss_names", f"{len(bosses_by_name)} distinct boss names carry a checkpoint")

    g, maps = build_graph()
    anchors = anchor_maps(bosses_by_name)

    # multi-source BFS: every map takes the lowest checkpoint reachable
    gate = dict(anchors)
    frontier = collections.deque((m, c) for m, c in anchors.items())
    hops = {m: 0 for m in anchors}
    MAXHOP = 4
    while frontier:
        m, c = frontier.popleft()
        if hops[m] >= MAXHOP:
            continue
        for n in g.get(m, ()):
            if n not in gate or c < gate[n]:
                gate[n] = c
                hops[n] = hops[m] + 1
                frontier.append((n, c))
    log("G3_propagated", f"{len(gate)} maps have a derived checkpoint "
                         f"(within {MAXHOP} hops of an anchor)")

    rows = list(csv.DictReader(open(f"{OUT}/02_world.tsv", encoding="utf-8"), delimiter="\t"))
    hit = miss = 0
    for r in rows:
        key = r["map"].replace("_", "").lower()
        cp = gate.get(key)
        if cp:
            r["earliest_gate"] = cp
            r["earliest_gate_confidence"] = "Inferred"
            hit += 1
        else:
            r["earliest_gate"] = "UNK"
            r["earliest_gate_confidence"] = "NA"
            miss += 1
    log("G4_item_coverage", f"{hit} world rows received a derived earliest_gate, {miss} remain UNK")

    dist = collections.Counter(r["earliest_gate"] for r in rows if r["earliest_gate"] != "UNK")
    log("G5_gate_distribution",
        ", ".join(f"cp{k}={v}" for k, v in sorted(dist.items(), key=lambda x: int(x[0]))))
    tms = [r for r in rows if r["item_const"].startswith(("ITEM_TM", "ITEM_HM"))
           and r["earliest_gate"] != "UNK"]
    log("G6_tm_gates", f"{len(tms)} TM/HM placements now carry a gate")
    log("G7_lower_bound_warning",
        "Derived gates model topological reach, not HM or badge locks, so they are "
        "a LOWER BOUND: an item may be gated LATER than stated, never earlier. "
        "Tagged Inferred; must be stated wherever a ceiling uses them.", "FINDING")

    cols = list(rows[0].keys())
    with open(f"{OUT}/02_world.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "UNK")) for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase2b.json", "w"), indent=2)
    print(f"world rows {len(rows)} x {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:170]}")

if __name__ == "__main__":
    main()
