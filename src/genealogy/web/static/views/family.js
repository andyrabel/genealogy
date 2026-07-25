import { api } from "../api.js";
import { esc, confirmModal, pickPerson, showError } from "../ui.js";

const VITAL_FIELDS = ["birth_date_raw", "birth_place", "death_date_raw", "death_place"];

export async function renderFamily(app, familyId) {
  const container = document.createElement("div");
  app.appendChild(container);

  async function refresh() {
    let family;
    try {
      family = await api.getFamily(familyId);
    } catch (err) {
      container.innerHTML = "";
      showError(container, err);
      return;
    }
    // Fetched sequentially: the backend opens one SQLite connection per
    // request and isn't safe under concurrent requests (see get_conn).
    const husbandDetail = family.husband ? await api.getIndividual(family.husband.id) : null;
    const wifeDetail = family.wife ? await api.getIndividual(family.wife.id) : null;

    container.innerHTML = renderShell(family, husbandDetail, wifeDetail);
    wireParents(family, refresh, container);
    wireSpousePanels(family, refresh, container);
    wireMarriage(family, refresh, container);
    wireChildren(family, refresh, container);
  }

  await refresh();
}

function renderParentsColumn(role, roleLabel, detail) {
  if (!detail) {
    return `<div class="parents-col"><div class="parents-header">Parents of ${roleLabel}</div></div>`;
  }
  const fac = detail.family_as_child;
  return `
    <div class="parents-col">
      <div class="parents-header">Parents of ${esc(detail.given_names || roleLabel)}</div>
      ${
        fac
          ? `
        <div class="parents-row">
          <span>Father: ${fac.father ? `<a href="#/family/${fac.family_id}">${esc(fac.father.name)}</a>` : '<span class="muted">unknown</span>'}</span>
          <span>Mother: ${fac.mother ? `<a href="#/family/${fac.family_id}">${esc(fac.mother.name)}</a>` : '<span class="muted">unknown</span>'}</span>
        </div>`
          : `<button class="add-parents" data-role="${role}">+ Add Parents</button>`
      }
    </div>`;
}

function renderSpousePanel(role, roleLabel, spouse) {
  if (!spouse) {
    return `
      <div class="spouse-panel">
        <h3>${roleLabel}</h3>
        <p class="muted">No ${roleLabel.toLowerCase()} recorded.</p>
        <button class="choose-spouse" data-role="${role}">+ Choose ${roleLabel.toLowerCase()}</button>
      </div>`;
  }
  return `
    <div class="spouse-panel" data-id="${spouse.id}">
      <h3>${roleLabel}</h3>
      <a class="spouse-name" href="#/person/${spouse.id}">${esc(spouse.name)}</a>
      <div class="vital-row">
        <label>Birth date<input type="text" data-field="birth_date_raw" value="${esc(spouse.birth_date_raw)}" /></label>
        <label>Birth place<input type="text" data-field="birth_place" value="${esc(spouse.birth_place)}" /></label>
      </div>
      <div class="vital-row">
        <label>Death date<input type="text" data-field="death_date_raw" value="${esc(spouse.death_date_raw)}" /></label>
        <label>Death place<input type="text" data-field="death_place" value="${esc(spouse.death_place)}" /></label>
      </div>
    </div>`;
}

