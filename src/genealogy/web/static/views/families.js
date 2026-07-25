import { api } from "../api.js";
import { esc } from "../ui.js";

export async function renderFamilies(app) {
  const state = { surname: "", page: 1, page_size: 25 };

  const container = document.createElement("div");
  container.innerHTML = `
    <div class="card">
      <h2>Browse families</h2>
      <div class="search-row">
        <input id="surname" placeholder="Husband or wife surname…" />
        <button id="search-btn" class="primary">Search</button>
      </div>
      <table>
        <thead><tr><th>Husband</th><th>Wife</th><th>Marriage</th><th>Children</th></tr></thead>
        <tbody id="results"></tbody>
      </table>
      <div class="pagination">
        <button id="prev-page">&laquo; Prev</button>
        <span id="page-info" class="muted"></span>
        <button id="next-page">Next &raquo;</button>
      </div>
    </div>
  `;
  app.appendChild(container);

  const tbody = container.querySelector("#results");
  const pageInfo = container.querySelector("#page-info");
  const prevBtn = container.querySelector("#prev-page");
  const nextBtn = container.querySelector("#next-page");

  async function load() {
    const params = { page: state.page, page_size: state.page_size };
    if (state.surname) params.surname = state.surname;

    const data = await api.listFamilies(params);

    tbody.innerHTML =
      data.results
        .map(
          (f) => `
        <tr class="clickable" data-id="${f.id}">
          <td>${f.husband ? esc(f.husband.name) : '<span class="muted">unknown</span>'}</td>
          <td>${f.wife ? esc(f.wife.name) : '<span class="muted">unknown</span>'}</td>
          <td>${f.marriage_date_raw || f.marriage_place ? esc([f.marriage_date_raw, f.marriage_place].filter(Boolean).join(" – ")) : ""}</td>
          <td>${f.children.length}</td>
        </tr>`
        )
        .join("") || `<tr><td colspan="4" class="muted">No families found.</td></tr>`;

    tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
      tr.addEventListener("click", () => {
        location.hash = `#/family/${tr.dataset.id}`;
      });
    });

    const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    pageInfo.textContent = `Page ${data.page} of ${totalPages} (${data.total} total)`;
    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= totalPages;
  }

  function applyFiltersFromInputs() {
    state.surname = container.querySelector("#surname").value.trim();
    state.page = 1;
    load();
  }

  container.querySelector("#search-btn").addEventListener("click", applyFiltersFromInputs);
  container.querySelector("#surname").addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyFiltersFromInputs();
  });
  prevBtn.addEventListener("click", () => {
    state.page--;
    load();
  });
  nextBtn.addEventListener("click", () => {
    state.page++;
    load();
  });

  await load();
}
