import { api } from "../api.js";
import { esc, openFormModal, confirmModal, pickPerson, showError, SEX_OPTIONS } from "../ui.js";
import { renderResearchPanel } from "./research.js";

const EVENT_TYPES = [
  "BIRT", "CHR", "DEAT", "BURI", "CREM", "BAPM", "CONF", "OCCU", "RESI",
  "EDUC", "EMIG", "IMMI", "NATU", "CENS", "PROB", "WILL", "GRAD", "RETI", "EVEN",
];

export async function renderPerson(app, id) {
  const container = document.createElement("div");
  app.appendChild(container);

  async function refresh() {
    let person;
    try {
      person = await api.getIndividual(id);
    } catch (err) {
      container.innerHTML = "";
      showError(container, err);
      return;
    }
    container.innerHTML = renderShell(person);
    wireHeader(person, refresh, container);
    wireEvents(person, refresh, container);
    wireParents(person, refresh, container);
    wireFamilies(person, refresh, container);
    wireCitations(person, refresh, container);
    await renderResearchPanel(container, person, refresh);
    focusFromQuery(container);
  }

  await refresh();
}

function focusFromQuery(container) {
  const [, queryString] = location.hash.slice(1).split("?");
  const focus = new URLSearchParams(queryString || "").get("focus");
  if (focus !== "citations") return;
  const card = container.querySelector("#citations-card");
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "start" });
  card.classList.add("focus-flash");
  setTimeout(() => card.classList.remove("focus-flash"), 2000);
}

function personLabel(p) {
  if (!p) return "";
  const years = [p.birth_date_raw, p.death_date_raw].filter(Boolean).join(" – ");
  return `${esc(p.name)}${years ? ` <span class="muted">(${esc(years)})</span>` : ""}`;
}

