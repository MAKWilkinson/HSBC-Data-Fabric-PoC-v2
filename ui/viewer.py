# ---------------------------------------------------------------------------
# 4 · Mapping viewer — static HTML UI  (viewer.py)
# ---------------------------------------------------------------------------

"""
Generate a single-file, zero-dependency HTML viewer for stored FileMappings.

Design:
- collect_mappings() walks MAPPINGS_DIR for *.mapping.json (the files written
  by persistence.store_mapping) and returns them as plain dicts.
- build_viewer_html() embeds those dicts as JSON inside an HTML template.
  All rendering (list, detail table, Mermaid lineage diagram) happens
  client-side in the browser; Mermaid is loaded from a CDN.
- write_viewer() ties the two together and writes viewer.html.

No server, no build step: open the output file in a browser. Re-run after a
pipeline run to refresh. Deterministic and LLM-free, same philosophy as the
persistence layer.

Usage:
    python viewer.py                      # reads persistence.MAPPINGS_DIR
    python viewer.py path/to/mappings     # explicit input dir
    python viewer.py path/to/mappings out.html
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)

_APP_ROOT = Path(__file__).resolve().parent.parent   # appv2/
sys.path.insert(0, str(_APP_ROOT))                   # so `import persistence` works from ui/

try:
    import persistence
    _DEFAULT_MAPPINGS_DIR = persistence.MAPPINGS_DIR
except ImportError:  # standalone use outside the pipeline
    _DEFAULT_MAPPINGS_DIR = _APP_ROOT / "mappings"

_DEFAULT_OUTPUT = Path(__file__).resolve().parent / "viewer.html"


# ---------------------------------------------------------------------------
# 1 · Collect stored mappings
# ---------------------------------------------------------------------------


def collect_mappings(mappings_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load every *.mapping.json under mappings_dir into a list of dicts.

    Each record gains a "_file" key (path relative to mappings_dir) so the
    UI can show provenance. Unreadable files are skipped with a warning —
    one corrupt record must not take down the whole viewer.
    """
    root = Path(mappings_dir or _DEFAULT_MAPPINGS_DIR)
    records: list[dict[str, Any]] = []

    if not root.is_dir():
        logger.warning("Mappings directory %s does not exist", root)
        return records

    for path in sorted(root.rglob("*.mapping.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Skipping unreadable mapping %s: %s", path, error)
            continue
        if not isinstance(record, dict):
            logger.warning("Skipping non-object mapping %s", path)
            continue
        record["_file"] = str(path.relative_to(root))
        records.append(record)

    logger.info("Collected %d mappings from %s", len(records), root)
    return records


# ---------------------------------------------------------------------------
# 2 · HTML template
# ---------------------------------------------------------------------------

# The template is plain HTML/CSS/JS with a single injection point,
# __MAPPING_DATA__. No str.format / f-strings, so the CSS/JS braces
# need no escaping.

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapping Viewer — data lineage</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<style>
  :root {
    --ink: #16212e;          /* sidebar / headings */
    --ink-2: #22303f;
    --paper: #f5f6f8;        /* app background */
    --card: #ffffff;
    --line: #e2e6ea;
    --text: #2a3540;
    --muted: #6b7885;
    --accent: #0e7c86;       /* teal — selection & focus */
    --exact: #1a7f4b;
    --renamed: #2563ae;
    --semantic: #b06a12;
    --merge: #7048b0;
    --transformed: #0e7c86;
    --unmapped: #8a94a0;
    --low: #c0392b;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: "IBM Plex Sans", system-ui, sans-serif;
    background: var(--paper); color: var(--text);
    display: flex; overflow: hidden;
  }
  code, .mono { font-family: "IBM Plex Mono", ui-monospace, monospace; }

  /* ---------- Sidebar ---------- */
  #sidebar {
    width: 340px; min-width: 260px; height: 100vh; overflow-y: auto;
    background: var(--ink); color: #dfe6ec; flex-shrink: 0;
    display: flex; flex-direction: column;
  }
  #sidebar header { padding: 18px 18px 12px; }
  #sidebar h1 { font-size: 15px; font-weight: 600; margin: 0 0 2px; color: #fff; letter-spacing: .02em; }
  #sidebar .sub { font-size: 12px; color: #93a1af; }
  #search {
    margin: 10px 14px; padding: 8px 10px; width: calc(100% - 28px);
    background: var(--ink-2); border: 1px solid #33404e; border-radius: 6px;
    color: #eef2f5; font: inherit; font-size: 13px;
  }
  #search:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .group-label {
    padding: 12px 18px 4px; font-size: 11px; letter-spacing: .08em;
    text-transform: uppercase; color: #8fa0af; font-weight: 600;
  }
  .group-label .mono { font-size: 11px; }
  .item {
    display: block; width: 100%; text-align: left; cursor: pointer;
    padding: 10px 18px; border: 0; background: none; color: #dfe6ec;
    font: inherit; border-left: 3px solid transparent;
  }
  .item:hover { background: var(--ink-2); }
  .item.active { background: var(--ink-2); border-left-color: var(--accent); }
  .item .out { font-size: 13px; font-weight: 600; color: #fff; }
  .item .from { font-size: 12px; color: #93a1af; margin-top: 2px; }
  .item .meta { display: flex; gap: 8px; align-items: center; margin-top: 5px; }
  .pill {
    font-size: 10.5px; font-weight: 600; padding: 1px 7px; border-radius: 999px;
    letter-spacing: .03em;
  }
  .pill.rel   { background: rgba(26,127,75,.25); color: #7fd8a8; }
  .pill.unrel { background: rgba(192,57,43,.22); color: #f0a49a; }
  .conf-mini { flex: 1; height: 4px; background: #33404e; border-radius: 2px; overflow: hidden; }
  .conf-mini > div { height: 100%; background: var(--accent); }
  #empty-side { padding: 18px; color: #93a1af; font-size: 13px; }

  /* ---------- Main ---------- */
  #main { flex: 1; min-width: 0; height: 100vh; overflow-y: auto; padding: 26px 32px 60px; }
  #detail { max-width: 1100px; margin: 0 auto; }

  .flowline { font-size: 12.5px; color: var(--muted); margin-bottom: 4px; }
  .flowline .sys { font-weight: 600; color: var(--text); }
  .flowline .arrow { color: var(--accent); font-weight: 600; }
  h2.title { font-size: 21px; margin: 0 0 2px; color: var(--ink); }
  h2.title .mono { font-size: 18px; }
  .subtitle { font-size: 13px; color: var(--muted); margin-bottom: 16px; }

  .nav-row { display: flex; align-items: center; gap: 10px; margin: 14px 0 18px; }
  .nav-row button {
    font: inherit; font-size: 13px; padding: 6px 14px; cursor: pointer;
    background: var(--card); border: 1px solid var(--line); border-radius: 6px; color: var(--text);
  }
  .nav-row button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .nav-row button:disabled { opacity: .4; cursor: default; }
  .nav-row .count { font-size: 12.5px; color: var(--muted); margin-left: auto; }
  .kbd-hint { font-size: 11.5px; color: var(--muted); }

  .card {
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 18px 20px; margin-bottom: 18px; overflow-x: auto;
  }
  .card h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); }

  .relatedness { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .conf-bar { width: 180px; height: 8px; background: #edf0f3; border-radius: 4px; overflow: hidden; }
  .conf-bar > div { height: 100%; }
  .reasoning { font-size: 13.5px; color: var(--text); margin-top: 10px; line-height: 1.5; }

  .prov { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .prov .box { font-size: 12.5px; }
  .prov .lbl { text-transform: uppercase; font-size: 10.5px; letter-spacing: .07em; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
  .prov .mono { font-size: 12px; word-break: break-all; color: var(--text); }
  .prov .fp { color: var(--muted); }

  /* tabs */
  .tabs { display: flex; gap: 6px; margin-bottom: 14px; }
  .tabs button {
    font: inherit; font-size: 13px; font-weight: 500; padding: 6px 16px; cursor: pointer;
    border: 1px solid var(--line); background: var(--card); border-radius: 999px; color: var(--muted);
  }
  .tabs button.active { background: var(--ink); color: #fff; border-color: var(--ink); }

  /* table */
  #tab-body { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
  th:nth-child(1) { width: 22%; }   /* outbound field */
  th:nth-child(2) { width: 26%; }   /* sources */
  th:nth-child(3) { width: 12%; }   /* transformation */
  th:nth-child(4) { width: 10%; }   /* confidence */
  th:nth-child(5) { width: 30%; }   /* reasoning */
  th {
    text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
    color: var(--muted); padding: 8px 10px; border-bottom: 2px solid var(--line);
  }
  td { padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  td, td .mono { overflow-wrap: anywhere; word-break: break-word; }
  tr:last-child td { border-bottom: 0; }
  td .mono { font-size: 12px; }
  .src-chip {
    display: inline-block; background: #eef1f4; border-radius: 4px;
    padding: 1px 6px; margin: 1px 3px 1px 0; font-size: 11.5px;
    white-space: normal; overflow-wrap: anywhere; word-break: break-word;
  }
  .badge {
    display: inline-block; font-size: 10.5px; font-weight: 700; letter-spacing: .04em;
    padding: 2px 8px; border-radius: 4px; color: #fff;
  }
  .badge.EXACT       { background: var(--exact); }
  .badge.RENAMED     { background: var(--renamed); }
  .badge.SEMANTIC    { background: var(--semantic); }
  .badge.MERGE       { background: var(--merge); }
  .badge.TRANSFORMED { background: var(--transformed); }
  .badge.UNMAPPED    { background: var(--unmapped); }
  td.conf-cell { min-width: 90px; }
  .conf-cell .num { font-size: 12px; color: var(--muted); }
  .conf-cell .bar { height: 6px; background: #edf0f3; border-radius: 3px; overflow: hidden; margin-top: 3px; }
  .conf-cell .bar > div { height: 100%; }
  td.reason { color: var(--muted); font-size: 12.5px; line-height: 1.45; }
  tr.low td { background: #fdf6f5; }

  /* diagram */
  #diagram-wrap { overflow-x: auto; }
  #diagram svg { max-width: none; }
  .diagram-controls { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; font-size: 12.5px; color: var(--muted); }
  .legend { display: flex; gap: 10px; flex-wrap: wrap; margin-left: auto; }
  .legend span { display: inline-flex; align-items: center; gap: 4px; }
  .legend i { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }

  #placeholder { text-align: center; color: var(--muted); margin-top: 18vh; }
  #placeholder h2 { color: var(--ink); font-weight: 600; }

  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (max-width: 900px) {
    body { flex-direction: column; }
    #sidebar { width: 100%; height: 40vh; }
    #main { height: auto; }
    .prov { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<nav id="sidebar" aria-label="Mappings">
  <header>
    <h1>Mapping viewer</h1>
    <div class="sub" id="side-count"></div>
  </header>
  <input id="search" type="search" placeholder="Filter by system, file, field…" aria-label="Filter mappings">
  <div id="list"></div>
</nav>

<main id="main">
  <div id="placeholder">
    <h2>Select a mapping</h2>
    <p>Choose a file pair on the left, or use ← → to step through them.</p>
  </div>
  <div id="detail" hidden></div>
</main>

<script>
const DATA = __MAPPING_DATA__;

/* ---------------- helpers ---------------- */
const $ = (sel, el=document) => el.querySelector(sel);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const brk = s => esc(s).replace(/([._])/g, "$1<wbr>");   // tidy wrap points in long field paths
const stem = name => String(name ?? "").replace(/\.[^.]+$/, "");
const TRANSFORM_COLORS = { EXACT:"#1a7f4b", RENAMED:"#2563ae", SEMANTIC:"#b06a12", MERGE:"#7048b0", TRANSFORMED:"#0e7c86", UNMAPPED:"#8a94a0" };
const THRESHOLD = 0.7;   // matches config confidence_threshold

const confColor = c => c >= 0.85 ? "var(--exact)" : c >= THRESHOLD ? "var(--semantic)" : "var(--low)";

const src = (rec, side) => (rec[side] || {}).source || {};
const label = rec => {
  const o = src(rec, "outbound_schema"), i = src(rec, "inbound_schema");
  return { out: stem(o.message_file_name), inn: stem(i.message_file_name),
           oProv: o.providing_system || "?", oCons: o.consuming_system || "none",
           iProv: i.providing_system || "?", iCons: i.consuming_system || "none" };
};

let filtered = DATA.map((_, i) => i);
let current = -1;
let activeTab = "table";
let dimLow = true;

/* ---------------- sidebar ---------------- */
function renderList() {
  const q = $("#search").value.trim().toLowerCase();
  filtered = DATA.map((_, i) => i).filter(i => {
    if (!q) return true;
    const r = DATA[i], l = label(r);
    const hay = [l.out, l.inn, l.oProv, l.oCons, l.iProv, r._file,
                 ...(r.mappings || []).flatMap(m => [m.outbound_field, ...(m.sources||[])])].join(" ").toLowerCase();
    return hay.includes(q);
  });

  // group by outbound provider → consumer
  const groups = new Map();
  for (const i of filtered) {
    const l = label(DATA[i]);
    const key = l.oProv + " → " + l.oCons;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(i);
  }

  const list = $("#list");
  list.innerHTML = "";
  if (!filtered.length) {
    list.innerHTML = '<div id="empty-side">No mappings match this filter.</div>';
  }
  for (const [key, idxs] of groups) {
    const g = document.createElement("div");
    g.innerHTML = '<div class="group-label mono">' + esc(key) + "</div>";
    for (const i of idxs) {
      const r = DATA[i], l = label(r);
      const conf = Number(r.relatedness_confidence || 0);
      const btn = document.createElement("button");
      btn.className = "item" + (i === current ? " active" : "");
      btn.setAttribute("data-idx", i);
      btn.innerHTML =
        '<div class="out mono">' + esc(l.out) + "</div>" +
        '<div class="from">from <span class="mono">' + esc(l.iProv) + " / " + esc(l.inn) + "</span></div>" +
        '<div class="meta">' +
          '<span class="pill ' + (r.related ? "rel\">related" : "unrel\">unrelated") + "</span>" +
          '<div class="conf-mini"><div style="width:' + (conf*100) + '%"></div></div>' +
          '<span style="font-size:11px;color:#93a1af">' + conf.toFixed(2) + "</span>" +
        "</div>";
      btn.onclick = () => select(i);
      g.appendChild(btn);
    }
    list.appendChild(g);
  }
  $("#side-count").textContent = filtered.length + " of " + DATA.length + " mappings";
}

/* ---------------- detail ---------------- */
function select(i) {
  current = i;
  renderList();
  renderDetail();
}

function navOffset(delta) {
  if (!filtered.length) return;
  const pos = filtered.indexOf(current);
  const next = pos === -1 ? 0 : Math.min(Math.max(pos + delta, 0), filtered.length - 1);
  select(filtered[next]);
}

function renderDetail() {
  const rec = DATA[current];
  $("#placeholder").hidden = !!rec;
  $("#detail").hidden = !rec;
  if (!rec) return;

  const l = label(rec);
  const conf = Number(rec.relatedness_confidence || 0);
  const pos = filtered.indexOf(current);
  const inS = src(rec, "inbound_schema"), outS = src(rec, "outbound_schema");
  const inFp = (rec.inbound_schema||{}).fingerprint || "—";
  const outFp = (rec.outbound_schema||{}).fingerprint || "—";
  const rows = rec.mappings || [];

  $("#detail").innerHTML =
    '<div class="flowline"><span class="sys">' + esc(l.iProv) + '</span> <span class="arrow">→</span> <span class="sys">' + esc(l.iCons) +
      '</span> <span class="arrow">→</span> <span class="sys">' + esc(l.oCons) + "</span></div>" +
    '<h2 class="title"><span class="mono">' + esc(l.out) + '</span> <span style="font-weight:400;color:var(--muted)">←</span> <span class="mono">' + esc(l.inn) + "</span></h2>" +
    '<div class="subtitle mono">' + esc(rec._file || "") + "</div>" +

    '<div class="nav-row">' +
      '<button id="prev"' + (pos <= 0 ? " disabled" : "") + ">← Previous</button>" +
      '<button id="next"' + (pos >= filtered.length - 1 ? " disabled" : "") + ">Next →</button>" +
      '<span class="kbd-hint">arrow keys work too</span>' +
      '<span class="count">' + (pos + 1) + " / " + filtered.length + "</span>" +
    "</div>" +

    '<div class="card"><h3>Relatedness</h3>' +
      '<div class="relatedness">' +
        '<span class="pill ' + (rec.related ? "rel\">related" : "unrel\">unrelated") + "</span>" +
        '<div class="conf-bar"><div style="width:' + (conf*100) + "%;background:" + confColor(conf) + '"></div></div>' +
        '<strong>' + conf.toFixed(2) + "</strong>" +
      "</div>" +
      '<div class="reasoning">' + esc(rec.relatedness_reasoning || "") + "</div>" +
    "</div>" +

    '<div class="card"><h3>Provenance</h3><div class="prov">' +
      '<div class="box"><div class="lbl">Inbound</div><div class="mono">' + esc(inS.path || "") + '</div><div class="mono fp">fingerprint ' + esc(inFp) + "</div></div>" +
      '<div class="box"><div class="lbl">Outbound</div><div class="mono">' + esc(outS.path || "") + '</div><div class="mono fp">fingerprint ' + esc(outFp) + "</div></div>" +
    "</div></div>" +

    '<div class="tabs">' +
      '<button id="tab-table" class="' + (activeTab === "table" ? "active" : "") + '">Field mappings (' + rows.length + ")</button>" +
      '<button id="tab-diagram" class="' + (activeTab === "diagram" ? "active" : "") + '">Lineage diagram</button>' +
    "</div>" +
    '<div class="card" id="tab-body"></div>';

  $("#prev").onclick = () => navOffset(-1);
  $("#next").onclick = () => navOffset(1);
  $("#tab-table").onclick = () => { activeTab = "table"; renderDetail(); };
  $("#tab-diagram").onclick = () => { activeTab = "diagram"; renderDetail(); };

  if (activeTab === "table") renderTable(rec); else renderDiagram(rec);
}

function renderTable(rec) {
  const rows = rec.mappings || [];
  let html = "<table><thead><tr><th>Outbound field</th><th>Sources</th><th>Transformation</th><th>Confidence</th><th>Reasoning</th></tr></thead><tbody>";
  for (const m of rows) {
    const c = Number(m.confidence || 0);
    html += '<tr class="' + (c < THRESHOLD ? "low" : "") + '">' +
      '<td class="mono">' + esc(m.outbound_field) + "</td>" +
      "<td>" + (m.sources||[]).map(s => '<span class="src-chip mono">' + esc(s) + "</span>").join("") + "</td>" +
      '<td><span class="badge ' + esc(m.transformation || "UNMAPPED") + '">' + esc(m.transformation || "UNMAPPED") + "</span></td>" +
      '<td class="conf-cell"><span class="num">' + c.toFixed(2) + '</span><div class="bar"><div style="width:' + (c*100) + "%;background:" + confColor(c) + '"></div></div></td>' +
      '<td class="reason">' + esc(m.reasoning || "") + "</td></tr>";
  }
  html += "</tbody></table>";
  $("#tab-body").innerHTML = html;
}

/* ---------------- Mermaid diagram ---------------- */
function buildMermaid(rec) {
  const l = label(rec);
  const rows = rec.mappings || [];

  // stable sanitized node ids: counter-based, real path in the quoted label
  const inIds = new Map(), outIds = new Map();
  const idFor = (map, prefix, name) => {
    if (!map.has(name)) map.set(name, prefix + map.size);
    return map.get(name);
  };
  for (const m of rows) {
    idFor(outIds, "o", m.outbound_field);
    for (const s of (m.sources || [])) idFor(inIds, "i", s);
  }

  const q = s => '"' + String(s).replace(/"/g, "'") + '"';
  const lines = ["flowchart LR"];
  lines.push('subgraph IN[' + q(l.iProv + " → " + l.iCons + ": " + l.inn) + "]");
  for (const [name, id] of inIds) lines.push("  " + id + "[" + q(name) + "]");
  lines.push("end");
  lines.push('subgraph OUT[' + q(l.oProv + " → " + l.oCons + ": " + l.out) + "]");
  for (const [name, id] of outIds) lines.push("  " + id + "[" + q(name) + "]");
  lines.push("end");

  // edges, remembering their order for linkStyle
  const edgeStyles = [];
  let edgeIdx = 0;
  for (const m of rows) {
    const c = Number(m.confidence || 0);
    const dashed = dimLow && c < THRESHOLD;
    const lbl = q((m.transformation || "?") + " " + c.toFixed(2));
    for (const s of (m.sources || [])) {
      lines.push(inIds.get(s) + (dashed ? " -. " + lbl + " .-> " : " -- " + lbl + " --> ") + outIds.get(m.outbound_field));
      edgeStyles.push("linkStyle " + edgeIdx + " stroke:" + (TRANSFORM_COLORS[m.transformation] || "#8a94a0") +
                      ",stroke-width:2px" + (dashed ? ",opacity:0.45" : ""));
      edgeIdx++;
    }
  }
  // unmapped outbound fields render as standalone dashed nodes
  lines.push("classDef unmapped fill:#f0f2f4,stroke:#8a94a0,stroke-dasharray:4 3,color:#6b7885");
  const unmapped = rows.filter(m => !(m.sources||[]).length).map(m => outIds.get(m.outbound_field));
  if (unmapped.length) lines.push("class " + unmapped.join(",") + " unmapped");

  return lines.concat(edgeStyles).join("\n");
}

let renderSeq = 0;
async function renderDiagram(rec) {
  const body = $("#tab-body");
  const legend = Object.entries(TRANSFORM_COLORS)
    .map(([k, v]) => "<span><i style=\"background:" + v + "\"></i>" + k + "</span>").join("");
  body.innerHTML =
    '<div class="diagram-controls">' +
      '<label><input type="checkbox" id="dim-low"' + (dimLow ? " checked" : "") + "> dash edges below " + THRESHOLD + "</label>" +
      '<div class="legend">' + legend + "</div>" +
    "</div>" +
    '<div id="diagram-wrap"><div id="diagram">Rendering…</div></div>';
  $("#dim-low").onchange = e => { dimLow = e.target.checked; renderDiagram(rec); };

  const seq = ++renderSeq;
  try {
    const { svg } = await mermaid.render("m" + seq, buildMermaid(rec));
    if (seq === renderSeq) $("#diagram").innerHTML = svg;
  } catch (err) {
    if (seq === renderSeq) $("#diagram").innerHTML =
      '<p style="color:var(--low)">Diagram failed to render: ' + esc(err.message || err) + "</p>";
  }
}

/* ---------------- boot ---------------- */
mermaid.initialize({ startOnLoad: false, theme: "neutral", flowchart: { curve: "basis" } });
$("#search").addEventListener("input", renderList);
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "ArrowLeft") navOffset(-1);
  if (e.key === "ArrowRight") navOffset(1);
});
renderList();
if (DATA.length) select(filtered[0]);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 3 · Build & write
# ---------------------------------------------------------------------------


def build_viewer_html(records: list[dict[str, Any]]) -> str:
    """Embed mapping records into the HTML template and return the page."""
    # </script> inside a JSON string would end the script block early
    payload = json.dumps(records, indent=None).replace("</", "<\\/")
    return _TEMPLATE.replace("__MAPPING_DATA__", payload)


def write_viewer(
    mappings_dir: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Collect mappings, render the viewer, write it to disk. Returns the path."""
    records = collect_mappings(mappings_dir)
    target = Path(output_path or _DEFAULT_OUTPUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_viewer_html(records), encoding="utf-8")
    logger.info("Wrote viewer with %d mappings to %s", len(records), target)
    return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    path = write_viewer(in_dir, out_file)
    print(f"Viewer written to {path} — open it in a browser.")