function renderShell(family, husbandDetail, wifeDetail) {
  const title = [family.husband?.name, family.wife?.name].filter(Boolean).join(" & ") || "Family";
  return `
    <div class="family-view">
      <div class="card family-header">
        <h2>${esc(title)}</h2>
        <div class="family-parents-row">
          ${renderParentsColumn("husband", "Husband", husbandDetail)}
          ${renderParentsColumn("wife", "Wife", wifeDetail)}
        </div>
      </div>

      <div class="card">
        <div class="spouse-grid">
          ${renderSpousePanel("husband", "Husband", family.husband)}
          ${renderSpousePanel("wife", "Wife", family.wife)}
        </div>
        <div class="marriage-row">
          <label>Married<input type="text" data-marriage="date_raw" value="${esc(family.marriage_date_raw)}" /></label>
          <label>at<input type="text" data-marriage="place" value="${esc(family.marriage_place)}" /></label>
        </div>
      </div>

      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3>Children (${family.children.length})</h3>
          <button id="add-child-btn">+ Add child</button>
        </div>
        <table>
          <thead>
            <tr><th>Name</th><th>Sex</th><th>Birth date</th><th>Birth place</th><th>Death date</th><th>Death place</th><th></th></tr>
          </thead>
          <tbody>
            ${
              family.children
                .map(
                  (c) => `
              <tr>
                <td><a href="#/${c.own_family_id ? `family/${c.own_family_id}` : `person/${c.id}`}">${esc(c.name)}</a></td>
                <td>${esc(c.sex)}</td>
                <td>${esc(c.birth_date_raw)}</td>
                <td>${esc(c.birth_place)}</td>
                <td>${esc(c.death_date_raw)}</td>
                <td>${esc(c.death_place)}</td>
                <td class="actions"><button class="link remove-child" data-id="${c.id}">remove</button></td>
              </tr>`
                )
                .join("") || `<tr><td colspan="7" class="muted">No children recorded.</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function ensureFamilyAsChild(individualId) {
  const detail = await api.getIndividual(individualId);
  if (detail.family_as_child) return detail.family_as_child.family_id;
  const fam = await api.createFamily({});
  await api.addChild(fam.id, individualId);
  return fam.id;
}

async function addParents(individualId, refresh) {
  const father = await pickPerson({ excludeId: individualId, title: "Choose father (cancel to skip)" });
  const mother = await pickPerson({ excludeId: individualId, title: "Choose mother (cancel to skip)" });
  if (father === null && mother === null) return;
  const familyId = await ensureFamilyAsChild(individualId);
  if (father !== null) await api.updateSpouse(familyId, { role: "HUSB", individual_id: father });
  if (mother !== null) await api.updateSpouse(familyId, { role: "WIFE", individual_id: mother });
  await refresh();
}

function wireParents(family, refresh, container) {
  container.querySelectorAll(".add-parents").forEach((btn) => {
    btn.addEventListener("click", () => {
      const individualId = btn.dataset.role === "husband" ? family.husband.id : family.wife.id;
      addParents(individualId, refresh);
    });
  });
}

function wireSpousePanels(family, refresh, container) {
  container.querySelectorAll(".spouse-panel[data-id]").forEach((panel) => {
    const individualId = Number(panel.dataset.id);

    const vitalInputs = VITAL_FIELDS.map((f) => panel.querySelector(`[data-field="${f}"]`));
    const originals = vitalInputs.map((i) => i.value);
    vitalInputs.forEach((input, idx) => {
      input.addEventListener("blur", async () => {
        if (input.value === originals[idx]) return;
        const body = {};
        VITAL_FIELDS.forEach((f, i) => {
          body[f] = vitalInputs[i].value.trim() || null;
        });
        vitalInputs.forEach((i) => (i.disabled = true));
        try {
          await api.updateVitals(individualId, body);
          await refresh();
        } catch (err) {
          vitalInputs.forEach((i) => (i.disabled = false));
          alert(err.message);
        }
      });
    });
  });

  container.querySelectorAll(".choose-spouse").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const roleAttr = btn.dataset.role;
      const role = roleAttr === "husband" ? "HUSB" : "WIFE";
      const excludeId = roleAttr === "husband" ? family.wife?.id : family.husband?.id;
      const chosen = await pickPerson({ excludeId, title: `Choose ${roleAttr}` });
      if (chosen === null) return;
      await api.updateSpouse(family.id, { role, individual_id: chosen });
      await refresh();
    });
  });
}

function wireMarriage(family, refresh, container) {
  const dateInput = container.querySelector('[data-marriage="date_raw"]');
  const placeInput = container.querySelector('[data-marriage="place"]');
  [dateInput, placeInput].forEach((input) => {
    const original = input.value;
    input.addEventListener("blur", async () => {
      if (input.value === original) return;
      input.disabled = true;
      try {
        await api.updateMarriage(family.id, {
          date_raw: dateInput.value.trim() || null,
          place: placeInput.value.trim() || null,
        });
        await refresh();
      } catch (err) {
        input.disabled = false;
        alert(err.message);
      }
    });
  });
}

function wireChildren(family, refresh, container) {
  container.querySelector("#add-child-btn").addEventListener("click", async () => {
    const chosen = await pickPerson({ title: "Choose child" });
    if (chosen === null) return;
    await api.addChild(family.id, chosen);
    await refresh();
  });

  container.querySelectorAll(".remove-child").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await confirmModal("Remove this child from the family? (does not delete the person)", { confirmLabel: "Remove" });
      if (!ok) return;
      await api.removeChild(family.id, Number(btn.dataset.id));
      await refresh();
    });
  });
}