function renderShell(person) {
  return `
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <h2>${esc(person.name)} ${person.sex ? `<span class="pill ${esc(person.sex)}">${esc(person.sex)}</span>` : ""}</h2>
          <p class="muted">
            ${person.birth_date_raw ? `Born ${esc(person.birth_date_raw)}${person.birth_place ? ` in ${esc(person.birth_place)}` : ""}` : "Birth unknown"}
            ${person.death_date_raw ? ` &middot; Died ${esc(person.death_date_raw)}${person.death_place ? ` in ${esc(person.death_place)}` : ""}` : person.is_living ? " &middot; Living" : ""}
          </p>
        </div>
        <div class="actions">
          <a href="#/tree/${person.id}?direction=ancestors"><button>Ancestors</button></a>
          <a href="#/tree/${person.id}?direction=descendants"><button>Descendants</button></a>
          <a href="#/tree/${person.id}?direction=descendants&view=outline"><button>Outline</button></a>
          <a href="#/tree/${person.id}?direction=descendants&view=direct"><button>Direct Line</button></a>
          <button id="edit-person-btn">Edit</button>
          <button id="delete-person-btn" class="danger">Delete</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Events</h3>
        <button id="add-event-btn">+ Add event</button>
      </div>
      <table>
        <thead><tr><th>Type</th><th>Date</th><th>Place</th><th>Note</th><th></th></tr></thead>
        <tbody id="events-body">
          ${person.events
            .map(
              (e) => `
            <tr data-id="${e.id}">
              <td>${esc(e.event_type)}</td>
              <td>${esc(e.date_raw)}</td>
              <td>${esc(e.place)}</td>
              <td>${esc(e.note)}</td>
              <td class="actions">
                <button class="link edit-event" data-id="${e.id}">edit</button>
                <button class="link delete-event" data-id="${e.id}">delete</button>
              </td>
            </tr>`
            )
            .join("") || `<tr><td colspan="5" class="muted">No events recorded.</td></tr>`}
        </tbody>
      </table>
    </div>

    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Parents</h3>
        ${person.family_as_child ? `<a href="#/family/${person.family_as_child.family_id}"><button class="primary">Family view</button></a>` : ""}
      </div>
      ${
        person.family_as_child
          ? `
        <div class="list-item">
          <span>Father: ${person.family_as_child.father ? `<a href="#/person/${person.family_as_child.father.id}">${personLabel(person.family_as_child.father)}</a>` : '<span class="muted">unknown</span>'}</span>
          <button class="link set-father">${person.family_as_child.father ? "change" : "set"}</button>
        </div>
        <div class="list-item">
          <span>Mother: ${person.family_as_child.mother ? `<a href="#/person/${person.family_as_child.mother.id}">${personLabel(person.family_as_child.mother)}</a>` : '<span class="muted">unknown</span>'}</span>
          <button class="link set-mother">${person.family_as_child.mother ? "change" : "set"}</button>
        </div>`
          : `<p class="muted">No parent family recorded.</p>
             <div class="actions"><button class="set-father">Set father</button><button class="set-mother">Set mother</button></div>`
      }
    </div>

    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Families</h3>
        <button id="add-spouse-btn">+ Add spouse</button>
      </div>
      <div id="families-body">
        ${
          person.families_as_spouse
            .map(
              (f) => `
          <div class="card" data-family-id="${f.family_id}" style="background:var(--bg);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <strong>${f.spouse ? `<a href="#/person/${f.spouse.id}">${personLabel(f.spouse)}</a>` : '<span class="muted">no spouse recorded</span>'}</strong>
                <div class="muted">
                  ${f.marriage_date_raw || f.marriage_place ? `Married ${esc(f.marriage_date_raw)}${f.marriage_place ? ` in ${esc(f.marriage_place)}` : ""}` : "Marriage date/place unknown"}
                </div>
              </div>
              <div class="actions">
                <a href="#/family/${f.family_id}"><button class="primary">Family view</button></a>
                <button class="link edit-marriage" data-family="${f.family_id}">edit marriage</button>
              </div>
            </div>
            <table style="margin-top:0.5rem;">
              <thead><tr><th>Child</th><th></th></tr></thead>
              <tbody>
                ${f.children
                  .map(
                    (c) => `
                  <tr>
                    <td><a href="#/person/${c.id}">${personLabel(c)}</a></td>
                    <td class="actions"><button class="link remove-child" data-family="${f.family_id}" data-child="${c.id}">remove</button></td>
                  </tr>`
                  )
                  .join("") || `<tr><td colspan="2" class="muted">No children recorded.</td></tr>`}
              </tbody>
            </table>
            <button class="add-child" data-family="${f.family_id}">+ Add child</button>
          </div>`
            )
            .join("") || `<p class="muted">No families recorded.</p>`
        }
      </div>
    </div>

    <div class="card" id="citations-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Sources</h3>
        <button id="add-citation-btn">+ Add citation</button>
      </div>
      <table>
        <thead><tr><th>Source</th><th>Page</th><th>Quality</th><th>Note</th><th></th></tr></thead>
        <tbody>
          ${person.citations
            .map(
              (c) => `
            <tr>
              <td>${c.source ? esc(c.source.title) : '<span class="muted">(source removed)</span>'}</td>
              <td>${esc(c.page)}</td>
              <td>${esc(c.quality)}</td>
              <td>${esc(c.note)}</td>
              <td><button class="link delete-citation" data-id="${c.id}">delete</button></td>
            </tr>`
            )
            .join("") || `<tr><td colspan="5" class="muted">No citations recorded.</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function wireHeader(person, refresh, container) {
  container.querySelector("#edit-person-btn").addEventListener("click", () => {
    openFormModal({
      title: "Edit person",
      fields: [
        { name: "given_names", label: "Given names" },
        { name: "surname", label: "Surname" },
        { name: "prefix", label: "Prefix" },
        { name: "suffix", label: "Suffix" },
        { name: "sex", label: "Sex", type: "select", options: SEX_OPTIONS },
      ],
      values: {
        given_names: person.given_names,
        surname: person.surname,
        prefix: person.name_prefix,
        suffix: person.name_suffix,
        sex: person.sex,
      },
      onSubmit: async (data) => {
        await api.updateIndividual(person.id, data);
        await refresh();
      },
    });
  });

  container.querySelector("#delete-person-btn").addEventListener("click", async () => {
    const ok = await confirmModal(`Delete ${person.name}? This also removes their events and citations.`);
    if (!ok) return;
    await api.deleteIndividual(person.id);
    location.hash = "#/";
  });
}

function wireEvents(person, refresh, container) {
  container.querySelector("#add-event-btn").addEventListener("click", () => {
    openFormModal({
      title: "Add event",
      fields: [
        { name: "event_type", label: "Type", type: "select", options: EVENT_TYPES.map((t) => ({ value: t, label: t })) },
        { name: "date_raw", label: "Date" },
        { name: "place", label: "Place" },
        { name: "note", label: "Note", type: "textarea" },
      ],
      submitLabel: "Add",
      onSubmit: async (data) => {
        await api.addEvent({ owner_type: "INDI", owner_id: person.id, ...data });
        await refresh();
      },
    });
  });

  container.querySelectorAll(".edit-event").forEach((btn) => {
    btn.addEventListener("click", () => {
      const event = person.events.find((e) => e.id === Number(btn.dataset.id));
      openFormModal({
        title: `Edit ${event.event_type}`,
        fields: [
          { name: "date_raw", label: "Date" },
          { name: "place", label: "Place" },
          { name: "note", label: "Note", type: "textarea" },
        ],
        values: event,
        onSubmit: async (data) => {
          await api.updateEvent(event.id, data);
          await refresh();
        },
      });
    });
  });

  container.querySelectorAll(".delete-event").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await confirmModal("Delete this event?");
      if (!ok) return;
      await api.deleteEvent(Number(btn.dataset.id));
      await refresh();
    });
  });
}

