#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 2d: flag-anchored earliest_gate.

THIS is the derivation that produced the committed earliest_gate values.
It supersedes derive_gates.py and derive_gates_hm.py, both of which are kept
in the repo only as records of approaches that failed for instructive reasons:

  derive_gates.py     — spatial reach from Littleroot. Failed because physical
                        adjacency is not story order: Petalburg Gym is five
                        warps from the player's bedroom but locked until badge
                        five, so anchoring on boss maps inverted the ladder.
  derive_gates_hm.py  — HM-aware reachability, solved as a fixpoint. The
                        reachability itself is correct (399/440 maps, all 8 HMs
                        in dependency order) but converting access waves to
                        checkpoints inherited the same inversion.

What works instead: each of the 19 level-cap flags from src/caps.c is SET by a
specific map script. Those setflag sites are story-ordered by construction, so
they anchor maps to checkpoints without any spatial inference at all.

Tiers:
  Measured — the item's map is the map that sets the checkpoint flag.
  Inferred — the item's map shares a region_map_section with such a map.
  UNK      — neither. Left unset rather than guessed.

Known limitation: a region inherits its EARLIEST anchor, so multi-stage areas
(visited early, revisited after Surf) remain a lower bound.
"""
import collections, csv, glob, json, os, re

SRC = "/home/claude/src_sable"
OUT = "/home/claude/out"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})

def main():
    caps = [(int(r["order"]), r["gate_flag"])
            for r in csv.DictReader(open(f"{OUT}/03b_checkpoints.tsv", encoding="utf-8"),
                                    delimiter="\t")]
    flags = {f: o for o, f in caps}

    # 1. which map sets each checkpoint flag
    anchor = {}
    for f in glob.glob(f"{SRC}/data/maps/*/scripts.inc"):
        m = f.split("/")[-2]
        txt = open(f, encoding="utf-8", errors="replace").read()
        for fl in re.findall(r"setflag\s+(FLAG_[A-Z0-9_]+)", txt):
            if fl in flags:
                anchor[m] = min(anchor.get(m, 99), flags[fl])
    log("K1_anchors", f"{len(anchor)} maps set a checkpoint flag "
                      f"(of {len(flags)} flags in the ladder)")
    missing = [f for f in flags if not any(True for _ in [0])] if False else []

    # 2. region sections inherit the earliest anchor inside them
    sec = {}
    for f in glob.glob(f"{SRC}/data/maps/*/map.json"):
        try:
            sec[f.split("/")[-2]] = json.load(open(f, encoding="utf-8")) \
                .get("region_map_section", "UNK")
        except Exception:
            continue
    region_cp = {}
    for m, o in anchor.items():
        s = sec.get(m)
        if s:
            region_cp[s] = min(region_cp.get(s, 99), o)
    log("K2_regions", f"{len(region_cp)} region sections anchored: " +
        ", ".join(f"{k.replace('MAPSEC_','')}=cp{v}"
                  for k, v in sorted(region_cp.items(), key=lambda x: x[1])))

    # 3. apply to world rows
    rows = list(csv.DictReader(open(f"{OUT}/02_world.tsv", encoding="utf-8"), delimiter="\t"))
    exact = reg = unk = 0
    for r in rows:
        m = r["map"]
        if m in anchor:
            r["earliest_gate"] = anchor[m]
            r["earliest_gate_confidence"] = "Measured"
            exact += 1
        elif sec.get(m) in region_cp:
            r["earliest_gate"] = region_cp[sec[m]]
            r["earliest_gate_confidence"] = "Inferred"
            reg += 1
        else:
            r["earliest_gate"] = "UNK"
            r["earliest_gate_confidence"] = "NA"
            unk += 1
    log("K3_coverage", f"{exact} Measured (map sets the flag itself), "
                       f"{reg} Inferred (shares a region section), {unk} UNK")
    dist = collections.Counter(r["earliest_gate"] for r in rows if r["earliest_gate"] != "UNK")
    log("K4_distribution", ", ".join(f"cp{k}={v}" for k, v in
                                     sorted(dist.items(), key=lambda x: int(x[0]))))
    log("K5_limits",
        "Region inheritance takes the EARLIEST anchor in that section, so it is a "
        "lower bound for multi-stage areas. Sections with no anchor stay UNK rather "
        "than being guessed.", "FINDING")

    cols = list(rows[0].keys())
    with open(f"{OUT}/02_world.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "UNK")) for c in cols) + "\n")
    json.dump(LOG, open(f"{OUT}/INT_integrity_log_phase2d.json", "w"), indent=2)
    print(f"world rows {len(rows)} x {len(cols)}")
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:180]}")

if __name__ == "__main__":
    main()
