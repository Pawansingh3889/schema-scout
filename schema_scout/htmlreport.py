"""Render the catalog as a single self-contained HTML dashboard.

The output is one file with the data embedded and zero external resources
(no CDN, no fonts, no network) so it opens offline by double-clicking and
nothing leaves the machine. It's built for a decision-maker: lead with the
domains and let them sort by what they care about (data volume, PII exposure,
modelling debt, query usage), trace how any two tables join, see health
issues, and drill into any table.
"""
from __future__ import annotations

import json

from schema_scout import domains, lint, render
from schema_scout.model import Catalog

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data catalog — schema-scout</title>
<style>
  :root {
    --bg:#0f172a; --panel:#1e293b; --panel2:#273449; --line:#334155;
    --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8;
    --fact:#3b82f6; --dimension:#10b981; --bridge:#a855f7;
    --reference:#64748b; --unknown:#9ca3af; --pii:#ef4444; --warn:#f59e0b;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.45;
  }
  header {
    padding:28px 32px; background:linear-gradient(120deg,#0ea5e9,#6366f1);
    color:#fff;
  }
  header h1 { margin:0 0 4px; font-size:24px; letter-spacing:.2px; }
  header p { margin:0; opacity:.9; font-size:14px; }
  .wrap { max-width:1200px; margin:0 auto; padding:24px 32px 64px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:14px; margin:-44px 0 28px; }
  .kpi { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:0 8px 24px rgba(0,0,0,.25); }
  .kpi .n { font-size:28px; font-weight:700; }
  .kpi .l { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.6px; }
  .kpi .sub { font-size:12px; color:var(--accent); margin-top:2px; }
  h2 { font-size:16px; margin:32px 0 14px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  h2 .hint { font-size:12px; color:var(--muted); font-weight:400; }
  .controls { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:14px; }
  select, input[type=search] {
    background:var(--panel2); color:var(--text); border:1px solid var(--line);
    border-radius:8px; padding:8px 10px; font-size:13px;
  }
  input[type=search] { min-width:240px; }
  button {
    background:var(--accent); color:#06283d; border:none; border-radius:8px;
    padding:8px 14px; font-size:13px; font-weight:700; cursor:pointer;
  }
  button:hover { filter:brightness(1.06); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; }
  .card {
    background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--accent);
    border-radius:12px; padding:16px; cursor:pointer; transition:transform .08s, border-color .08s;
  }
  .card:hover { transform:translateY(-2px); border-color:var(--accent); }
  .card.active { outline:2px solid var(--accent); }
  .card h3 { margin:0 0 10px; font-size:16px; }
  .card .row { display:flex; justify-content:space-between; font-size:13px; padding:3px 0; color:var(--muted); }
  .card .row b { color:var(--text); font-weight:600; }
  .bar { height:6px; border-radius:3px; background:var(--panel2); margin-top:12px; overflow:hidden; }
  .bar > span { display:block; height:100%; background:linear-gradient(90deg,#38bdf8,#6366f1); }
  .badge { display:inline-block; font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px; }
  .badge.pii { background:rgba(239,68,68,.15); color:#fca5a5; }
  .badge.debt { background:rgba(245,158,11,.15); color:#fcd34d; }
  .badge.health { background:rgba(148,163,184,.18); color:#cbd5e1; }
  table.tbl { width:100%; border-collapse:collapse; font-size:13px; }
  table.tbl th { text-align:left; color:var(--muted); font-weight:600; padding:8px 10px; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); }
  table.tbl td { padding:8px 10px; border-bottom:1px solid var(--line); }
  tr.trow { cursor:pointer; }
  tr.trow:hover { background:var(--panel); }
  .kind { font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; color:#fff; }
  .num { text-align:right; font-variant-numeric:tabular-nums; }
  .detail td { background:var(--panel); }
  .cols { width:100%; border-collapse:collapse; font-size:12px; margin:6px 0; }
  .cols th { color:var(--muted); text-align:left; padding:4px 8px; font-weight:600; }
  .cols td { padding:4px 8px; border-bottom:1px solid var(--line); }
  .pk { color:#fcd34d; font-weight:700; }
  .rel { font-size:12px; color:var(--muted); margin-top:6px; }
  .rel .inf { color:var(--warn); }
  .sev { font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }
  .sev.high { background:rgba(239,68,68,.18); color:#fca5a5; }
  .sev.medium { background:rgba(245,158,11,.18); color:#fcd34d; }
  .sev.low { background:rgba(148,163,184,.18); color:#cbd5e1; }
  #pathResult { margin-top:4px; font-size:13px; }
  #pathResult .step { padding:3px 0; }
  #pathResult .inf { color:var(--warn); }
  .muted { color:var(--muted); }
  details > summary { cursor:pointer; color:var(--muted); font-size:13px; margin-bottom:10px; }
  footer { color:var(--muted); font-size:12px; padding:24px 32px; border-top:1px solid var(--line); }
</style>
</head>
<body>
<header>
  <h1>Data catalog</h1>
  <p>Generated by schema-scout · read-only · nothing left this machine</p>
</header>
<div class="wrap">
  <div class="kpis" id="kpis"></div>

  <h2>Where to focus <span class="hint">— domains ranked; sort by what matters, click a card to filter the tables below</span></h2>
  <div class="controls">
    <label class="muted" style="font-size:13px">Sort domains by</label>
    <select id="domainSort">
      <option value="rows">Data volume (rows)</option>
      <option value="pii">PII exposure</option>
      <option value="tables">Number of tables</option>
      <option value="inferred_fks">Modelling debt (undeclared FKs)</option>
      <option value="queries">Usage (queries)</option>
    </select>
  </div>
  <div class="grid" id="domains"></div>

  <h2>Find a join path <span class="hint">— how do two tables connect?</span></h2>
  <div class="controls">
    <select id="pathFrom"></select>
    <span class="muted">→</span>
    <select id="pathTo"></select>
    <button id="pathBtn">Find path</button>
  </div>
  <div id="pathResult" class="muted"></div>

  <h2>Health <span class="hint">— structural &amp; data-quality issues to review</span></h2>
  <details id="healthBox">
    <summary id="healthSummary"></summary>
    <table class="tbl">
      <thead><tr><th>Severity</th><th>Table</th><th>Domain</th><th>Issue</th></tr></thead>
      <tbody id="health"></tbody>
    </table>
  </details>

  <h2>Tables <span class="hint">— search, filter, click a row for columns &amp; relationships</span></h2>
  <div class="controls">
    <input type="search" id="search" placeholder="Search tables or columns…">
    <select id="kindFilter">
      <option value="">All kinds</option>
      <option value="fact">Fact</option>
      <option value="dimension">Dimension</option>
      <option value="bridge">Bridge</option>
      <option value="reference">Reference</option>
      <option value="unknown">Unknown</option>
    </select>
    <select id="domainFilter"><option value="">All domains</option></select>
    <label class="muted" style="font-size:13px"><input type="checkbox" id="piiOnly"> PII only</label>
    <span class="muted" id="tableCount" style="margin-left:auto"></span>
  </div>
  <table class="tbl">
    <thead><tr id="tableHead"></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<footer>schema-scout · classification, inferred relationships and health flags are heuristics for a human to confirm.</footer>

<script>
const DATA = __DATA__;
const DOMAINS = __DOMAINS__;
const FINDINGS = __FINDINGS__;
const KIND_COLORS = {fact:"#3b82f6",dimension:"#10b981",bridge:"#a855f7",reference:"#64748b",unknown:"#9ca3af"};
const fmt = n => (n==null?"":Number(n).toLocaleString());
let activeDomain = "";

const hasUsage = DATA.tables.some(t => (t.query_count||0) > 0);
const domainHealth = {};
FINDINGS.forEach(f => { domainHealth[f.domain] = (domainHealth[f.domain]||0)+1; });

function totalRows(){ return DATA.tables.reduce((a,t)=>a+(t.row_count||0),0); }
function piiTotal(){ return DATA.tables.reduce((a,t)=>a+t.columns.filter(c=>c.pii).length,0); }
function inferredTotal(){ return DATA.tables.reduce((a,t)=>a+t.foreign_keys.filter(f=>f.inferred).length,0); }
function highFlags(){ return FINDINGS.filter(f=>f.severity==='high').length; }

function renderKpis(){
  const tiles = [
    {n:DATA.table_count, l:"Tables"},
    {n:fmt(totalRows()), l:"Total rows"},
    {n:DATA.relationship_count, l:"Relationships", sub:inferredTotal()+" inferred"},
    {n:piiTotal(), l:"PII columns"},
    {n:FINDINGS.length, l:"Health flags", sub:highFlags()+" high"},
    {n:DOMAINS.length, l:"Domains"},
  ];
  document.getElementById("kpis").innerHTML = tiles.map(t=>
    `<div class="kpi"><div class="n">${t.n}</div><div class="l">${t.l}</div>${t.sub?`<div class="sub">${t.sub}</div>`:""}</div>`
  ).join("");
}

function renderDomains(){
  const key = document.getElementById("domainSort").value;
  const sorted = [...DOMAINS].sort((a,b)=>(b[key]||0)-(a[key]||0));
  const max = Math.max(1, ...sorted.map(d=>d[key]||0));
  document.getElementById("domains").innerHTML = sorted.map(d=>{
    const pct = Math.round(100*((d[key]||0)/max));
    const badges = [];
    if(d.pii>0) badges.push(`<span class="badge pii">${d.pii} PII</span>`);
    if(d.inferred_fks>0) badges.push(`<span class="badge debt">${d.inferred_fks} undeclared FK</span>`);
    const h = domainHealth[d.name]||0;
    if(h>0) badges.push(`<span class="badge health">${h} health</span>`);
    const usageRow = hasUsage ? `<div class="row"><span>Queries</span><b>${fmt(d.queries)}</b></div>` : "";
    return `<div class="card ${activeDomain===d.name?'active':''}" data-d="${d.name}">
      <h3>${d.name} ${badges.join(" ")}</h3>
      <div class="row"><span>Tables</span><b>${d.tables}</b></div>
      <div class="row"><span>Rows</span><b>${fmt(d.rows)}</b></div>
      <div class="row"><span>Relationships</span><b>${d.declared_fks+d.inferred_fks}</b></div>
      ${usageRow}
      <div class="row"><span>Columns</span><b>${fmt(d.columns)}</b></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    </div>`;
  }).join("");
  document.querySelectorAll("#domains .card").forEach(el=>{
    el.onclick = ()=>{
      const d = el.getAttribute("data-d");
      activeDomain = (activeDomain===d) ? "" : d;
      document.getElementById("domainFilter").value = activeDomain;
      renderDomains(); renderRows();
    };
  });
}

// --- join path (BFS over the relationship graph) ---
function buildAdjacency(){
  const adj = {};
  DATA.tables.forEach(t => { adj[t.qualified_name] = adj[t.qualified_name] || []; });
  DATA.tables.forEach(t => t.foreign_keys.forEach(f => {
    const a = f.from.split('.').slice(0,2).join('.');
    const b = f.to.split('.').slice(0,2).join('.');
    (adj[a] = adj[a] || []).push({to:b, fk:f});
    (adj[b] = adj[b] || []).push({to:a, fk:f});
  }));
  return adj;
}
function findPath(src, dst){
  if(src===dst) return [];
  const adj = buildAdjacency();
  if(!(src in adj) || !(dst in adj)) return null;
  const prev = {}; prev[src] = null; const q = [src];
  while(q.length){
    const cur = q.shift();
    if(cur===dst) break;
    (adj[cur]||[]).forEach(e => { if(!(e.to in prev)){ prev[e.to] = [cur, e.fk]; q.push(e.to); } });
  }
  if(!(dst in prev)) return null;
  const steps = []; let node = dst;
  while(prev[node]){ const [cur, fk] = prev[node]; steps.push({from:cur, to:node, fk}); node = cur; }
  steps.reverse(); return steps;
}
function renderPath(){
  const src = document.getElementById("pathFrom").value;
  const dst = document.getElementById("pathTo").value;
  const steps = findPath(src, dst);
  const box = document.getElementById("pathResult");
  if(steps===null){ box.innerHTML = `<span class="muted">No join path between <b>${src}</b> and <b>${dst}</b>.</span>`; return; }
  if(steps.length===0){ box.innerHTML = `<span class="muted">Same table.</span>`; return; }
  box.innerHTML = `<div class="muted">${steps.length} join(s):</div>` + steps.map(s =>
    `<div class="step">${s.from} → ${s.to} &nbsp; <span class="muted">ON ${s.fk.from} = ${s.fk.to}</span>` +
    (s.fk.inferred?` <span class="inf">(inferred)</span>`:``) + `</div>`
  ).join("");
}

function renderHealth(){
  const sevRank = {high:0, medium:1, low:2};
  const sorted = [...FINDINGS].sort((a,b)=>sevRank[a.severity]-sevRank[b.severity]);
  const counts = {high:0, medium:0, low:0};
  FINDINGS.forEach(f=>counts[f.severity]++);
  document.getElementById("healthSummary").textContent =
    `${FINDINGS.length} issues (${counts.high} high, ${counts.medium} medium, ${counts.low} low) — click to expand`;
  document.getElementById("health").innerHTML = sorted.map(f =>
    `<tr><td><span class="sev ${f.severity}">${f.severity}</span></td>` +
    `<td><b>${f.table}</b></td><td class="muted">${f.domain}</td><td>${f.message}</td></tr>`
  ).join("") || `<tr><td colspan="4" class="muted">No issues found.</td></tr>`;
}

function kindBadge(k){ return `<span class="kind" style="background:${KIND_COLORS[k]||'#9ca3af'}">${k}</span>`; }

function rowMatches(t){
  const q = document.getElementById("search").value.toLowerCase().trim();
  const kind = document.getElementById("kindFilter").value;
  const dom = document.getElementById("domainFilter").value;
  const piiOnly = document.getElementById("piiOnly").checked;
  if(kind && t.kind!==kind) return false;
  if(dom && (t.subject_area||"Ungrouped")!==dom) return false;
  if(piiOnly && !t.columns.some(c=>c.pii)) return false;
  if(q){
    const inName = t.qualified_name.toLowerCase().includes(q);
    const inCol = t.columns.some(c=>c.name.toLowerCase().includes(q));
    if(!inName && !inCol) return false;
  }
  return true;
}

function colTable(t){
  const head = `<tr><th>Column</th><th>Type</th><th>Null%</th><th>Distinct</th><th>PII</th><th>Examples / range</th></tr>`;
  const rows = t.columns.map(c=>{
    const ex = (c.sample_values&&c.sample_values.length) ? c.sample_values.slice(0,3).join(", ")
             : (c.min!=null ? `${c.min} … ${c.max}` : "");
    return `<tr>
      <td class="${c.primary_key?'pk':''}">${c.name}${c.primary_key?' 🔑':''}</td>
      <td class="muted">${c.data_type}</td>
      <td class="num">${c.null_pct==null?'':c.null_pct+'%'}</td>
      <td class="num">${fmt(c.distinct_count)}</td>
      <td>${c.pii?`<span class="badge pii">${c.pii}</span>`:''}</td>
      <td class="muted">${ex}</td>
    </tr>`;
  }).join("");
  let rel = "";
  if(t.foreign_keys.length){
    rel = `<div class="rel">Relationships: ` + t.foreign_keys.map(f=>
      `${f.from.split('.').pop()} → ${f.to}` + (f.inferred?` <span class="inf">(inferred ${Math.round(f.confidence*100)}%)</span>`:` (declared)`)
    ).join(" · ") + `</div>`;
  }
  return `<table class="cols">${head}${rows}</table>${rel}`;
}

function renderHead(){
  const cols = ["Table","Domain","Kind","Rows","Cols","FKs"];
  if(hasUsage) cols.push("Queries");
  cols.push("PII");
  const numCols = new Set(["Rows","Cols","FKs","Queries","PII"]);
  document.getElementById("tableHead").innerHTML =
    cols.map(c=>`<th class="${numCols.has(c)?'num':''}">${c}</th>`).join("");
  return cols.length;
}

function renderRows(){
  const ncol = renderHead();
  const tb = document.getElementById("rows");
  const list = DATA.tables.filter(rowMatches).sort((a,b)=>b.row_count-a.row_count);
  document.getElementById("tableCount").textContent = `${list.length} of ${DATA.table_count} tables`;
  tb.innerHTML = list.map((t,i)=>{
    const pii = t.columns.filter(c=>c.pii).length;
    const usageCell = hasUsage ? `<td class="num">${fmt(t.query_count)}</td>` : "";
    return `<tr class="trow" data-i="${i}">
      <td><b>${t.qualified_name}</b></td>
      <td class="muted">${t.subject_area||'Ungrouped'}</td>
      <td>${kindBadge(t.kind)}</td>
      <td class="num">${fmt(t.row_count)}</td>
      <td class="num">${t.columns.length}</td>
      <td class="num">${t.foreign_keys.length}</td>
      ${usageCell}
      <td class="num">${pii?`<span class="badge pii">${pii}</span>`:''}</td>
    </tr>
    <tr class="detail" id="d${i}" style="display:none"><td colspan="${ncol}">${colTable(t)}</td></tr>`;
  }).join("");
  tb.querySelectorAll("tr.trow").forEach(r=>{
    r.onclick = ()=>{ const d=document.getElementById("d"+r.getAttribute("data-i")); d.style.display = d.style.display==="none"?"":"none"; };
  });
}

function init(){
  const tableNames = DATA.tables.map(t=>t.qualified_name).sort();
  const opts = tableNames.map(n=>`<option value="${n}">${n}</option>`).join("");
  document.getElementById("pathFrom").innerHTML = opts;
  document.getElementById("pathTo").innerHTML = opts;
  if(tableNames.length>1) document.getElementById("pathTo").selectedIndex = 1;
  document.getElementById("pathBtn").onclick = renderPath;

  document.getElementById("domainFilter").innerHTML =
    `<option value="">All domains</option>` + DOMAINS.map(d=>`<option value="${d.name}">${d.name}</option>`).join("");

  renderKpis(); renderDomains(); renderHealth(); renderRows();
  document.getElementById("domainSort").onchange = renderDomains;
  ["search","kindFilter","piiOnly"].forEach(id=>document.getElementById(id).oninput = renderRows);
  document.getElementById("domainFilter").onchange = ()=>{ activeDomain=document.getElementById("domainFilter").value; renderDomains(); renderRows(); };
}
init();
</script>
</body>
</html>
"""


def render_html(catalog: Catalog, findings: list | None = None) -> str:
    if findings is None:
        findings = lint.lint_catalog(catalog)
    data = render.to_dict(catalog)
    doms = domains.summarize_domains(catalog)
    data_json = json.dumps(data, default=str).replace("</", "<\\/")
    doms_json = json.dumps(doms, default=str).replace("</", "<\\/")
    find_json = json.dumps(findings, default=str).replace("</", "<\\/")
    return (
        _TEMPLATE.replace("__DATA__", data_json)
        .replace("__DOMAINS__", doms_json)
        .replace("__FINDINGS__", find_json)
    )
