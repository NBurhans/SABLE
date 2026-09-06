#!/usr/bin/env node
/*
 * HALYARD / target SABLE — Phase 4a: custom data layer.
 *
 * Overwrites the gen-8 species and move tables in @smogon/calc with data parsed
 * from this hack's own source. The fork ships Radical Red's data layer; per the
 * source hierarchy that layer is NEVER used — the fork supplies mechanics only.
 *
 * Emits data_layer.json plus a coverage report. Anything present in the hack but
 * absent from the calc is added, never silently substituted with the vanilla or
 * Radical Red version.
 */
const fs = require('fs');
const OUT = '/home/claude/out';

function tsv(path) {
  const lines = fs.readFileSync(path, 'utf8').trim().split('\n');
  const cols = lines[0].split('\t');
  return lines.slice(1).map(l => {
    const v = l.split('\t'), o = {};
    cols.forEach((c, i) => o[c] = v[i]);
    return o;
  });
}

const TYPE = s => s.replace('TYPE_', '').toLowerCase()
  .replace(/^./, c => c.toUpperCase());

// calc keys species by display name; our source keys by constant + form
function speciesKey(r) {
  let n = r.species_name;
  if (r.form_type && r.form_type !== 'base' && r.form_markers !== 'NONE') {
    const c = r.species_const.replace(/^SPECIES_/, '').split('_').slice(1);
    if (c.length) n += '-' + c.map(x => x[0] + x.slice(1).toLowerCase()).join('-');
  }
  return n;
}

const species = tsv(`${OUT}/01_species.tsv`);
const moves = tsv(`${OUT}/01b_moves.tsv`);

const SP = {}, MV = {};
let skippedSp = 0;
for (const r of species) {
  const bs = ['base_hp','base_atk','base_def','base_spa','base_spd','base_spe']
    .map(k => parseInt(r[k], 10));
  if (bs.some(isNaN)) { skippedSp++; continue; }
  const types = [TYPE(r.type_1)];
  if (r.type_2 !== r.type_1 && r.type_2 !== 'UNK') types.push(TYPE(r.type_2));
  const ab = {};
  [r.ability_1, r.ability_2, r.ability_hidden].forEach((a, i) => {
    if (a && a !== 'NONE' && a !== 'UNK') {
      ab[i === 2 ? 'H' : String(i)] = a.replace('ABILITY_', '')
        .split('_').map(w => w[0] + w.slice(1).toLowerCase()).join(' ');
    }
  });
  SP[speciesKey(r)] = {
    types,
    bs: {hp: bs[0], at: bs[1], df: bs[2], sa: bs[3], sd: bs[4], sp: bs[5]},
    weightkg: 10,          // not in source; only affects weight-based moves
    abilities: ab,
    nfe: r.evolutions !== 'NONE' && r.evolutions !== 'UNK',
  };
}

let skippedMv = 0;
for (const r of moves) {
  if (r.move_const === 'MOVE_NONE') continue;
  const bp = parseInt(r.power, 10);
  if (isNaN(bp)) { skippedMv++; continue; }
  const cat = r.category === 'PHYSICAL' ? 'Physical'
            : r.category === 'SPECIAL' ? 'Special' : 'Status';
  const m = {bp, type: TYPE(r.type), category: cat};
  const f = r.flags || '';
  if (f.includes('makesContact')) m.makesContact = true;
  if (f.includes('punchingMove')) m.isPunch = true;
  if (f.includes('bitingMove')) m.isBite = true;
  if (f.includes('slicingMove')) m.isSlicing = true;
  if (f.includes('soundMove')) m.isSound = true;
  if (f.includes('ballisticMove')) m.isBullet = true;
  if (f.includes('windMove')) m.isWind = true;
  const pr = parseInt(r.priority, 10);
  if (pr) m.priority = pr;
  const cs = /criticalHitStage:(\d+)/.exec(f);
  if (cs) m.willCrit = false, m.critRatio = parseInt(cs[1], 10) + 1;
  const sc = /strikeCount:(\d+)/.exec(f);
  if (sc) m.multihit = parseInt(sc[1], 10);
  MV[r.move_name] = m;
}

// coverage against the stock tables
const {SPECIES} = require('/home/claude/rrcalc/calc/dist/data/species.js');
const {MOVES}  = require('/home/claude/rrcalc/calc/dist/data/moves.js');
const stockSp = new Set(Object.keys(SPECIES[8]));
const stockMv = new Set(Object.keys(MOVES[8]));
const newSp = Object.keys(SP).filter(k => !stockSp.has(k));
const newMv = Object.keys(MV).filter(k => !stockMv.has(k));
const K = ['hp','at','df','sa','sd','sp'];
const eq = (a,b) => K.every(k => a[k] === b[k]);
const changedSp = Object.keys(SP).filter(k => stockSp.has(k) && !eq(SPECIES[8][k].bs, SP[k].bs));
const changedTypes = Object.keys(SP).filter(k => stockSp.has(k) &&
  (SPECIES[8][k].types || []).join('/') !== SP[k].types.join('/'));
const changedMv = Object.keys(MV).filter(k => stockMv.has(k) &&
  (MOVES[8][k].bp !== MV[k].bp || MOVES[8][k].type !== MV[k].type));

fs.writeFileSync(`${OUT}/data_layer.json`,
  JSON.stringify({species: SP, moves: MV}, null, 0));

const report = {
  species_in_layer: Object.keys(SP).length,
  species_skipped: skippedSp,
  species_not_in_calc: newSp.length,
  species_with_changed_stats: changedSp.length,
  moves_in_layer: Object.keys(MV).length,
  moves_skipped: skippedMv,
  moves_not_in_calc: newMv.length,
  sample_new_species: newSp.slice(0, 8),
  sample_new_moves: newMv.slice(0, 8),
  species_with_changed_types: changedTypes.length,
  moves_with_changed_bp_or_type: changedMv.length,
  sample_changed_stats: changedSp.slice(0, 6),
  sample_changed_types: changedTypes.slice(0, 6),
  sample_changed_moves: changedMv.slice(0, 6),
};
fs.writeFileSync(`${OUT}/INT_data_layer_report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
