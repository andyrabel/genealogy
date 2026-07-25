import { api } from "../api.js";
import { esc } from "../ui.js";

export async function renderSearch(app) {
  const state = { q: "", surname: "", birth_from: "", birth_to: "", sort: "name", page: 1, page_size: 25 };

  const container = document.createElement("div");
  container.innerHTML = `
    <div class="card">
      <h2>Browse individuals</h2>
      <div class="search-row">
        <input id="q" placeholder="Name contains…" />
        <input id="surname" placeholder="Surname" style="max-width:160px" />
        <input id="birth_from" placeholder="Birth year from" style="max-width:140px" />
        <input id="birth_to" placeholder="Birth year to" style="max-width:140px" />
        <button id="search-btn" class="primary">Search</button>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Sex</th><th class="sortable" id="sort-birth">Birth</th><th>Death</th></tr></thead>
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
  const birthHeader = container.querySelector("#sort-birth");

  function updateSortHeader() {
    birthHeader.textContent = "Birth";
    if (state.sort === "birth_asc") birthHeader.textContent = "Birth ▲";
    else if (state.sort === "birth_desc") birthHeader.textContent = "Birth ▼";
  }

  async function load() {
    const params = { page: state.page, page_size: state.page_size, sort: state.sort };
    if (state.q) params.q = state.q;
    if (state.surname) params.surname = state.surname;
    if (state.birth_from) params.birth_from = state.birth_from;
    if (state.birth_to) params.birth_to = state.birth_to;

    const data = await api.listIndividuals(params);

    tbody.innerHTML =
      data.results
        .map(
          (r) => `
        <tr class="clickable" data-id="${r.id}">
          <td>${esc(r.name)}</td>
          <td>${r.sex ? `<span class="pill ${esc(r.sex)}">${esc(r.sex)}</span>` : ""}</td>
          <td>${esc(r.birth_date_raw)}</td>
          <td>${esc(r.death_date_raw)}${!r.death_date_raw && r.is_living ? '<span class="pill living">living?</span>' : ""}</td>
        </tr>`
        )
        .join("") || `<tr><td colspan="4" class="muted">No results.</td></tr>`;

    tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
      tr.addEventListener("click", () => {
        location.hash = `#/person/${tr.dataset.id}`;
      });
    });

    const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    pageInfo.textContent = `Page ${data.page} of ${totalPages} (${data.total} total)`;
    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= totalPages;
  }

  function applyFiltersFromInputs() {
    state.q = container.querySelector("#q").value.trim();
    state.surname = container.querySelector("#surname").value.trim();
    state.birth_from = container.querySelector("#birth_from").value.trim();
    state.birth_to = container.querySelector("#birth_to").value.trim();
    state.page = 1;
    load();
  }

  container.querySelector("#search-btn").addEventListener("click", applyFiltersFromInputs);
  container.querySelectorAll(".search-row input").forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") applyFiltersFromInputs();
    });
  });
  prevBtn.addEventListener("click", () => {
    state.page--;
    load();
  });
  nextBtn.addEventListener("click", () => {
    state.page++;
    load();
  });
  birthHeader.addEventListener("click", () => {
    state.sort = state.sort === "birth_asc" ? "birth_desc" : "birth_asc";
    state.page = 1;
    updateSortHeader();
    load();
  });

  updateSortHeader();
  await load();
}
