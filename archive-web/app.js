/* 千分の一の国 — UI 制御 / API / グラフ
 *
 * 依存ライブラリなし。ビルド不要。
 * サーバ契約は server/app.py の simulate() の docstring。
 * 系列キーを変えるときは下の SERIES と app.py の2か所。
 */

import { Town } from './town3d.js';

const SERIES = [
  { key: 'gdp',          label: 'GDP',     en: 'monthly',      fmt: fmtYen,                    axis: yenAxis },
  { key: 'cpi',          label: '物価指数', en: 'CPI',          fmt: v => (v * 100).toFixed(1), axis: numAxis(100, '') },
  { key: 'unemployment', label: '失業率',   en: 'unemployment', fmt: fmtPct,                    axis: numAxis(100, '%') },
  { key: 'gini',         label: 'ジニ係数', en: 'gini',         fmt: v => v.toFixed(3),         axis: numAxis(1, '') },
  { key: 'gov_debt',     label: '政府債務', en: 'debt',         fmt: fmtYen,                    axis: yenAxis },
  { key: 'gov_balance',  label: '財政収支', en: 'balance',      fmt: fmtYen,                    axis: yenAxis },
];

function fmtYen(v) {
  const a = Math.abs(v);
  if (a >= 1e12) return (v / 1e12).toFixed(2) + '兆円';
  if (a >= 1e8)  return (v / 1e8).toFixed(0) + '億円';
  if (a >= 1e4)  return (v / 1e4).toFixed(0) + '万円';
  return Math.round(v).toLocaleString('ja-JP') + '円';
}
function fmtPct(v) { return (v * 100).toFixed(2) + '%'; }

/* 軸は「値ごと」ではなく「軸ごと」に書式を1つ決める。
   値ごとだと同じ軸に「9764億」と「1.1兆」が並び、幅が狭いと 0.37 が2つ並ぶ。 */
function yenAxis(lo, hi) {
  const a = Math.max(Math.abs(lo), Math.abs(hi));
  const [div, sfx] = a >= 1e12 ? [1e12, '兆'] : a >= 1e8 ? [1e8, '億'] : a >= 1e4 ? [1e4, '万'] : [1, ''];
  const step = Math.abs(hi - lo) / 3 / div;
  const dp = step >= 10 ? 0 : step >= 1 ? 1 : 2;
  return v => (v / div).toFixed(dp) + sfx;
}
function numAxis(scale, unit) {
  return (lo, hi) => {
    const step = (Math.abs(hi - lo) / 3) * scale;
    const dp = step >= 10 ? 0 : step >= 1 ? 1 : step >= 0.1 ? 2 : 3;
    return v => (v * scale).toFixed(dp) + unit;
  };
}

const $ = id => document.getElementById(id);
const el = {};
for (const id of ['synthetic-banner','presets','law','months','seed','run','status','charts','legend',
  'view-toggle','table-view','tooltip','warnings','warnings-list','error','error-kind','error-pos',
  'error-message','error-snippet','error-hint','town','gazette','gz-fold',
  'law-no','hud-year','hud-mon','hud-phase','hud-unemp','hud-cpi','hud-gini','stamp','stamp-name',
  'play','scrub','tl-read','report','ab','li-unemp','viewhint','about','about-open','about-close']) {
  el[id.replace(/-(\w)/g, (_, c) => c.toUpperCase())] = $(id);
}

let lastResult = null;
let showTable = false;
let lawCount = 0;

const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// --- 起動 ------------------------------------------------------------------

init();

async function init() {
  Town.init(el.town);
  // カメラを触ったらヒントを消す。要素が無くても落ちないようにする
  const hideHint = () => el.viewhint && el.viewhint.classList.add('gone');
  ['pointerdown', 'wheel'].forEach(ev => el.town.addEventListener(ev, hideHint, { once: true }));
  setTimeout(hideHint, 9000);
  Town.onMonth = onTownMonth;

  try {
    const h = await fetch('/api/health').then(r => r.json());
    if (h.demo) el.syntheticBanner.hidden = false;
  } catch (_) {}

  try { renderPresets(await fetch('/api/laws').then(r => r.json())); }
  catch (_) { el.presets.innerHTML = '<button type="button">例文を読めません</button>'; }

  run(true);          // baseline を1本流して街を生かす
}

