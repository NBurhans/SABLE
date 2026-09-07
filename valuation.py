#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 5b: VORP, tiers, invariants.

Replacement level (VISION 4.4): for a given (checkpoint, role), the performance
of the THIRD-BEST obtainable species-form for that role at that checkpoint under
ZERO investment. Zero investment is the Floor anchor, which is why Phase 5a
scores floors as well as ceilings.

    VORP = ceiling_fit - replacement_fit(checkpoint, role)

Published per (species-form, checkpoint, role). A single global ladder is a BST
ranking with extra steps (roles.md s7), so the ladder is published per role.

Tiers use numeric thresholds on VORP, stated below, and the resulting
distribution is REPORTED, not forced. Fourteen S-tiers is a finding.
"""
import csv, json, collections, statistics, math, itertools

OUT = "/home/claude/out"
WORK = "/home/claude/work"
LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})
def tsv(p): return list(csv.DictReader(open(f"{OUT}/{p}", encoding="utf-8"), delimiter="\t"))

TIERS = [("S+", 0.30), ("S", 0.22), ("A", 0.14), ("B", 0.07),
         ("C", 0.00), ("D", -0.10), ("F", -99)]

def corr(xs, ys):
    if len(xs) < 10: return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    n = sum((a-mx)*(b-my) for a, b in zip(xs, ys))
    d = math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
    return n/d if d else 0


def main():
    roles = tsv("05_roles.tsv")
    species = {s["species_const"]: s for s in tsv("01_species.tsv")}
    avail = {a["species_const"]: a for a in tsv("01c_availability.tsv")}
    world = tsv("02_world.tsv")

    scored = [r for r in roles if r["primary_role"] != "NONE"]
    floors = [r for r in scored if r["anchor"] == "floor"]
    ceils  = [r for r in scored if r["anchor"] == "candidate"]

    # ---- replacement level per (checkpoint, role), from FLOOR builds only
    fl = collections.defaultdict(list)
    for r in floors:
        fl[(r["checkpoint"], r["primary_role"])].append(
            (float(r["primary_fit"]), r["species_const"]))
    replacement, thin = {}, []
    for k, lst in fl.items():
        lst.sort(key=lambda p: -p[0])
        if len(lst) >= 3:
            replacement[k] = lst[2][0]
        else:
            # fewer than three obtainable floors in this role: the replacement
            # construction is undefined, so use the worst available and flag it
            replacement[k] = lst[-1][0]
            thin.append((k, len(lst)))
    log("V0_replacement",
        f"replacement level set for {len(replacement)} (checkpoint, role) cells")
    log("V1_thin_roles",
        f"{len(thin)} cells had fewer than three obtainable floor builds, so the "
        f"third-best construction is undefined and the worst available was used; "
        f"sample {thin[:6]}", "WARN" if thin else "INFO")

    # ---- best ceiling per (species, checkpoint), and VORP
    # builds.md s4.3 already says headline builds use RELIABLY obtainable items
    # only, with one-of-a-kind items generating a separate flagged build and the
    # gap published as item dependence. The role layer was picking the best fit
    # outright, which is why Life Orb — scarce, and a flat +30% damage — took
    # 55% of published ceilings. Enforcing the existing rule is not padding the
    # distribution; ignoring it was the defect.
    best, best_any, dep_n = {}, {}, 0
    for r in ceils:
        k = (r["species_const"], r["checkpoint"])
        fit = float(r["primary_fit"])
        if k not in best_any or fit > float(best_any[k]["primary_fit"]):
            best_any[k] = r
        if r["item_reliable"] != "TRUE" and r["item"] != "NONE":
            continue
        if k not in best or fit > float(best[k]["primary_fit"]):
            best[k] = r
    for k, r in best_any.items():
        if k not in best:
            best[k] = r            # nothing reliable available: fall back, flagged
    log("V0a_scarcity_gate",
        f"{sum(1 for k in best_any if best[k] is not best_any[k])} ceilings were "
        f"demoted to a reliably-obtainable item; "
        f"{sum(1 for k in best_any if k not in {kk for kk,v in best.items() if v.get('item_reliable')=='TRUE' or v['item']=='NONE'})} "
        f"had no reliable option and kept a scarce item, flagged")
    fmap = {(r["species_const"], r["checkpoint"]): r for r in floors}

    out = []
    for (sc, cp), r in best.items():
        role = r["primary_role"]
        rep = replacement.get((cp, role), 0.0)
        ceil_fit = float(r["primary_fit"])
        f = fmap.get((sc, cp))
        floor_fit = float(f["primary_fit"]) if f else 0.0
        vorp = ceil_fit - rep
        tier = next(t for t, th in TIERS if vorp >= th)
        a = avail.get(sc, {})
        s = species[sc]
        out.append({
            "species_const": sc, "species_name": r["species_name"], "checkpoint": int(cp),
            "primary_role": role, "hybrid_role": r["hybrid_role"], "top3": r["top3"],
            "ceiling_fit": round(ceil_fit, 4), "floor_fit": round(floor_fit, 4),
            "replacement_fit": round(rep, 4), "vorp": round(vorp, 4), "tier": tier,
            "investment_delta": round(ceil_fit - floor_fit, 4),
            "S": r["S"], "T": r["T"], "Y": r["Y"], "F": r["F"],
            "track": r["track"], "ability": r["ability"], "nature": r["nature"],
            "item": r["item"], "item_reliable": r["item_reliable"], "moves": r["moves"],
            "bst": s["bst"], "earliest_cp": a.get("earliest_cp", "UNK"),
            "availability_confidence": a.get("availability_confidence", "UNK"),
            "entry_reason": a.get("entry_reason", "UNK"),
            "matrix_score": r["matrix_score"], "confidence": "Derived",
            "item_dependence": round(
                float(best_any[(sc, cp)]["primary_fit"]) - ceil_fit, 4),
            "unreliable_best_item": best_any[(sc, cp)]["item"]
                if best_any[(sc, cp)]["item"] != r["item"] else "NA",
        })

    # ---- cant_miss: high value AND one-time or missable availability.
    # The rule is written down rather than vibed: VORP in the top decile for its
    # role at the checkpoint it becomes available, AND an entry path that is a
    # one-time gift/trade/static rather than a repeatable wild encounter.
    byrole = collections.defaultdict(list)
    for r in out: byrole[(r["checkpoint"], r["primary_role"])].append(r["vorp"])
    cut = {k: (statistics.quantiles(v, n=10)[8] if len(v) >= 10 else max(v))
           for k, v in byrole.items()}
    n_cm = 0
    for r in out:
        top = r["vorp"] >= cut[(r["checkpoint"], r["primary_role"])]
        one_time = "wild" not in r["entry_reason"] and r["entry_reason"] != "starter:game_start"
        r["cant_miss"] = "TRUE" if (top and one_time) else "FALSE"
        n_cm += r["cant_miss"] == "TRUE"
    log("V2_cant_miss",
        f"{n_cm} (species, checkpoint) rows flagged cant_miss: top-decile VORP for "
        f"their role AND a non-repeatable entry path")

    dist = collections.Counter(r["tier"] for r in out)
    log("V3_tier_distribution",
        " ".join(f"{t}:{dist[t]}({dist[t]/len(out):.1%})" for t, _ in TIERS)
        + " — thresholds numeric on VORP, curve NOT forced")

    # ================= invariants =================
    inv, tot = {}, len(out)
    ic = collections.Counter(r["item"] for r in out)
    top_i, top_iv = ic.most_common(1)[0]
    inv["I1"] = {"metric": "max item share", "value": round(top_iv/tot, 4),
                 "threshold": 0.25, "pass": top_iv/tot <= 0.25, "worst": top_i}
    nc = collections.Counter(r["nature"] for r in out)
    top_n, top_nv = nc.most_common(1)[0]
    inv["I2"] = {"metric": "max nature share", "value": round(top_nv/tot, 4),
                 "threshold": 0.20, "pass": top_nv/tot <= 0.20, "worst": top_n}

    # I3 on the PUBLISHED value (VORP), within each (checkpoint, role)
    rr = []
    for k, grp in itertools.groupby(sorted(out, key=lambda r: (r["checkpoint"], r["primary_role"])),
                                      key=lambda r: (r["checkpoint"], r["primary_role"])):
        g = list(grp)
        c = corr([x["vorp"] for x in g], [int(x["bst"]) for x in g])
        if c is not None: rr.append((k, c, len(g)))
    fails = [x for x in rr if abs(x[1]) > 0.60]
    mean_r = statistics.mean(abs(x[1]) for x in rr) if rr else 0
    inv["I3"] = {"metric": "mean |r| VORP vs BST within (checkpoint, role)",
                 "value": round(mean_r, 4), "threshold": 0.60,
                 "pass": mean_r <= 0.60, "n_cells": len(rr), "cells_failing": len(fails),
                 "worst": sorted(rr, key=lambda x: -abs(x[1]))[:5]}

    # I4: every role at every checkpoint has >=3 species-forms within 10% of leader
    i4fail = []
    for k, grp in itertools.groupby(sorted(out, key=lambda r: (r["checkpoint"], r["primary_role"])),
                                      key=lambda r: (r["checkpoint"], r["primary_role"])):
        g = sorted(grp, key=lambda r: -r["ceiling_fit"])
        lead = g[0]["ceiling_fit"]
        near = sum(1 for x in g if x["ceiling_fit"] >= lead*0.90)
        if near < 3: i4fail.append((k, near, len(g)))
    inv["I4"] = {"metric": "(checkpoint, role) cells with <3 forms within 10% of leader",
                 "value": len(i4fail), "threshold": 0,
                 "pass": not i4fail, "sample": i4fail[:8]}

    # I5: recommended teams simultaneously equippable given copy counts
    qty, mart = collections.defaultdict(int), set()
    for w in world:
        if w["entity_type"] == "mart_stock": mart.add(w["item_const"])
        else:
            try: qty[w["item_const"]] += int(w["quantity"])
            except ValueError: qty[w["item_const"]] += 1
    i5fail = []
    for cp in sorted({r["checkpoint"] for r in out}):
        g = sorted([r for r in out if r["checkpoint"] == cp],
                   key=lambda r: -r["vorp"])[:6]
        used = collections.Counter(r["item"] for r in g if r["item"] != "NONE")
        for it, n in used.items():
            if it in mart: continue
            if qty.get(it, 0) < n:
                i5fail.append((cp, it, n, qty.get(it, 0)))
    inv["I5"] = {"metric": "top-6 teams needing more copies than exist",
                 "value": len(i5fail), "threshold": 0, "pass": not i5fail,
                 "sample": i5fail[:8]}

    # I7: no move in >30% of recommended movesets, obligatory STAB excluded
    mc, stabc = collections.Counter(), collections.Counter()
    for r in out:
        s = species[r["species_const"]]
        t = {s["type_1"].replace("TYPE_","").capitalize(),
             s["type_2"].replace("TYPE_","").capitalize()}
        for m in r["moves"].split(","):
            mc[m] += 1
    top_m, top_mv = mc.most_common(1)[0]
    inv["I7"] = {"metric": "max move share of movesets", "value": round(top_mv/tot, 4),
                 "threshold": 0.30, "pass": top_mv/tot <= 0.30, "worst": top_m,
                 "top5": mc.most_common(5)}

    for k, v in inv.items():
        log(f"INV_{k}", f"{'PASS' if v['pass'] else 'FAIL'} — {v['metric']} = "
                        f"{v['value']} (threshold {v['threshold']})"
                        + (f", worst {v.get('worst')}" if v.get("worst") else ""),
            "INFO" if v["pass"] else "WARN")

    cols = [c for c in out[0].keys()]
    with open(f"{OUT}/05_valuation.tsv","w",encoding="utf-8") as f:
        f.write("\t".join(cols)+"\n")
        for r in sorted(out, key=lambda r: (r["checkpoint"], r["primary_role"], -r["vorp"])):
            f.write("\t".join(str(r[c]) for c in cols)+"\n")
    json.dump({"log": LOG, "invariants": inv},
              open(f"{OUT}/INT_invariants_phase5.json","w"), indent=2, default=str)
    print(f"rows {len(out)}")
    for e in LOG: print(f"  [{e['severity']}] {e['check']}: {e['detail'][:230]}")

if __name__ == "__main__":
    main()
