#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 7a: build the app's embedded payload.

The app is a single self-contained HTML file that opens offline, so the data
ships inside it. Everything is interned into string tables and emitted as arrays
rather than objects — an object-per-row payload of 19,215 valuation rows runs to
several megabytes of repeated key names for no benefit.

SCOPE DECISION — availability filtering RESTORED.

The creator's published walkthrough supplied the progression ordering the source
tree does not encode, so all 127 encounter maps now carry a gate and every
ladder row has a timing. 120 of those 127 gates are Asserted — read off a
secondary source — so the confidence rides alongside the number everywhere it
is shown, rather than the number being presented bare.

Original note, kept for the record:
There are two different columns in this dataset that both get called
"checkpoint", and only one of them is trustworthy:

  earliest_cp   WHEN the player can obtain the form.   61.8% UNK.  NOT SHIPPED.
  checkpoint    WHICH boss roster the build was scored
                against.  0 UNK, derived from 521 parsed
                boss slots.                             SHIPPED.

The app therefore offers no "available by gym N" filter and no availability
column, because that data would quietly mislead. It does keep per-boss-fight
views, which rest on measured trainer rosters.
"""
import csv, json, collections, gzip, os

OUT = "/home/claude/out"
WORK = "/home/claude/work"

def tsv(p):
    op = gzip.open if p.endswith(".gz") else open
    with op(f"{OUT}/{p}", "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))

class Intern:
    def __init__(self): self.d, self.l = {}, []
    def __call__(self, s):
        if s not in self.d:
            self.d[s] = len(self.l); self.l.append(s)
        return self.d[s]

def main():
    species = tsv("01_species.tsv")
    val = tsv("05_valuation.tsv")
    caps = {int(r["order"]): int(r["level_cap"]) for r in tsv("03b_checkpoints.tsv")}
    cpmeta = {int(r["order"]): r for r in tsv("03b_checkpoints.tsv")}
    trainers = tsv("03_trainers.tsv")
    names = json.load(open(f"{WORK}/species_names.json"))

    S = Intern()   # strings: moves, items, roles, abilities, natures, maps
    TY = lambda s: s.replace("TYPE_", "").capitalize() if s not in ("NONE","UNK") else None

    # ---------- species master
    sp_idx, sp_rows = {}, []
    for s in species:
        c = s["species_const"]
        sp_idx[c] = len(sp_rows)
        sp_rows.append([
            names.get(c, s["species_name"]),
            S(TY(s["type_1"]) or "None"),
            S(TY(s["type_2"]) or "None") if TY(s["type_2"]) else -1,
            int(s["base_hp"]), int(s["base_atk"]), int(s["base_def"]),
            int(s["base_spa"]), int(s["base_spd"]), int(s["base_spe"]),
            int(s["bst"]),
            S(s["ability_1"].replace("ABILITY_","").replace("_"," ").title()),
            S(s["ability_2"].replace("ABILITY_","").replace("_"," ").title())
                if s["ability_2"] not in ("NONE","UNK","") else -1,
            S(s["ability_hidden"].replace("ABILITY_","").replace("_"," ").title())
                if s["ability_hidden"] not in ("NONE","UNK","") else -1,
            s["evolutions"] if s["evolutions"] not in ("NONE","UNK","") else "",
        ])

    # ---------- valuation, one row per (species, boss fight)
    v_rows = []
    for r in val:
        si = sp_idx.get(r["species_const"])
        if si is None: continue
        v_rows.append([
            si, int(r["checkpoint"]),
            S(r["primary_role"]),
            S(r["hybrid_role"]) if r["hybrid_role"] != "NA" else -1,
            S(r["tier"]),
            None if r["vorp"] == "UNDEFINED" else round(float(r["vorp"]), 3),
            round(float(r["ceiling_fit"]), 3), round(float(r["floor_fit"]), 3),
            S(r["track"]), S(r["ability"].replace("ABILITY_","").replace("_"," ").title()),
            S(r["nature"]),
            S(r["item"].replace("ITEM_","").replace("_"," ").title()),
            [S(m) for m in r["moves"].split(",") if m],
            1 if r["item_reliable"] == "TRUE" else 0,
            1 if r.get("cant_miss") == "TRUE" else 0,
            round(float(r["S"]), 2) if r["S"] != "NA" else None,
            round(float(r["T"]), 2) if r["T"] != "NA" else None,
            round(float(r["Y"]), 2) if r["Y"] != "NA" else None,
            round(float(r["F"]), 2) if r["F"] != "NA" else None,
            r["earliest_cp"] if r["earliest_cp"] != "UNK" else None,
            S(r["availability_confidence"]),
        ])

    # ---------- boss fights, from measured trainer rosters
    resolved = json.load(open(f"{WORK}/boss_resolved.json"))
    fights = collections.defaultdict(list)
    for t in trainers:
        if t["role"] == "route" or t["checkpoint"] == "DYNAMIC": continue
        cp = int(t["checkpoint"])
        roster = []
        for slot in t["roster"].split("|"):
            p = slot.split(":")
            if len(p) < 5: continue
            roster.append([S(resolved.get(p[0], p[0])), int(p[1]) if p[1].isdigit() else 0,
                           S(p[2]) if p[2] else -1, S(p[3]) if p[3] else -1])
        if roster:
            fights[cp].append([S(t["trainer_label"]), S(t["role"]), roster])
    fight_rows = [[cp, caps.get(cp, 0), fights[cp]] for cp in sorted(fights)]

    # ---------- routes: which map holds which encounters (read-only listing)
    routes = collections.defaultdict(list)
    for s in species:
        if s["wild_availability"] in ("NONE","UNK",""): continue
        si = sp_idx[s["species_const"]]
        for rec in s["wild_availability"].split("|"):
            p = rec.split(":")
            if len(p) < 2: continue
            mp = p[0].replace("MAP_","").replace("_"," ").title()
            method = p[1] if len(p) > 1 else "?"
            lv = p[2] if len(p) > 2 else ""
            rate = p[3] if len(p) > 3 else ""
            routes[mp].append([si, S(method), lv, rate])
    route_rows = [[m, sorted(v)] for m, v in sorted(routes.items())]

    payload = {
        "strings": S.l,
        "species": sp_rows,
        "valuation": v_rows,
        "fights": fight_rows,
        "routes": route_rows,
        "meta": {
            "cells": 4248276,
            "builds_enumerated": 2414290,
            "candidates": 152865,
            "mechanics_gen": 8,
            "invariants": {"I1": [0.277, 0.25, False], "I2": [0.281, 0.20, False],
                           "I3": [0.502, 0.60, True], "I4": [117, 0, False],
                           "I5": [1, 0, False], "I6": [0.856, 0.20, True],
                           "I7": [0.129, 0.30, True]},
            "tier_thresholds": [["S+",0.30],["S",0.22],["A",0.14],["B",0.07],
                                ["C",0.00],["D",-0.10],["F",-99]],
            "calc_discrepancy": 0.003,
            "excluded": "153 level-scaled rival slots",
            "availability_note": "All 127 encounter maps are gated. 120 gates come "
                "from the creator's walkthrough (Asserted); 7 from item placements "
                "in source (Derived). Confidence is shown wherever timing is.",
        },
    }
    js = json.dumps(payload, separators=(",", ":"))
    open(f"{WORK}/payload.json", "w").write(js)
    print(f"strings   {len(S.l):,}")
    print(f"species   {len(sp_rows):,}")
    print(f"valuation {len(v_rows):,}")
    print(f"fights    {sum(len(f[2]) for f in fight_rows):,} across {len(fight_rows)} checkpoints")
    print(f"routes    {len(route_rows):,} maps, {sum(len(r[1]) for r in route_rows):,} encounter records")
    print(f"payload   {len(js)/1e6:.2f} MB raw")

if __name__ == "__main__":
    main()
