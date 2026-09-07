#!/usr/bin/env python3
"""
HALYARD / target SABLE — Phase 6b: invariant I6.

I6 is the direct test of "base stats determine the build". Perturb base stats by
+/-15 and re-run build generation on a stratified sample; require the recommended
build to change for >= 20% of the sample. If stat spreads can be scrambled
without changing recommendations, the build generator is not reading them.

Sampling is stratified across BST quartiles and evolution stages, and the seed is
recorded so the run reproduces. This is the only invariant that requires
re-running the pipeline, so it is sampled and run once rather than on every
export.

Method: for each sampled species-form, generate its builds at three checkpoints
under (a) true stats and (b) perturbed stats, and compare the resulting build
SET — orientation track, natures, item classes and movesets. A change in any of
those is a changed recommendation.
"""
import csv, json, random, collections, statistics, sys, copy, re, os

OUT = "/home/claude/out"
WORK = "/home/claude/work"
sys.path.insert(0, WORK)

SEED = 20260907
SAMPLE = 150
CHECKPOINTS = [3, 10, 19]
DELTA = 15

LOG = []
def log(c, d, s="INFO"): LOG.append({"check": c, "severity": s, "detail": d})


def stratified_sample(species, avail):
    pool = [s for s in species
            if avail.get(s["species_const"], {}).get("in_pool") == "TRUE"
            and s["bst"].isdigit()]
    bsts = sorted(int(s["bst"]) for s in pool)
    q = [bsts[len(bsts)*i//4] for i in range(1, 4)]
    def quart(s):
        b = int(s["bst"])
        return 0 if b < q[0] else 1 if b < q[1] else 2 if b < q[2] else 3
    def stage(s):
        has_evo = s["evolutions"] not in ("NONE", "UNK", "")
        evolves_from = s.get("species_const") and False
        return "unevolved" if has_evo else "final"
    strata = collections.defaultdict(list)
    for s in pool:
        strata[(quart(s), stage(s))].append(s)
    rng = random.Random(SEED)
    per = max(1, SAMPLE // len(strata))
    sample = []
    for k in sorted(strata):
        grp = sorted(strata[k], key=lambda s: s["species_const"])
        sample += rng.sample(grp, min(per, len(grp)))
    # top up to SAMPLE deterministically
    rest = sorted([s for s in pool if s not in sample], key=lambda s: s["species_const"])
    while len(sample) < SAMPLE and rest:
        sample.append(rest.pop(rng.randrange(len(rest))))
    log("I6_strata", f"{len(strata)} strata across BST quartiles x evolution stage; "
                     f"{per} per stratum, sample {len(sample)}, seed {SEED}")
    return sample[:SAMPLE]


def main():
    import generate_builds2 as G

    species = G.tsv("01_species.tsv")
    avail = {a["species_const"]: a for a in G.tsv("01c_availability.tsv")}
    sample = stratified_sample(species, avail)
    names = {s["species_const"] for s in sample}
    json.dump({"seed": SEED, "sample": sorted(names), "delta": DELTA,
               "checkpoints": CHECKPOINTS},
              open(f"{OUT}/INT_i6_sample.json", "w"), indent=1)

    rng = random.Random(SEED)
    perturb = {}
    for s in sample:
        perturb[s["species_const"]] = {
            k: rng.choice([-DELTA, DELTA]) for k in
            ("base_hp","base_atk","base_def","base_spa","base_spd","base_spe")}

    def run(perturbed):
        """Generate builds for the sample, optionally with perturbed stats."""
        rows = []
        src = f"{OUT}/01_species.tsv"
        tmp = f"{WORK}/_i6_species_{'pert' if perturbed else 'base'}.tsv"
        with open(src, encoding="utf-8") as f:
            hdr = f.readline().rstrip("\n").split("\t")
            lines = [hdr]
            for line in f:
                v = line.rstrip("\n").split("\t")
                r = dict(zip(hdr, v))
                if perturbed and r["species_const"] in perturb:
                    d = perturb[r["species_const"]]
                    tot = 0
                    for k, dv in d.items():
                        try: base = int(r[k])
                        except ValueError: continue
                        nv = max(1, min(255, base + dv))
                        r[k] = str(nv); tot += nv
                    r["bst"] = str(tot)
                lines.append([r[c] for c in hdr])
        with open(tmp, "w", encoding="utf-8") as f:
            for l in lines: f.write("\t".join(l) + "\n")
        return tmp

    base_file = run(False)
    pert_file = run(True)

    def gen(path, cps):
        """Run the real generator against a species file and collect the
        candidate builds for the sampled species only."""
        import shutil
        real = f"{OUT}/01_species.tsv"
        bak = f"{WORK}/_i6_real_species.tsv"
        shutil.copy(real, bak)
        shutil.copy(path, real)
        try:
            G.LOG.clear()
            G.main(cps)
            out = collections.defaultdict(set)
            for r in G.tsv("04a_candidates.tsv"):
                if r["species_const"] in names and r["anchor"] == "candidate":
                    out[(r["species_const"], r["checkpoint"])].add(
                        (r["track"], r["nature"], r["item"], r["moves"]))
            return out
        finally:
            shutil.copy(bak, real)

    a = gen(base_file, CHECKPOINTS)
    b = gen(pert_file, CHECKPOINTS)

    keys = set(a) | set(b)
    changed, same, detail = 0, 0, []
    per_species = collections.defaultdict(bool)
    for k in sorted(keys):
        if a.get(k, set()) != b.get(k, set()):
            changed += 1
            per_species[k[0]] = True
            if len(detail) < 12:
                detail.append({"species": k[0], "checkpoint": k[1],
                               "n_base": len(a.get(k, set())),
                               "n_perturbed": len(b.get(k, set()))})
        else:
            same += 1
            per_species.setdefault(k[0], False)

    sp_changed = sum(1 for v in per_species.values() if v)
    sp_total = len(per_species)
    rate_cells = changed / max(1, changed + same)
    rate_species = sp_changed / max(1, sp_total)

    log("I6_cells", f"{changed + same} (species, checkpoint) cells compared; "
                    f"{changed} changed ({rate_cells:.1%})")
    log("I6_species", f"{sp_changed} of {sp_total} sampled species-forms changed "
                      f"their recommended build set ({rate_species:.1%})")
    log("I6_result",
        f"{'PASS' if rate_species >= 0.20 else 'FAIL'} — threshold >= 20% of the "
        f"sample must change; observed {rate_species:.1%}",
        "INFO" if rate_species >= 0.20 else "WARN")

    json.dump({"seed": SEED, "delta": DELTA, "checkpoints": CHECKPOINTS,
               "sample_size": sp_total, "species_changed": sp_changed,
               "rate_species": round(rate_species, 4),
               "cells_compared": changed + same, "cells_changed": changed,
               "rate_cells": round(rate_cells, 4),
               "pass": rate_species >= 0.20, "sample_detail": detail,
               "log": LOG},
              open(f"{OUT}/INT_i6_result.json", "w"), indent=2)
    for e in LOG:
        print(f"  [{e['severity']}] {e['check']}: {e['detail'][:220]}")


if __name__ == "__main__":
    main()
