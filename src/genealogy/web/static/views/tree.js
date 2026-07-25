import { api } from "../api.js";

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

export async function renderTree(app, rootId, direction = "ancestors", generations = 5) {
  const container = document.createElement("div");
  container.innerHTML = `
    <div class="card">
      <div class="tree-controls">
        <strong>Pedigree</strong>
        <button id="dir-ancestors" class="${direction === "ancestors" ? "primary" : ""}">Ancestors</button>
        <button id="dir-descendants" class="${direction === "descendants" ? "primary" : ""}">Descendants</button>
        <label class="muted">Generations
          <select id="gen-select">
            ${[2, 3, 4, 5, 6, 7, 8].map((g) => `<option value="${g}" ${g === generations ? "selected" : ""}>${g}</option>`).join("")}
          </select>
        </label>
        <a id="view-detail-link" href="#/person/${rootId}">View person details &rarr;</a>
      </div>
      <svg id="tree-svg"></svg>
    </div>
  `;
  app.appendChild(container);

  container.querySelector("#dir-ancestors").addEventListener("click", () => {
    location.hash = `#/tree/${rootId}?direction=ancestors&generations=${generations}`;
  });
  container.querySelector("#dir-descendants").addEventListener("click", () => {
    location.hash = `#/tree/${rootId}?direction=descendants&generations=${generations}`;
  });
  container.querySelector("#gen-select").addEventListener("change", (e) => {
    location.hash = `#/tree/${rootId}?direction=${direction}&generations=${e.target.value}`;
  });

  const data = await api.getTree(rootId, direction, generations);
  const nodesById = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  const hierarchyData = buildHierarchy(rootId, nodesById, data.edges, direction, new Set());

  drawTree(container.querySelector("#tree-svg"), hierarchyData, direction);
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