function renderPresets(laws) {
  el.presets.innerHTML = '';
  const mk = (name, src) => {
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = name; b.setAttribute('aria-pressed', 'false');
    b.onclick = () => {
      el.law.value = src;
      [...el.presets.children].forEach(o => o.setAttribute('aria-pressed', String(o === b)));
    };
    return b;
  };
  laws.forEach(l => el.presets.appendChild(mk(l.name, l.source)));
  el.presets.appendChild(mk('白紙', ''));
}

// --- 実行 ------------------------------------------------------------------

el.run.onclick = () => run(false);
el.law.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') run(false);
});

async function run(silent) {
  el.run.disabled = true;
  hideError();
  const payload = { months: +el.months.value, seed: +el.seed.value, law: el.law.value };
  const named = (el.law.value.match(/法律\s*"([^"]+)"/) || [])[1];

  if (!silent && payload.law.trim()) stampIt(named || '施行');
  el.status.textContent = '計算中';

  const t0 = performance.now();
  try {
    const res = await fetch('/api/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => null);

    if (!res.ok) { showError(body, res.status); el.status.textContent = '失敗'; return; }

    lastResult = body;
    el.syntheticBanner.hidden = !body.synthetic;
    renderWarnings(body.warnings || []);

    const hasLaw = !!body.runs.treatment;

    // 法文から効果の種類を読み取り、街に渡す。
    // W2 で DSL の IR が来たら body.law.ir を見るように差し替える(TODO)。
    const src = payload.law;
    let fx = null;
    if (hasLaw) {
      const type = /禁止/.test(src) ? 'gacha'
                 : /給付/.test(src) ? 'benefit'
                 : /税率変更/.test(src) ? 'vat' : 'other';
      fx = { type, name: named || '法律', enact: body.enact_month ?? 0 };
    }
    Town.setLaw(fx);
    el.ab.hidden = !hasLaw;
    setVariantUI(hasLaw ? 'treatment' : 'baseline');
    Town.setRun(body, hasLaw ? 'treatment' : 'baseline');
    el.scrub.max = String(body.runs.baseline.months.length - 1);

    if (hasLaw) { lawCount++; el.lawNo.textContent = `法律 第${lawCount}号`; }
    renderResult(body);

    el.status.textContent = `${payload.months}ヶ月 × ${hasLaw ? 2 : 1}本 / seed=${payload.seed} / ${Math.round(performance.now() - t0)}ms`;
  } catch (_) {
    showError({ detail: { kind: '接続エラー', message: 'サーバに繋がりません。uvicorn は起動していますか?',
      hint: '.venv/bin/uvicorn server.app:app --reload --port 8000' } }, 0);
    el.status.textContent = '失敗';
  } finally { el.run.disabled = false; }
}

/* 施行 = 朱印を捺す。押した瞬間に世界が変わる、という意味を持たせている */
function stampIt(name) {
  el.stampName.textContent = name;
  el.stamp.hidden = false;
  const wrap = el.town.parentElement;
  wrap.classList.add('shake');
  setTimeout(() => wrap.classList.remove('shake'), 380);
  setTimeout(() => { el.stamp.hidden = true; }, 1150);
}

// --- 街とのつなぎ ----------------------------------------------------------

function onTownMonth(m, phase) {
  el.hudYear.textContent = Math.floor(m / 12);
  el.hudMon.textContent = (m % 12) + 1;
  el.hudPhase.textContent = Town.phaseName;
  el.scrub.value = String(m);
  el.tlRead.textContent = `${m + 1} / ${Town.length}ヶ月`;

  if (!lastResult) return;
  const d = lastResult.runs[Town.variant] || lastResult.runs.baseline;
  const u = d.series.unemployment[m];
  el.hudUnemp.textContent = (u * 100).toFixed(2) + '%';
  el.liUnemp.classList.toggle('alert', u > d.series.unemployment[0] * 1.15);
  el.hudCpi.textContent = (d.series.cpi[m] * 100).toFixed(1);
  el.hudGini.textContent = d.series.gini[m].toFixed(3);
}

el.scrub.oninput = () => { Town.setPlaying(false); el.play.textContent = '▶'; Town.seek(+el.scrub.value); };
el.play.onclick = () => {
  const p = el.play.textContent === '▶';
  Town.setPlaying(p);
  el.play.textContent = p ? '❚❚' : '▶';
};

el.ab.querySelectorAll('button').forEach(b => {
  b.onclick = () => setVariantUI(b.dataset.v, true);
});
function setVariantUI(v, apply) {
  el.ab.querySelectorAll('button').forEach(b => {
    const on = b.dataset.v === v;
    b.classList.toggle('on', on);
    b.classList.toggle('pill-coral', on && b.dataset.v === 'treatment');
    b.classList.toggle('pill-blue', on && b.dataset.v === 'baseline');
  });
  if (apply) Town.setVariant(v);
}

el.gzFold.onclick = () => {
  const g = el.gazette;
  g.classList.toggle('folded');
  el.gzFold.textContent = g.classList.contains('folded') ? '▸' : '▾';
};

el.aboutOpen.onclick = () => { el.about.hidden = false; document.body.style.overflow = 'hidden'; };
const closeAbout = () => { el.about.hidden = true; document.body.style.overflow = ''; };
el.aboutClose.onclick = closeAbout;
el.about.addEventListener('click', e => { if (e.target === el.about) closeAbout(); });
addEventListener('keydown', e => { if (e.key === 'Escape' && !el.about.hidden) closeAbout(); });

// --- エラー・警告 ----------------------------------------------------------
// サーバが返した日本語をそのまま出す。UI で言い換えない。

function showError(body, status) {
  let d = body && body.detail;
  if (Array.isArray(d)) d = { kind: '入力エラー', message: d.map(x => x.msg).join(' / ') };
  if (!d) d = { kind: 'エラー', message: `サーバが ${status} を返しました。` };

  el.errorKind.textContent = d.kind || 'エラー';
  el.errorMessage.textContent = d.message || '';
  const has = d.line != null;
  el.errorPos.textContent = has ? `${d.line}行 ${d.col != null ? d.col + '文字' : ''}` : '';
  const sn = has ? snippet(el.law.value, d.line, d.col) : null;
  el.errorSnippet.textContent = sn || ''; el.errorSnippet.hidden = !sn;
  el.errorHint.textContent = d.hint || ''; el.errorHint.hidden = !d.hint;
  el.error.hidden = false;
  el.gazette.classList.remove('folded');
}
function hideError() { el.error.hidden = true; el.warnings.hidden = true; }

function renderWarnings(list) {
  if (!list.length) { el.warnings.hidden = true; return; }
  el.warningsList.innerHTML = '';
  list.forEach(w => { const li = document.createElement('li'); li.textContent = w; el.warningsList.appendChild(li); });
  el.warnings.hidden = false;
}

function snippet(src, line, col) {
  const L = src.split('\n');
  if (line < 1 || line > L.length) return null;
  const g = String(line);
  return `${g} | ${L[line - 1]}\n${' '.repeat(g.length)} | ${' '.repeat(Math.max(0, (col || 1) - 1))}^`;
}

// --- グラフ ----------------------------------------------------------------

el.viewToggle.onclick = () => {
  showTable = !showTable;
  el.viewToggle.textContent = showTable ? 'グラフで見る' : '表で見る';
  renderResult(lastResult);
};

let rz = null;
window.addEventListener('resize', () => {
  if (!lastResult || showTable) return;
  clearTimeout(rz); rz = setTimeout(() => renderResult(lastResult), 150);
});

function renderResult(result) {
  if (!result) return;
  const base = result.runs.baseline, treat = result.runs.treatment;
  el.legend.hidden = !treat;

  if (showTable) {
    el.charts.hidden = true; el.tableView.hidden = false;
    return renderTable(base, treat);
  }
  el.charts.hidden = false; el.tableView.hidden = true;
  el.charts.innerHTML = '';

  for (const def of SERIES) {
    if (!base.series[def.key]) continue;
    const card = document.createElement('div');
    card.className = 'chart';
    card.innerHTML = `<div class="chart-head"><p class="chart-title">${def.label}</p>` +
      `<span class="chart-en">${def.en}</span></div><p class="chart-delta">${delta(def, base, treat)}</p>`;
    el.charts.appendChild(card);
    drawChart(card, def, {
      months: base.months, baseline: base.series[def.key],
      treatment: treat ? treat.series[def.key] : null,
      warmup: base.warmup ?? 0, enact: result.enact_month ?? null,
    });
  }
}

function delta(def, base, treat) {
  const b = base.series[def.key], last = b[b.length - 1];
  if (!treat) return `最終月 ${def.fmt(last)}`;
  const t = treat.series[def.key], lt = t[t.length - 1], d = lt - last;
  const pct = last !== 0 ? (d / Math.abs(last)) * 100 : 0;
  return `${def.fmt(last)} → ${def.fmt(lt)}(${d >= 0 ? '+' : '−'}${Math.abs(pct).toFixed(1)}%)`;
}

const NS = 'http://www.w3.org/2000/svg';
function sv(n, a) { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); return e; }

