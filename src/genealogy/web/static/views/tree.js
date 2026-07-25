import { api } from "../api.js";
import { esc, pickPerson, showError } from "../ui.js";
import { renderOutlineHtml, renderDirectLineHtml, DATE_MODES, DEFAULT_DATE_MODE } from "./reportViews.js";

function buildHierarchy(rootId, nodesById, edges, mode, seen) {
  if (seen.has(rootId)) return null; // guard against pedigree collapse (e.g. cousin marriages)
  seen.add(rootId);
  const node = nodesById[rootId];
  if (!node) return null;

  const spouseNames = edges
    .filter((e) => e.type === "spouse" && (e.from === rootId || e.to === rootId))
    .map((e) => nodesById[e.from === rootId ? e.to : e.from]?.name)
    .filter(Boolean);

  const childIds =
    mode === "ancestors"
      ? edges.filter((e) => e.type === "parent" && e.to === rootId).map((e) => e.from)
      : edges.filter((e) => e.type === "parent" && e.from === rootId).map((e) => e.to);

  return {
    ...node,
    spouseNames,
    children: childIds
      .map((cid) => buildHierarchy(cid, nodesById, edges, mode, seen))
      .filter(Boolean),
  };
}

function hashFor(rootId, { direction, generations, view, targetId }) {
  const params = new URLSearchParams({ direction, generations: String(generations), view });
  if (view === "direct" && targetId) params.set("target", String(targetId));
  return `#/tree/${rootId}?${params}`;
}

export async function renderTree(app, rootId, opts = {}) {
  const direction = opts.direction === "descendants" ? "descendants" : "ancestors";
  const generations = opts.generations || 5;
  const view = ["outline", "direct"].includes(opts.view) ? opts.view : "chart";
  const targetId = opts.targetId || null;

  document.title = "Genealogy";

  const container = document.createElement("div");
  container.innerHTML = `
    <div class="card">
      <div class="tree-controls no-print">
        <div class="view-tabs">
          <button id="mode-chart" class="${view === "chart" ? "primary" : ""}">Chart</button>
          <button id="mode-outline" class="${view === "outline" ? "primary" : ""}">Outline Descendants</button>
          <button id="mode-direct" class="${view === "direct" ? "primary" : ""}">Direct Line</button>
        </div>
        <a id="view-detail-link" href="#/person/${rootId}">View person details &rarr;</a>
      </div>
      <div id="mode-body"></div>
    </div>
  `;
  app.appendChild(container);

  container.querySelector("#mode-chart").addEventListener("click", () => {
    location.hash = hashFor(rootId, { direction, generations, view: "chart" });
  });
  container.querySelector("#mode-outline").addEventListener("click", () => {
    location.hash = hashFor(rootId, { direction, generations, view: "outline" });
  });
  container.querySelector("#mode-direct").addEventListener("click", () => {
    location.hash = hashFor(rootId, { direction, generations, view: "direct", targetId });
  });

  const body = container.querySelector("#mode-body");

  if (view === "chart") {
    await renderChart(body, rootId, direction, generations);
  } else if (view === "outline") {
    await renderOutline(body, rootId);
  } else {
    await renderDirectLine(body, rootId, targetId);
  }
}

async function renderChart(body, rootId, direction, generations) {
  body.innerHTML = `
    <div class="tree-controls no-print">
      <strong>Pedigree</strong>
      <button id="dir-ancestors" class="${direction === "ancestors" ? "primary" : ""}">Ancestors</button>
      <button id="dir-descendants" class="${direction === "descendants" ? "primary" : ""}">Descendants</button>
      <label class="muted">Generations
        <select id="gen-select">
          ${[2, 3, 4, 5, 6, 7, 8].map((g) => `<option value="${g}" ${g === generations ? "selected" : ""}>${g}</option>`).join("")}
        </select>
      </label>
    </div>
    <svg id="tree-svg"></svg>
  `;

  body.querySelector("#dir-ancestors").addEventListener("click", () => {
    location.hash = hashFor(rootId, { direction: "ancestors", generations, view: "chart" });
  });
  body.querySelector("#dir-descendants").addEventListener("click", () => {
    location.hash = hashFor(rootId, { direction: "descendants", generations, view: "chart" });
  });
  body.querySelector("#gen-select").addEventListener("change", (e) => {
    location.hash = hashFor(rootId, { direction, generations: Number(e.target.value), view: "chart" });
  });

  const data = await api.getTree(rootId, direction, generations);
  const nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  const hierarchyData = buildHierarchy(rootId, nodesById, data.edges, direction, new Set());

  drawTree(body.querySelector("#tree-svg"), hierarchyData, direction);
}

function reportHeader({ title, subtitle, onPrint, dateMode, onDateModeChange }) {
  const header = document.createElement("div");
  header.innerHTML = `
    <div class="report-toolbar no-print">
      <label class="muted">Dates
        <select id="report-date-mode">
          ${DATE_MODES.map((m) => `<option value="${m.value}" ${m.value === dateMode ? "selected" : ""}>${esc(m.label)}</option>`).join("")}
        </select>
      </label>
      <button id="report-print-btn">Print</button>
    </div>
    <h2 class="report-title">${esc(title)}</h2>
    ${subtitle ? `<p class="muted report-subtitle">${esc(subtitle)}</p>` : ""}
  `;
  header.querySelector("#report-print-btn").addEventListener("click", onPrint);
  header.querySelector("#report-date-mode").addEventListener("change", (e) => onDateModeChange(e.target.value));
  return header;
}