async function setParent(person, role, refresh) {
  const chosen = await pickPerson({ excludeId: person.id, title: role === "HUSB" ? "Choose father" : "Choose mother" });
  if (chosen === null) return;

  let familyId = person.family_as_child?.family_id;
  if (!familyId) {
    const family = await api.createFamily({});
    familyId = family.id;
    await api.addChild(familyId, person.id);
  }
  await api.updateSpouse(familyId, { role, individual_id: chosen });
  await refresh();
}

function wireParents(person, refresh, container) {
  container.querySelectorAll(".set-father").forEach((btn) => btn.addEventListener("click", () => setParent(person, "HUSB", refresh)));
  container.querySelectorAll(".set-mother").forEach((btn) => btn.addEventListener("click", () => setParent(person, "WIFE", refresh)));
}

function wireFamilies(person, refresh, container) {
  container.querySelector("#add-spouse-btn").addEventListener("click", async () => {
    const chosen = await pickPerson({ excludeId: person.id, title: "Choose spouse (cancel for unknown spouse)" });
    const body =
      person.sex === "F"
        ? { husband_id: chosen, wife_id: person.id }
        : { husband_id: person.id, wife_id: chosen };
    await api.createFamily(body);
    await refresh();
  });

  container.querySelectorAll(".edit-marriage").forEach((btn) => {
    btn.addEventListener("click", () => {
      const family = person.families_as_spouse.find((f) => f.family_id === Number(btn.dataset.family));
      openFormModal({
        title: "Edit marriage",
        fields: [
          { name: "date_raw", label: "Date" },
          { name: "place", label: "Place" },
        ],
        values: { date_raw: family.marriage_date_raw, place: family.marriage_place },
        onSubmit: async (data) => {
          await api.updateMarriage(family.family_id, data);
          await refresh();
        },
      });
    });
  });

  container.querySelectorAll(".add-child").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const familyId = Number(btn.dataset.family);
      const chosen = await pickPerson({ title: "Choose child" });
      if (chosen === null) return;
      await api.addChild(familyId, chosen);
      await refresh();
    });
  });

  container.querySelectorAll(".remove-child").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await confirmModal("Remove this child from the family? (does not delete the person)", { confirmLabel: "Remove" });
      if (!ok) return;
      await api.removeChild(Number(btn.dataset.family), Number(btn.dataset.child));
      await refresh();
    });
  });
}

function wireCitations(person, refresh, container) {
  container.querySelector("#add-citation-btn").addEventListener("click", async () => {
    const sources = (await api.listSources()).results;
    if (sources.length === 0) {
      alert("No sources exist yet. Create one from the Sources page first.");
      return;
    }
    openFormModal({
      title: "Add citation",
      fields: [
        { name: "source_id", label: "Source", type: "select", options: sources.map((s) => ({ value: String(s.id), label: s.title || `Source #${s.id}` })) },
        { name: "page", label: "Page" },
        { name: "quality", label: "Quality (0-3)" },
        { name: "note", label: "Note", type: "textarea" },
      ],
      submitLabel: "Add",
      onSubmit: async (data) => {
        await api.addCitation({ ...data, source_id: Number(data.source_id), individual_id: person.id });
        await refresh();
      },
    });
  });

  container.querySelectorAll(".delete-citation").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await confirmModal("Delete this citation?");
      if (!ok) return;
      await api.deleteCitation(Number(btn.dataset.id));
      await refresh();
    });
  });
}