function drawChart(card, def, data) {
  const width = Math.max(250, card.clientWidth - 28), height = 142;
  const m = { top: 8, right: 50, bottom: 19, left: 46 };
  const iw = width - m.left - m.right, ih = height - m.top - m.bottom;

  const all = data.treatment ? data.baseline.concat(data.treatment) : data.baseline;
  let lo = Math.min(...all), hi = Math.max(...all);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * .12; lo -= pad; hi += pad;

  const af = def.axis(lo, hi), n = data.months.length;
  const x = i => m.left + (n <= 1 ? 0 : (i / (n - 1)) * iw);
  const y = v => m.top + ih - ((v - lo) / (hi - lo)) * ih;

  const svg = sv('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': def.label });
  const cB = cssVar('--series-base'), cT = cssVar('--series-treat');
  const cG = cssVar('--grid'), c3 = cssVar('--ink-3'), c2 = cssVar('--ink-2'), cS = cssVar('--paper-2');

  if (data.warmup > 0 && data.warmup < n)
    svg.appendChild(sv('rect', { x: m.left, y: m.top, width: x(data.warmup) - m.left, height: ih, fill: cssVar('--warmup') }));

  for (let k = 0; k <= 3; k++) {
    const v = lo + ((hi - lo) * k) / 3;
    svg.appendChild(sv('line', { x1: m.left, x2: m.left + iw, y1: y(v), y2: y(v), stroke: cG, 'stroke-width': 1 }));
    const t = sv('text', { x: m.left - 7, y: y(v) + 3.5, 'text-anchor': 'end', 'font-size': 9.5, fill: c3 });
    t.textContent = af(v); svg.appendChild(t);
  }
  for (let mo = 0; mo < n; mo += 12) {
    const t = sv('text', { x: x(mo), y: height - 5, 'text-anchor': 'middle', 'font-size': 9.5, fill: c3 });
    t.textContent = (mo / 12) + '年'; svg.appendChild(t);
  }
  if (data.enact != null && data.enact < n) {
    svg.appendChild(sv('line', { x1: x(data.enact), x2: x(data.enact), y1: m.top, y2: m.top + ih,
      stroke: c3, 'stroke-width': 1, 'stroke-dasharray': '3 3' }));   // 朱にしない(系列の橙と混同するため)
    const t = sv('text', { x: x(data.enact) + 3, y: m.top + 9, 'font-size': 9, fill: c3 });
    t.textContent = '施行'; svg.appendChild(t);
  }

  const path = v => v.map((q, i) => (i ? 'L' : 'M') + x(i) + ' ' + y(q)).join('');
  svg.appendChild(sv('path', { d: path(data.baseline), fill: 'none', stroke: cB, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
  if (data.treatment)
    svg.appendChild(sv('path', { d: path(data.treatment), fill: 'none', stroke: cT, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));

  const labs = [{ v: data.baseline[n - 1], c: cB, name: 'なし' }];
  if (data.treatment) labs.push({ v: data.treatment[n - 1], c: cT, name: '施行後' });
  let ys = labs.map(l => y(l.v));
  if (ys.length === 2 && Math.abs(ys[0] - ys[1]) < 12) {
    const mid = (ys[0] + ys[1]) / 2; ys = ys[0] < ys[1] ? [mid - 6, mid + 6] : [mid + 6, mid - 6];
  }
  labs.forEach((l, i) => {
    svg.appendChild(sv('circle', { cx: x(n - 1), cy: y(l.v), r: 4, fill: l.c, stroke: cS, 'stroke-width': 2 }));
    const t = sv('text', { x: m.left + iw + 8, y: ys[i] + 3.5, 'font-size': 9.5, fill: c2 });
    t.textContent = l.name; svg.appendChild(t);   // 文字は系列色にしない
  });

  const cross = sv('line', { y1: m.top, y2: m.top + ih, stroke: c3, 'stroke-width': 1, opacity: 0 });
  svg.appendChild(cross);
  const dots = labs.map(l => sv('circle', { r: 4.5, fill: l.c, stroke: cS, 'stroke-width': 2, opacity: 0 }));
  dots.forEach(d => svg.appendChild(d));
  const hit = sv('rect', { x: m.left, y: m.top, width: iw, height: ih, fill: 'transparent' });
  svg.appendChild(hit);

  hit.addEventListener('mousemove', ev => {
    const box = svg.getBoundingClientRect();
    let i = Math.round(((((ev.clientX - box.left) / box.width) * width - m.left) / iw) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('opacity', 1);
    const vs = [data.baseline[i]]; if (data.treatment) vs.push(data.treatment[i]);
    dots.forEach((d, k) => { d.setAttribute('cx', x(i)); d.setAttribute('cy', y(vs[k])); d.setAttribute('opacity', 1); });

    // グラフのホバーで街も同じ月へ飛ぶ。絵と数字が同じものである証明
    Town.setPlaying(false); el.play.textContent = '▶'; Town.seek(i);

    el.tooltip.innerHTML = `<div class="tt-month">${Math.floor(i / 12)}年${(i % 12) + 1}ヶ月目${i < data.warmup ? ' — ウォームアップ' : ''}</div>` +
      vs.map((v, k) => `<div class="tt-row"><span class="swatch" style="background:${labs[k].c}"></span>${labs[k].name}<span class="tt-val">${def.fmt(v)}</span></div>`).join('');
    el.tooltip.hidden = false;
    el.tooltip.style.left = Math.min(ev.clientX + 14, innerWidth - el.tooltip.offsetWidth - 8) + 'px';
    el.tooltip.style.top = (ev.clientY + 14) + 'px';
  });
  hit.addEventListener('mouseleave', () => {
    cross.setAttribute('opacity', 0); dots.forEach(d => d.setAttribute('opacity', 0)); el.tooltip.hidden = true;
  });

  card.appendChild(svg);
}

function renderTable(base, treat) {
  const keys = SERIES.filter(d => base.series[d.key]);
  let h = '<table><thead><tr><th>月</th>';
  keys.forEach(d => { h += `<th>${d.label}(なし)</th>`; if (treat) h += `<th>${d.label}(施行後)</th>`; });
  h += '</tr></thead><tbody>';
  for (let i = 0; i < base.months.length; i++) {
    h += `<tr><td>${i}${i < (base.warmup ?? 0) ? ' *' : ''}</td>`;
    keys.forEach(d => { h += `<td>${d.fmt(base.series[d.key][i])}</td>`; if (treat) h += `<td>${d.fmt(treat.series[d.key][i])}</td>`; });
    h += '</tr>';
  }
  el.tableView.innerHTML = h + '</tbody></table>';
}