async function renderOutline(body, rootId) {
  body.innerHTML = "";
  let data;
  try {
    data = await api.getDescendantsOutline(rootId);
  } catch (err) {
    showError(body, err);
    return;
  }

  const asOf = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long" });
  const birthYear = data.root.birth_year ? ` ${data.root.birth_year}` : "";
  document.title = `Outline Descendants of ${data.root.name}${birthYear} as of ${asOf}`;

  const report = document.createElement("div");
  report.className = "outline-report";
  let dateMode = DEFAULT_DATE_MODE;
  const renderReport = () => {
    report.innerHTML = renderOutlineHtml(data.root, dateMode);
  };
  renderReport();

  body.appendChild(
    reportHeader({
      title: `Descendants of ${data.root.name}`,
      subtitle: `as of ${asOf}`,
      onPrint: () => window.print(),
      dateMode,
      onDateModeChange: (value) => {
        dateMode = value;
        renderReport();
      },
    })
  );
  body.appendChild(report);
}

async function renderDirectLine(body, rootId, targetId) {
  body.innerHTML = "";

  const toolbar = document.createElement("div");
  toolbar.className = "report-toolbar no-print";
  toolbar.innerHTML = `<button id="pick-target-btn">${targetId ? "Change target person…" : "Choose target descendant…"}</button>`;
  body.appendChild(toolbar);

  toolbar.querySelector("#pick-target-btn").addEventListener("click", async () => {
    const chosen = await pickPerson({ excludeId: rootId, title: "Choose the descendant to trace the line to" });
    if (chosen === null) return;
    location.hash = hashFor(rootId, { direction: "descendants", generations: 5, view: "direct", targetId: chosen });
  });

  if (!targetId) {
    const hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = "Choose a descendant above to trace the direct line of descent down to them.";
    body.appendChild(hint);
    return;
  }

  let data;
  try {
    data = await api.getDirectLine(rootId, targetId);
  } catch (err) {
    showError(body, err);
    return;
  }

  const first = data.steps[0];
  const last = data.steps[data.steps.length - 1];
  const asOf = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long" });
  document.title = `Direct Line Descendants of ${first.name} to ${last.name} as of ${asOf}`;

  const report = document.createElement("div");
  report.className = "outline-report";
  let dateMode = DEFAULT_DATE_MODE;
  const renderReport = () => {
    report.innerHTML = renderDirectLineHtml(data.steps, dateMode);
  };
  renderReport();

  body.appendChild(
    reportHeader({
      title: `Direct Descendants of ${first.name} to ${last.name}`,
      subtitle: `as of ${asOf}`,
      onPrint: () => window.print(),
      dateMode,
      onDateModeChange: (value) => {
        dateMode = value;
        renderReport();
      },
    })
  );
  body.appendChild(report);
}

function drawTree(svgEl, hierarchyData, direction) {
  const width = svgEl.clientWidth || 900;
  const height = svgEl.clientHeight || 560;
  const nodeSpacing = 90;

  const root = d3.hierarchy(hierarchyData);
  const depth = root.height || 1;

  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${width} ${height}`);
  svg.selectAll("*").remove();
  const g = svg.append("g");

  let layout;
  if (direction === "ancestors") {
    layout = d3.tree().size([height - 60, Math.max(width - 160, depth * nodeSpacing)]);
    layout(root);
    root.each((d) => {
      const x = d.y + 60;
      const y = d.x + 30;
      d.px = x;
      d.py = y;
    });
  } else {
    layout = d3.tree().size([width - 120, Math.max(height - 80, depth * nodeSpacing)]);
    layout(root);
    root.each((d) => {
      d.px = d.x + 60;
      d.py = d.y + 40;
    });
  }

  g.selectAll("path.tree-link")
    .data(root.links())
    .join("path")
    .attr("class", "tree-link")
    .attr(
      "d",
      d3
        .linkHorizontal()
        .x((d) => d.px)
        .y((d) => d.py)
    );

  const nodeGroups = g
    .selectAll("g.tree-node")
    .data(root.descendants())
    .join("g")
    .attr("class", (d) => `tree-node ${d.data.sex || "U"}`)
    .attr("transform", (d) => `translate(${d.px},${d.py})`)
    .style("cursor", "pointer");

  nodeGroups.append("circle").attr("r", 7);

  nodeGroups
    .append("text")
    .attr("x", 12)
    .attr("dy", "0.32em")
    .text((d) => d.data.name);

  nodeGroups
    .append("text")
    .attr("x", 12)
    .attr("dy", "1.5em")
    .attr("class", "muted")
    .style("font-size", "10px")
    .text((d) => {
      const years = [d.data.birth_year, d.data.death_year].filter(Boolean).join("–");
      const spouses = d.data.spouseNames?.length ? ` m. ${d.data.spouseNames.join(", ")}` : "";
      return `${years}${spouses}`;
    });

  nodeGroups.on("click", (_event, d) => {
    location.hash = `#/tree/${d.data.id}?direction=${direction}`;
  });

  nodeGroups.append("title").text((d) => d.data.name);
}
