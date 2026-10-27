/* The Gate: front end for the membrane-brain toy game.
 * SPDX-License-Identifier: AGPL-3.0-only  (c) 2026 Jean-Francois Brisson
 * All numbers are computed by brain.py / rigor.py via py/bridge.py in Pyodide.
 * No network beyond this page's own files; no storage; no tracking. */
"use strict";
(() => {
const $ = (id) => document.getElementById(id);
const GOLD = [201, 168, 76], CYAN = [77, 216, 255];
const PY_FILES = ["brain.py", "rigor.py", "tests.py", "bridge.py"];
let pyodide = null, bridge = null, G = null;   // Pyodide, bridge module, geometry payload
const S = {tab: "observe", obs: null, t: 1, playing: false, selected: null,
           game: null, scan: null, bestBreak: 0, breakLog: []};

const call = (fn, ...a) => JSON.parse(bridge[fn](...a));
const status = (txt, state) => { const s = $("status"); s.textContent = txt; s.dataset.state = state || "loading"; };
const tick = () => new Promise((r) => setTimeout(r, 0));
const fmt = (x, n = 3) => (x === null || x === undefined ? "-" : Number(x).toFixed(n));

/* ------------------------------------------------------------ canvas */
const cv = $("brain"), ctx = cv.getContext("2d");
const XMIN = -24.5, XMAX = 24.5, YMIN = -10.2, YMAX = 10.2;
function sizeCanvas() {
  const r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(320, Math.round(r.width * dpr)), h = Math.round(w * (YMAX - YMIN) / (XMAX - XMIN));
  if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
}
const px = (x) => (x - XMIN) / (XMAX - XMIN) * cv.width;
const py_ = (y) => (YMAX - y) / (YMAX - YMIN) * cv.height;
function phaseColour(ph, amp, alphaMin = 0.25) {
  const t = (1 + Math.cos(ph)) / 2, b = alphaMin + (1 - alphaMin) * Math.pow(amp, 0.6);
  const c = GOLD.map((g, i) => Math.round(CYAN[i] + (g - CYAN[i]) * t));
  return `rgba(${c[0]},${c[1]},${c[2]},${b.toFixed(3)})`;
}
/* view = {edges, amp, phase, show:[bool], ring:[colour|null], mark:id|null, dim:[bool]} */
function draw(view) {
  sizeCanvas();
  const W = cv.width, H = cv.height, k = W / 960;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#070d20"; ctx.fillRect(0, 0, W, H);
  const N = G.nodes;
  // hemisphere outlines
  ctx.strokeStyle = "rgba(77,216,255,.18)"; ctx.lineWidth = 1.5 * k;
  for (const cx of [-11, 11]) { ctx.beginPath(); ctx.ellipse(px(cx), py_(0), 12 / (XMAX - XMIN) * W, 9 / (YMAX - YMIN) * H, 0, 0, 7); ctx.stroke(); }
  for (const [a, b, cross] of view.edges) {
    const on = !view.show || (view.show[a] && view.show[b]);
    ctx.strokeStyle = cross ? (on ? "rgba(77,216,255,.95)" : "rgba(77,216,255,.55)") : (on ? "rgba(201,168,76,.38)" : "rgba(120,140,190,.16)");
    ctx.lineWidth = (cross ? 2.6 : 1) * k;
    ctx.beginPath(); ctx.moveTo(px(N[a][0]), py_(N[a][1])); ctx.lineTo(px(N[b][0]), py_(N[b][1])); ctx.stroke();
  }
  N.forEach((n, i) => {
    const x = px(n[0]), y = py_(n[1]), r = 5.2 * k, lit = !view.show || view.show[i];
    if (view.dead && view.dead[i]) {
      ctx.strokeStyle = "rgba(255,123,123,.8)"; ctx.lineWidth = 1.6 * k;
      ctx.beginPath(); ctx.moveTo(x - r * .7, y - r * .7); ctx.lineTo(x + r * .7, y + r * .7); ctx.moveTo(x + r * .7, y - r * .7); ctx.lineTo(x - r * .7, y + r * .7); ctx.stroke();
      return;
    }
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7);
    ctx.fillStyle = lit && view.amp ? phaseColour(view.phase[i], view.amp[i]) : "rgba(120,140,190,.35)";
    ctx.fill();
    if (view.ring && view.ring[i]) { ctx.strokeStyle = view.ring[i]; ctx.lineWidth = 2.4 * k; ctx.beginPath(); ctx.arc(x, y, r + 3 * k, 0, 7); ctx.stroke(); }
  });
  for (const sid of G.seed_ids) {   // stored seeds: small diamond
    const x = px(N[sid][0]), y = py_(N[sid][1]), d = 9 * k;
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.6 * k;
    ctx.beginPath(); ctx.moveTo(x, y - d); ctx.lineTo(x + d, y); ctx.lineTo(x, y + d); ctx.lineTo(x - d, y); ctx.closePath(); ctx.stroke();
  }
  if (view.mark !== null && view.mark !== undefined) {
    const x = px(N[view.mark][0]), y = py_(N[view.mark][1]);
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.2 * k; ctx.setLineDash([4 * k, 3 * k]);
    ctx.beginPath(); ctx.arc(x, y, 12 * k, 0, 7); ctx.stroke(); ctx.setLineDash([]);
  }
}
function pickNeuron(ev) {
  const r = cv.getBoundingClientRect(), sx = r.width / (XMAX - XMIN), sy = r.height / (YMAX - YMIN);
  const cx = ev.clientX - r.left, cy = ev.clientY - r.top;
  let best = -1, bd = 1e9;
  G.nodes.forEach((n, i) => { const d = Math.hypot((n[0] - XMIN) * sx - cx, (YMAX - n[1]) * sy - cy); if (d < bd) { bd = d; best = i; } });
  return bd < 24 ? best : -1;
}

/* ------------------------------------------------------------ tabs */
function setTab(name) {
  S.tab = name; S.playing = false;
  document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  for (const t of ["observe", "gate", "break", "check"]) $("p-" + t).hidden = t !== name;
  $("stage").hidden = name === "check";
  $("tau-panel").hidden = !(name === "gate" || name === "break");
  if (name === "observe") renderObserve(); else if (name === "gate") renderGate();
  else if (name === "break") renderBreak(); else renderCheckEnv();
}

/* ------------------------------------------------------------ tau */
function showRates(r) {
  $("tau-v").textContent = fmt(r.tau);
  $("tau").value = Math.round(r.tau * 100);
  $("tau-rates").textContent = `At tau = ${fmt(r.tau)}: accepts ${Math.round(r.tpr * r.n)}/${r.n} noisy stored probes, accepts ${Math.round(r.fpr * r.n)}/${r.n} random fields (held-out sets).`;
}
$("tau").addEventListener("input", (e) => { const t = e.target.value / 100; showRates(call("set_tau", t)); onTauChange(); });
$("tau-reset").addEventListener("click", () => { showRates(call("reset_tau")); onTauChange(); });
function onTauChange() { if (S.tab === "break") refreshAttack(); }

/* ------------------------------------------------------------ observe */
function obsParams() {
  return [Number(document.querySelector('input[name=exp]:checked').value), document.querySelector('input[name=mode]:checked').value];
}
function renderObserve() {
  const [e, m] = obsParams();
  S.obs = call("spread", e, m);
  const o = S.obs, fin = o.delays.filter((d) => d !== null);
  $("tslider").max = 100; S.tmax = Math.ceil(Math.max(...fin));
  paintObserve();
  const hem = G.nodes[o.src][2] === 0 ? "left" : "right";
  $("obs-stats").innerHTML = [
    ["edges", `${o.n_edges} (${o.n_cross} cross)`],
    ["reached from the seed", `${o.reached}/128`],
    [`${hem === "left" ? "right" : "left"} hemisphere reached`, `${o.opp_reached}/${o.opp_total}`],
    ["median delay to the other side", o.median_opposite === null ? "unreachable" : fmt(o.median_opposite, 2)],
    ["wave vs stored memory, |overlap|", o.overlaps.map((v) => fmt(v, 2)).join(" / ")],
    ["gate says", o.verdict === "accept" ? "accept: " + o.name : "refuse"],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  $("obs-note").textContent = ({
    intact: "Intact graph: the 12 cross edges are the only bridge. Even here the 4-nearest-neighbour graph is not fully connected, so some neurons are never reached from this seed (that is a property of this random layout, not of anything real).",
    cut: "Cut: the same graph with every cross-hemisphere edge deleted. The other hemisphere is unreachable by construction; the wave field there is zero. The overlaps above compare this wave with the memory stored on the intact graph.",
    split: "Module split (coupling=False in brain.py): the graph is re-wired so each neuron links to its 4 nearest neighbours in its own hemisphere. That is a different graph, not the same one with edges removed (see RESULTS.md section 6).",
  })[m];
}
function paintObserve() {
  const o = S.obs, tt = S.t * S.tmax;
  const show = o.delays.map((d) => d !== null && d <= tt);
  const dead = o.delays.map((d) => d === null);
  draw({edges: o.edges, amp: o.amp, phase: o.phase, show, dead, mark: o.src});
  $("tval").textContent = `t = ${tt.toFixed(1)} of ${S.tmax}`;
}
$("tslider").addEventListener("input", (e) => { S.t = e.target.value / 100; paintObserve(); });
document.querySelectorAll('input[name=exp],input[name=mode]').forEach((i) => i.addEventListener("change", () => { S.t = 1; $("tslider").value = 100; renderObserve(); }));
$("play").addEventListener("click", () => {
  if (S.playing) { S.playing = false; return; }
  S.playing = true; if (S.t >= 1) S.t = 0;
  const step = () => { if (!S.playing || S.tab !== "observe") return; S.t = Math.min(1, S.t + 0.012); $("tslider").value = Math.round(S.t * 100); paintObserve(); if (S.t < 1) requestAnimationFrame(step); else S.playing = false; };
  requestAnimationFrame(step);
});

/* ------------------------------------------------------------ be the gate */
function bars(el, overlaps, tau, winIdx) {
  el.textContent = "";
  overlaps.forEach((v, i) => {
    const row = document.createElement("div"); row.className = "bar";
    const name = document.createElement("span"); name.textContent = G.names[i];
    const track = document.createElement("span"); track.className = "track";
    const fill = document.createElement("span"); fill.className = "fill" + (i === winIdx ? " win" : "");
    fill.style.width = Math.min(100, v * 100) + "%";
    const line = document.createElement("span"); line.className = "tauline"; line.title = "tau"; line.style.left = tau * 100 + "%";
    track.append(fill, line);
    const val = document.createElement("span"); val.textContent = fmt(v, 3);
    row.append(name, track, val); el.append(row);
  });
  const note = document.createElement("div"); note.className = "hint"; note.textContent = "red line = tau " + fmt(tau);
  el.append(note);
}
function newGame() {
  const run = Math.max(1, Math.min(99999, Number($("g-run").value) || 1));
  S.game = {run, level: 0, idx: 0, you: 0, gate: 0, n: 0, phase: "answering", hinted: false, hist: []};
  $("g-start").textContent = "Restart run";
  nextRound(true);
}
function totalRounds() { return G.levels.length * G.rounds_per_level; }
function nextRound(first) {
  const g = S.game;
  if (!first) { g.idx++; if (g.idx >= G.rounds_per_level) { g.idx = 0; g.level++; } }
  if (g.level >= G.levels.length) return endGame();
  g.phase = "answering"; g.hinted = false;
  const r = call("new_round", g.run, g.level, g.idx);
  g.round = r;
  draw({edges: G.edges, amp: r.amp, phase: r.phase});
  $("g-bars").innerHTML = ""; $("g-result").textContent = "";
  $("g-prompt").textContent = `Level ${g.level + 1}: ${G.levels[g.level].name} (noise sigma ${G.levels[g.level].sigma}). Which stored experience did this field come from, or is it none of them?`;
  setGameButtons();
}
function setGameButtons() {
  const g = S.game, live = g && g.phase === "answering";
  document.querySelectorAll("#g-answers button").forEach((b) => (b.disabled = !live));
  $("g-hint").disabled = !live || g.hinted; $("g-next").disabled = !g || g.phase !== "revealed";
  $("g-round").textContent = g ? `${Math.min(g.n + (g.phase === "answering" ? 1 : 0), totalRounds())}/${totalRounds()}` : "0/" + totalRounds();
  $("g-level").textContent = g && g.level < G.levels.length ? `${g.level + 1} ${G.levels[g.level].name}` : "-";
  $("g-you").textContent = g ? g.you : 0; $("g-gate").textContent = g ? g.gate : 0;
}
function answer(choice) {
  const g = S.game; if (!g || g.phase !== "answering") return;
  const r = call("grade", g.run, g.level, g.idx, choice, g.hinted);
  g.phase = "revealed"; g.n++; g.you += r.you_points; g.gate += r.gate_points; g.hist.push(r);
  bars($("g-bars"), r.overlaps, r.tau, r.overlaps.indexOf(Math.max(...r.overlaps)));
  const truth = r.kind === "pattern" ? `a noisy copy of <b>${r.truth_name}</b>` : r.kind === "random" ? "a <b>random field</b> (stored nowhere)" : "a wave from neuron " + r.src + ", <b>never stored</b>";
  const gateTxt = r.gate_choice >= 0 ? "accepted as " + G.names[r.gate_choice] : "refused";
  const mine = choice >= 0 ? "named " + G.names[choice] : "refused";
  $("g-result").innerHTML = `It was ${truth}. You ${mine}: <b class="${r.you_ok ? "good" : "bad"}">${r.you_ok ? "right" : "wrong"} (${r.you_points >= 0 ? "+" : ""}${r.you_points})</b>. The real gate ${gateTxt}: <b class="${r.gate_ok ? "good" : "bad"}">${r.gate_ok ? "right" : "wrong"} (${r.gate_points >= 0 ? "+" : ""}${r.gate_points})</b>. Best |overlap| ${fmt(r.e)} vs tau ${fmt(r.tau)}.`;
  setGameButtons();
  if (g.level === G.levels.length - 1 && g.idx === G.rounds_per_level - 1) $("g-next").textContent = "Finish"; else $("g-next").textContent = "Next";
}
function endGame() {
  const g = S.game; g.phase = "done"; setGameButtons();
  const yo = g.hist.filter((h) => h.you_ok).length, go = g.hist.filter((h) => h.gate_ok).length;
  draw({edges: G.edges});
  $("g-bars").innerHTML = "";
  $("g-prompt").textContent = "Run finished.";
  $("g-result").innerHTML = `Run ${g.run}, tau ${fmt(G.tau)}: you ${g.you} points (${yo}/${g.hist.length} right), real gate ${g.gate} points (${go}/${g.hist.length} right). ` +
    (g.you > g.gate ? "You beat the gate." : g.you === g.gate ? "A tie." : "The gate won this one.") + " Change the run id for a new set of probes.";
  $("g-next").textContent = "Next";
}
document.querySelectorAll("#g-answers button").forEach((b) => b.addEventListener("click", () => answer(Number(b.dataset.ans))));
$("g-start").addEventListener("click", newGame);
$("g-next").addEventListener("click", () => nextRound(false));
$("g-hint").addEventListener("click", () => {
  const g = S.game; if (!g || g.phase !== "answering" || g.hinted) return;
  g.hinted = true; const h = call("hint", g.run, g.level, g.idx);
  bars($("g-bars"), h.overlaps, h.tau, -1); setGameButtons();
});
function renderGate() {
  const g = S.game;
  if (g && g.round && g.phase === "answering") draw({edges: G.edges, amp: g.round.amp, phase: g.round.phase});
  else draw({edges: G.edges});
  setGameButtons();
}

/* ------------------------------------------------------------ break the gate */
function breakParams() { return [S.selected, $("b-alpha").value / 100, $("b-sigma").value / 100]; }
function refreshAttack() {
  const [src, alpha, sigma] = breakParams();
  $("b-alpha-v").textContent = Math.round(alpha * 100) + "%"; $("b-sigma-v").textContent = sigma.toFixed(2);
  if (S.scan && S.scan.sigma !== sigma) S.scan = null;
  if (src === null) { drawBreak(null); return; }
  const a = call("attack", src, alpha, sigma);
  S.lastAttack = a;
  drawBreak(a);
  bars($("b-bars"), a.overlaps, a.tau, a.overlaps.indexOf(Math.max(...a.overlaps)));
  $("b-stats").innerHTML = [
    ["source neuron", `#${a.src} (${G.nodes[a.src][2] ? "right" : "left"}${a.stored ? ", STORED seed" : ""})`],
    ["distance to nearest stored seed", fmt(a.dist, 2)],
    ["best |overlap| / tau", `${fmt(a.e)} / ${fmt(a.tau)}`],
    ["gate says", a.verdict === "accept" ? "accept: " + a.name : "refuse"],
  ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  let msg;
  if (a.fooled) { msg = `<b class="good">Fooled the gate!</b> It accepted a wave from a never-stored neuron ${fmt(a.dist, 1)} units from any stored seed and named it "${a.name}". Score +${a.points}.`; recordBreak(a); }
  else if (a.verdict === "accept" && a.stored) msg = "Accepted, but this neuron is a stored seed: that is the gate working as designed.";
  else if (a.verdict === "accept") msg = `Accepted as "${a.name}", but the source is only ${fmt(a.dist, 1)} units from a stored seed (needs at least 6): a neighbouring wave looks like the stored one. Pick a more distant neuron.`;
  else msg = "Refused. Try fewer noise, more wave share, or a different neuron.";
  $("b-result").innerHTML = msg;
}
function drawBreak(a) {
  const ring = new Array(128).fill(null);
  if (S.scan) S.scan.rows.forEach(([id, acc]) => { ring[id] = acc ? "rgba(77,255,136,.9)" : "rgba(255,123,123,.55)"; });
  draw({edges: G.edges, amp: a ? a.amp : null, phase: a ? a.phase : null, ring, mark: S.selected});
}
function recordBreak(a) {
  const key = a.src + "|" + a.alpha + "|" + a.sigma;
  if (S.breakLog.some((l) => l.key === key)) return;
  S.breakLog.push({key, src: a.src, alpha: a.alpha, sigma: a.sigma, points: a.points, name: a.name});
  S.breakLog.sort((x, y) => y.points - x.points); S.breakLog = S.breakLog.slice(0, 5);
  S.bestBreak = S.breakLog[0].points; $("b-best").textContent = S.bestBreak;
  $("b-log").innerHTML = S.breakLog.map((l) => `<li>neuron #${l.src}, wave share ${Math.round(l.alpha * 100)}%, sigma ${l.sigma.toFixed(2)}: accepted as ${l.name}, +${l.points}</li>`).join("");
}
function renderBreak() { $("b-stealth").disabled = $("b-scan").disabled = false; if (S.selected !== null) refreshAttack(); else drawBreak(null); }
cv.addEventListener("click", (ev) => {
  if (S.tab !== "break") return;
  const i = pickNeuron(ev); if (i < 0) return;
  S.selected = i; refreshAttack();
});
["b-alpha", "b-sigma"].forEach((id) => $(id).addEventListener("input", refreshAttack));
$("b-stealth").addEventListener("click", () => {
  if (S.selected === null) { $("b-result").textContent = "Tap a neuron first."; return; }
  const [src, , sigma] = breakParams(), r = call("stealth", src, sigma);
  if (r.alpha_min === null) { $("b-result").textContent = `Neuron #${src}: the gate refuses at every wave share up to 100% (sigma ${sigma.toFixed(2)}).`; return; }
  $("b-alpha").value = Math.round(r.alpha_min * 100); refreshAttack();
  $("b-result").innerHTML += ` <br>Least wave share the gate accepts for neuron #${src}: <b>${Math.round(r.alpha_min * 100)}%</b>.`;
});
$("b-scan").addEventListener("click", async () => {
  const sigma = $("b-sigma").value / 100, rows = [];
  $("b-scan").disabled = true; S.scan = {sigma, rows};
  for (let s = 0; s < 128; s += 16) {
    rows.push(...call("scan", s, 16, sigma));
    $("b-result").textContent = `Scanning ${rows.length}/128...`; drawBreak(S.lastAttack || null); await tick();
  }
  const far = rows.filter(([id]) => farFromSeeds(id)), acc = rows.filter((r) => r[1]), farAcc = far.filter((r) => r[1]);
  $("b-result").innerHTML = `Scan at sigma ${sigma.toFixed(2)}, tau ${fmt(call("rates_now").tau)}: the gate accepts waves from <b>${acc.length}/128</b> neurons; of the ${far.length} neurons at least 6 units from every stored seed it accepts <b>${farAcc.length}</b> (green rings = accepted, red = refused). Those are gaps in this toy gate, measured on this one layout.`;
  $("b-scan").disabled = false; drawBreak(S.lastAttack || null);
});
function farFromSeeds(id) {
  const n = G.nodes[id]; return G.seed_ids.every((s) => Math.hypot(n[0] - G.nodes[s][0], n[1] - G.nodes[s][1]) >= 6);
}

/* ------------------------------------------------------------ test the code */
const GROUPS = [["readme", "Reproduce the README numbers (seed 42)"], ["determinism", "Determinism"], ["null", "Null control: shuffled labels"], ["unit", "The repository's own unit tests"]];
function renderCheckEnv() { if (!$("c-groups").innerHTML) buildCheckTable(); }
function buildCheckTable() {
  $("c-groups").innerHTML = GROUPS.map(([id, title]) => `<h3>${title}</h3><div class="tbl"><table class="checks" id="t-${id}"><thead><tr><th>check</th><th>published / expected</th><th>measured here</th><th></th></tr></thead><tbody></tbody></table></div>`).join("");
}
async function runChecks() {
  buildCheckTable(); $("c-run").disabled = true;
  let pass = 0, total = 0; const t0 = performance.now();
  for (const [id] of GROUPS) {
    await tick();
    const rows = call("run_checks", id);
    $("t-" + id).querySelector("tbody").innerHTML = rows.map((r) => `<tr data-check="${r.id}"><td>${r.label}${r.note ? `<br><small>${r.note}</small>` : ""}</td><td>${r.expected}</td><td>${r.measured}</td><td><span class="badge" data-ok="${r.ok}">${r.ok ? "PASS" : "FAIL"}</span></td></tr>`).join("");
    rows.forEach((r) => { total++; pass += r.ok ? 1 : 0; });
  }
  const ms = Math.round(performance.now() - t0);
  $("c-sum").textContent = `${pass}/${total} checks pass (${ms} ms)`; $("c-sum").dataset.pass = pass; $("c-sum").dataset.total = total;
  $("c-env").textContent = "Executed by Python " + pyodide.runPython("import platform; platform.python_version()") + " in WebAssembly (Pyodide " + pyodide.version + "). The fingerprint row compares against the value computed under CPython: equality is evidence that the browser build computes the same patterns, not a proof for every platform.";
  $("c-run").disabled = false;
}
$("c-run").addEventListener("click", runChecks);

/* ------------------------------------------------------------ boot */
async function boot() {
  try {
    status("Loading Python (WebAssembly)... first load downloads about 14 MB from this site only.");
    pyodide = await loadPyodide({indexURL: "vendor/pyodide/"});
    status("Loading brain.py ...");
    pyodide.FS.mkdirTree("/home/pyodide/game");
    for (const f of PY_FILES) {
      const r = await fetch("py/" + f); if (!r.ok) throw new Error("cannot fetch py/" + f);
      pyodide.FS.writeFile("/home/pyodide/game/" + f, new Uint8Array(await r.arrayBuffer()));
    }
    pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/game')");
    bridge = pyodide.pyimport("bridge");
    status("Building the toy brain and calibrating the gate...");
    await tick();
    G = call("init", 42);
    S.tmax = 100;
    showRates(G.rates);
    // expose a read-only test handle
    window.__gate = {geometry: G, call};
    status(`Ready: ${G.nodes.length} neurons, ${G.n_edges} edges, ${G.cross} cross edges, tau ${fmt(G.tau)}. Python ${pyodide.runPython("import platform; platform.python_version()")} (WebAssembly).`, "ready");
    document.body.dataset.ready = "1";
    $("c-run").disabled = false;
    setTab("observe");
    S.t = 1; paintObserve();
  } catch (e) {
    status("Could not start Python: " + e, "error"); document.body.dataset.ready = "error"; console.error(e);
  }
}
document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { if (G) setTab(b.dataset.tab); }));
window.addEventListener("resize", () => { if (!G) return; if (S.tab === "observe") paintObserve(); else if (S.tab === "gate") renderGate(); else if (S.tab === "break") renderBreak(); });
boot();
})();
