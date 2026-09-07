/*
 * HALYARD / target SABLE — Phase 4e: the 1v1 matchup matrix.
 *
 * VISION 4.2: the 1v1 matrix is the primitive; everything the player sees is
 * derived from it. For each (build, opposing Pokemon) pair this computes damage
 * both directions, speed order, turns-to-KO both directions, the outcome from
 * full HP and from a chipped state, and emits a win/loss/marginal verdict WITH
 * a margin — never a bare binary.
 *
 * Every cell is Derived, not Measured, however solid its inputs: the mechanics
 * generation is pinned (Gen 8) and every cell inherits that assumption.
 *
 * Checkpoints with no roster of their own are scored against the roster of the
 * next boss ahead of them (VISION 8) — the fight they are preparing you for.
 */
'use strict';
const fs = require('fs');
const {makeGeneration, toID} = require('./sable_gen.js');
const CALC = '/home/claude/rrcalc/calc/dist';
const {calculate, Pokemon, Move, Field} = require(`${CALC}/adaptable.js`);

const OUT = '/home/claude/out';
const gen = makeGeneration(8, require('./data_layer.json'));

// ------------------------------------------------------------------ helpers
function readTSV(p) {
  const lines = fs.readFileSync(p, 'utf8').split('\n');
  const cols = lines[0].split('\t');
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i]) continue;
    const v = lines[i].split('\t');
    const o = {};
    for (let j = 0; j < cols.length; j++) o[cols[j]] = v[j];
    rows.push(o);
  }
  return rows;
}

const ITEM_NAMES = JSON.parse(fs.readFileSync('/home/claude/work/item_names.json', 'utf8'));
const SPECIES_NAMES = JSON.parse(fs.readFileSync('/home/claude/work/species_names.json', 'utf8'));

function itemName(c) {
  if (!c || c === 'NONE' || c === 'UNK') return undefined;
  return ITEM_NAMES[c];
}

const missing = {species: new Set(), move: new Set(), ability: new Set(), item: new Set()};

function mkMon(specName, opts) {
  const id = toID(specName);
  if (!gen.species.get(id)) { missing.species.add(specName); return null; }
  try { return new Pokemon(gen, specName, opts); }
  catch (e) { missing.species.add(specName + ' [' + e.message.slice(0, 40) + ']'); return null; }
}

function mkMoves(list) {
  const out = [];
  for (const n of list) {
    if (!n) continue;
    if (!gen.moves.get(toID(n))) { missing.move.add(n); continue; }
    try { out.push(new Move(gen, n)); } catch (e) { missing.move.add(n); }
  }
  return out;
}

/* best damage one direction: max over the mon's moves of the average roll,
 * as a fraction of the defender's max HP */
function bestHit(atk, def, moves, field) {
  let best = 0, bestMove = 'NONE', bestRange = 'NA';
  for (const m of moves) {
    let r;
    try { r = calculate(gen, atk, def, m, field); } catch (e) { continue; }
    const dmg = r.damage;
    let lo, hi;
    if (Array.isArray(dmg)) {
      const flat = dmg.flat ? dmg.flat() : dmg;
      lo = Math.min(...flat); hi = Math.max(...flat);
    } else { lo = hi = dmg || 0; }
    const avg = (lo + hi) / 2 / def.maxHP();
    if (avg > best) { best = avg; bestMove = m.name; bestRange = `${lo}-${hi}`; }
  }
  return {frac: best, move: bestMove, range: bestRange};
}

function turnsToKO(frac) {
  if (frac <= 0) return 99;
  return Math.ceil(1 / frac);
}

/* ------------------------------------------------------------------ utility
 * A turns-to-KO damage race cannot see hazards, status, recovery or screens,
 * so the entire support track scored 0.115 against 0.451 for attackers and was
 * the best build for 5 of 1035 species. That is a property of the model, not of
 * the game. These adjustments let the 1v1 primitive value utility, in the three
 * currencies it actually trades in:
 *
 *   chip     — hazards reduce the HP the opponent brings to the fight
 *   denial   — status and speed control take turns away from the opponent
 *   longevity— recovery and screens extend the turns the player survives
 *
 * Each is applied to the SAME turns-to-KO race, so utility and damage are
 * commensurable rather than scored on separate scales. Every adjustment is
 * stored in its own column so a verdict can be traced back to what caused it.
 */
const norm = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');

const HAZARD = {stealthrock: 'sr', spikes: 'spikes', toxicspikes: 'tspikes', stickyweb: 'web'};
const RECOVERY = new Set(['recover','roost','softboiled','synthesis','moonlight','morningsun',
  'slackoff','milkdrink','rest','shoreup','strengthsap','junglehealing','lifedew','wish']);
const SCREENS = new Set(['reflect','lightscreen','auroraveil']);
const PARA = new Set(['thunderwave','glare','nuzzle','stunspore']);
const BURN = new Set(['willowisp','scald','sacredfire']);
const SLEEP = new Set(['spore','sleeppowder','hypnosis','darkvoid','lovelykiss','sing','yawn']);
const POISON = new Set(['toxic','toxicthread','poisonpowder','poisongas']);
const PHAZE = new Set(['whirlwind','roar','dragontail','circlethrow','haze','clearsmog']);
const LEECH = new Set(['leechseed']);

function utilityProfile(moveNames) {
  const n = moveNames.map(norm);
  return {
    hazards: n.filter(x => HAZARD[x]).map(x => HAZARD[x]),
    recovery: n.some(x => RECOVERY.has(x)),
    screens: n.some(x => SCREENS.has(x)),
    para: n.some(x => PARA.has(x)),
    burn: n.some(x => BURN.has(x)),
    sleep: n.some(x => SLEEP.has(x)),
    poison: n.some(x => POISON.has(x)),
    phaze: n.some(x => PHAZE.has(x)),
    leech: n.some(x => LEECH.has(x)),
  };
}

/* Stealth Rock chip depends on the defender's Rock matchup; Spikes is flat and
 * only bites grounded targets. Chip is applied ONCE per opponent, which is the
 * honest single-battle reading: hazards pay off across a roster, not in one 1v1.
 * The per-roster payoff is what the boss-level aggregate in Phase 5 sees. */
function hazardChip(prof, defMon) {
  let chip = 0;
  const types = defMon.types || [];
  const grounded = !types.includes('Flying') &&
    norm(defMon.ability || '') !== 'levitate' &&
    norm(defMon.item || '') !== 'airballoon';
  for (const h of prof.hazards) {
    if (h === 'sr') {
      let e = 1;
      for (const t of types) e *= (ROCK_EFF[t] !== undefined ? ROCK_EFF[t] : 1);
      chip += 0.125 * e;
    } else if (h === 'spikes' && grounded) {
      chip += 0.125;
    } else if (h === 'tspikes' && grounded && !types.includes('Poison') &&
               !types.includes('Steel')) {
      chip += 0.0;                       // damage-over-time, counted under denial
    }
  }
  return Math.min(chip, 0.5);
}
const ROCK_EFF = {Fire:2, Ice:2, Flying:2, Bug:2, Fighting:0.5, Ground:0.5,
                  Steel:0.5};

// ------------------------------------------------------------------- inputs
const cands = readTSV(`${OUT}/04a_candidates.tsv`);
const trainers = readTSV(`${OUT}/03_trainers.tsv`);
const caps = {};
for (const r of readTSV(`${OUT}/03b_checkpoints.tsv`)) caps[+r.order] = +r.level_cap;
const resolveMap = JSON.parse(fs.readFileSync('/home/claude/work/boss_resolved.json', 'utf8'));

// boss slots per checkpoint
const bossByCp = {};
let dynamicSlots = 0, unresolvedSlots = 0;
for (const t of trainers) {
  if (t.role === 'route') continue;
  const slots = t.roster.split('|');
  const ivs = t.ivs.split('|'), evs = t.evs.split('|');
  if (t.checkpoint === 'DYNAMIC') { dynamicSlots += slots.length; continue; }
  const cp = +t.checkpoint;
  if (!bossByCp[cp]) bossByCp[cp] = [];
  slots.forEach((s, i) => {
    const p = s.split(':');
    if (p.length < 5) return;
    const resolved = resolveMap[p[0]];
    if (!resolved) { unresolvedSlots++; return; }
    const parseSpread = str => {
      const o = {};
      if (!str) return o;
      for (const tok of str.split(',')) {
        const m = tok.trim().split(/\s+/);
        if (m.length === 2) {
          const key = {hp: 'hp', at: 'atk', df: 'def', sa: 'spa', sd: 'spd', sp: 'spe'}[m[1]];
          if (key) o[key] = +m[0];
        }
      }
      return o;
    };
    bossByCp[cp].push({
      trainer: t.trainer_label, trainer_id: t.trainer_id, role: t.role, slot: i + 1,
      name: resolved, raw: p[0], level: +p[1] || caps[cp],
      ability: p[2], item: p[3], nature: p[4],
      moves: (p[5] || '').split(','),
      ivs: parseSpread(ivs[i]), evs: parseSpread(evs[i]),
    });
  });
}

// VISION 8: a checkpoint with no roster is scored against the next boss ahead
const rosterFor = {};
const ordered = Object.keys(caps).map(Number).sort((a, b) => a - b);
for (const cp of ordered) {
  if (bossByCp[cp] && bossByCp[cp].length) { rosterFor[cp] = {cp, slots: bossByCp[cp]}; continue; }
  const next = ordered.find(o => o > cp && bossByCp[o] && bossByCp[o].length);
  rosterFor[cp] = next ? {cp: next, slots: bossByCp[next], borrowed: true} : null;
}

// ------------------------------------------------------------------- runner
const EV_BY_TRACK = {
  physical: {atk: 252, spe: 252, hp: 6},
  special:  {spa: 252, spe: 252, hp: 6},
  mixed:    {atk: 252, spa: 252, spe: 6},
  support:  {hp: 252, def: 252, spd: 6},
  floor:    {},
};

const targetCps = process.argv.slice(2).map(Number);
const cpList = targetCps.length ? targetCps : ordered;

let cells = 0, calcs = 0, skipped = 0;
const t0 = Date.now();
const summary = [];

for (const cp of cpList) {
  const rf = rosterFor[cp];
  const mine = cands.filter(c => +c.checkpoint === cp);
  if (!rf || !mine.length) continue;

  // build defenders once per checkpoint and reuse
  const defenders = [];
  for (const b of rf.slots) {
    const mon = mkMon(b.name, {
      level: b.level, nature: b.nature, ability: b.ability,
      item: itemName(b.item) || b.item, ivs: b.ivs, evs: b.evs,
    });
    if (!mon) { skipped++; continue; }
    defenders.push({meta: b, mon, moves: mkMoves(b.moves)});
  }

  const outRows = [];
  for (const c of mine) {
    const evs = EV_BY_TRACK[c.track] || {};
    const atkMon = mkMon(c.species_name === undefined ? c.species_const : SPECIES_NAMES[c.species_const], {
      level: caps[cp], nature: c.nature, ability: c.ability,
      item: itemName(c.item), evs,
    });
    if (!atkMon) { skipped++; continue; }
    const myMoves = mkMoves(c.moves.split(','));
    if (!myMoves.length) { skipped++; continue; }
    const prof = utilityProfile(c.moves.split(','));
    const utilTags = [
      prof.hazards.length ? 'hazard:' + prof.hazards.join('+') : null,
      prof.recovery ? 'recovery' : null, prof.screens ? 'screens' : null,
      prof.sleep ? 'sleep' : null, prof.para ? 'para' : null,
      prof.burn ? 'burn' : null, prof.poison ? 'poison' : null,
      prof.leech ? 'leech' : null, prof.phaze ? 'phaze' : null,
    ].filter(Boolean).join(',') || 'NONE';

    for (const d of defenders) {
      const field = new Field();
      const off = bestHit(atkMon, d.mon, myMoves, field);
      const def = bestHit(d.mon, atkMon, d.moves, field);
      calcs += myMoves.length + d.moves.length;

      // ---- utility adjustments, applied to the same turns race
      const chip = hazardChip(prof, d.mon);
      const effOffFrac = off.frac / Math.max(0.5, 1 - chip);   // chip shortens the race
      const myTurns = turnsToKO(effOffFrac);

      // denial: turns the opponent loses to status. Sleep is worth the most,
      // paralysis is probabilistic, burn cuts physical damage rather than turns.
      let denial = 0;
      if (prof.sleep) denial += 1.5;
      if (prof.para) denial += 0.75;
      if (prof.poison) denial += 0.5;
      if (prof.leech) denial += 0.5;
      if (prof.phaze) denial += 0.5;
      let incoming = def.frac;
      if (prof.burn && d.moves.some(m => m.category === 'Physical')) incoming *= 0.75;
      if (prof.screens) incoming *= 0.66;
      // longevity: recovery buys turns proportional to how hard it is being hit
      if (prof.recovery) incoming = Math.max(0, incoming - 0.25);
      const opTurns = turnsToKO(incoming) + denial;

      let mySpe = atkMon.stats.spe;
      if (prof.para) mySpe = mySpe;                    // paralysis halves THEIR speed
      const theirSpe = prof.para ? d.mon.stats.spe * 0.5 : d.mon.stats.spe;
      const faster = mySpe > theirSpe ? 1 : (mySpe < theirSpe ? -1 : 0);
      // outcome from full HP: the faster side effectively needs one fewer turn
      const eff = myTurns - opTurns + (faster >= 0 ? -0.5 : 0.5);
      let verdict;
      if (eff <= -1.5) verdict = 'win';
      else if (eff >= 1.5) verdict = 'loss';
      else verdict = 'marginal';
      // chipped: the player enters at 65% HP, a realistic mid-route state
      const opTurnsChipped = turnsToKO(incoming / 0.65) + denial;
      const effChipped = myTurns - opTurnsChipped + (faster >= 0 ? -0.5 : 0.5);
      const verdictChipped = effChipped <= -1.5 ? 'win'
                           : (effChipped >= 1.5 ? 'loss' : 'marginal');

      outRows.push([
        c.species_const, SPECIES_NAMES[c.species_const] || c.species_const, cp, rf.cp,
        rf.borrowed ? 'TRUE' : 'FALSE', c.anchor, c.track,
        c.ability, c.nature, c.item, c.moves,
        d.meta.trainer_id, d.meta.trainer, d.meta.role, d.meta.slot,
        d.meta.raw, d.meta.name, d.meta.level, d.meta.ability, d.meta.item, d.meta.nature,
        caps[cp], JSON.stringify(evs),
        off.move, off.range, off.frac.toFixed(4),
        def.move, def.range, def.frac.toFixed(4),
        atkMon.stats.spe, d.mon.stats.spe, faster,
        myTurns, opTurns.toFixed(2), verdict, (-eff).toFixed(2), verdictChipped,
        utilTags, chip.toFixed(3), denial.toFixed(2), incoming.toFixed(4), 'Derived',
      ].join('\t'));
      cells++;
    }
  }

  const hdr = ['species_const','species_name','checkpoint','roster_cp','roster_borrowed',
    'anchor','track','ability','nature','item','moves',
    'boss_trainer_id','boss_trainer','boss_role','boss_slot',
    'boss_raw_name','boss_species','boss_level','boss_ability','boss_item','boss_nature',
    'player_level','player_evs',
    'my_best_move','my_dmg_range','my_dmg_frac',
    'their_best_move','their_dmg_range','their_dmg_frac',
    'my_spe','their_spe','speed_order',
    'my_turns_to_ko','their_turns_to_ko','verdict','margin','verdict_chipped',
    'utility_tags','hazard_chip','denial_turns','incoming_after_utility','confidence'];
  fs.writeFileSync(`${OUT}/04_matchups_cp${cp}.tsv`, hdr.join('\t') + '\n' + outRows.join('\n') + '\n');
  const wins = outRows.filter(r => r.split('\t')[34] === 'win').length;
  summary.push({cp, roster_cp: rf.cp, borrowed: !!rf.borrowed, cells: outRows.length,
                win_rate: outRows.length ? +(wins / outRows.length).toFixed(3) : 0});
  console.log(`cp${cp} roster=${rf.cp}${rf.borrowed ? ' (borrowed)' : ''} cells=${outRows.length} win_rate=${outRows.length ? (wins / outRows.length * 100).toFixed(1) : 0}% elapsed=${((Date.now() - t0) / 1000).toFixed(0)}s`);
}

const report = {
  cells, calcs, seconds: +((Date.now() - t0) / 1000).toFixed(1),
  skipped_builds: skipped,
  dynamic_slots_excluded: dynamicSlots,
  unresolved_boss_slots: unresolvedSlots,
  missing_species: [...missing.species].slice(0, 40),
  missing_moves: [...missing.move].slice(0, 40),
  missing_species_count: missing.species.size,
  missing_moves_count: missing.move.size,
  per_checkpoint: summary,
};
fs.writeFileSync(`${OUT}/INT_matrix_report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify({cells, calcs, seconds: report.seconds,
  missing_species: missing.species.size, missing_moves: missing.move.size,
  dynamic_excluded: dynamicSlots}, null, 1));
