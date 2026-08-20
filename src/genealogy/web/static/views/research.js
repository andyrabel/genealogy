import { api } from "../api.js";
import { esc, openFormModal } from "../ui.js";

function factsLine(facts) {
  const bits = [];
  if (facts.birth_year || facts.birth_place) {
    bits.push(`b. ${esc(facts.birth_year || "?")}${facts.birth_place ? ` in ${esc(facts.birth_place)}` : ""}`);
  }
  if (facts.death_year || facts.death_place) {
    bits.push(`d. ${esc(facts.death_year || "?")}${facts.death_place ? ` in ${esc(facts.death_place)}` : ""}`);
  }
  if (facts.father_surname) bits.push(`father's surname: ${esc(facts.father_surname)}`);
  return bits.join(" &middot; ") || "No dates or places recorded yet -- searches will be broad.";
}

function renderLinks(links) {
  return links
    .map(
      (l) => `
    <div class="list-item">
      <div>
        <a href="${esc(l.url)}" target="_blank" rel="noopener"><button class="primary">${esc(l.label)}</button></a>
        ${l.prefilled ? "" : `<span class="muted"> (opens plain search -- use the facts above)</span>`}
      </div>
      <span class="muted">${esc(l.description)}</span>
    </div>`
    )
    .join("");
}

function citationTooltip(citations) {
  if (!citations || citations.length === 0) return "";
  return citations
    .map((c) => c.page ? `${c.source_title || "Untitled source"} — ${c.page}` : c.source_title || "Untitled source")
    .join("\n");
}

function renderPatriline(chain) {
  if (chain.length === 0) return `<p class="muted">Unable to compute patriline.</p>`;

  const rows = chain
    .map((step, i) => {
      const years = [step.birth_year, step.death_year].filter(Boolean).join("–");
      const marker = step.has_citation
        ? `<a class="pill living" href="#/person/${step.id}?focus=citations" title="${esc(citationTooltip(step.citations))}">sourced</a>`
        : `<span class="pill F">unsourced</span>`;
      const label = `<a href="#/person/${step.id}">${esc(step.name)}</a>`;
      return `<div class="list-item"><span>${"&nbsp;&nbsp;".repeat(i)}${label}${years ? ` <span class="muted">(${esc(years)})</span>` : ""}</span>${marker}</div>`;
    })
    .join("");

  const last = chain[chain.length - 1];
  const nextTarget = `<p class="muted">Next research target: find the father of <a href="#/person/${last.id}">${esc(last.name)}</a>${
    last.has_citation ? "" : " (and a source for their own birth)"
  }.</p>`;

  return rows + nextTarget;
}

export async function renderResearchPanel(app, person, refreshPerson) {
  const container = document.createElement("div");
  container.className = "card";
  app.appendChild(container);

  container.innerHTML = `<p class="muted">Loading research panel&hellip;</p>`;

  let facts;
  let links;
  let chain;
  try {
    const [linkData, patrilineData] = await Promise.all([
      api.getResearchLinks(person.id),
      api.getPatriline(person.id),
    ]);
    facts = linkData.facts;
    links = linkData.links;
    chain = patrilineData.chain;
  } catch (err) {
    container.innerHTML = `<h3>Research</h3><p class="muted">Couldn't load research data: ${esc(err.message)}</p>`;
    return;
  }

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h3>Research</h3>
      <button id="log-find-btn">Log a find</button>
    </div>

    <p class="muted">${factsLine(facts)}</p>

    <h4>Search UK records</h4>
    ${renderLinks(links)}

    <h4>Patriline</h4>
    ${renderPatriline(chain)}
  `;

  container.querySelector("#log-find-btn").addEventListener("click", () => {
    const applyOptions = [
      { value: "general", label: "General (about this person)" },
      ...person.events.map((e) => ({ value: `event:${e.id}`, label: `${e.event_type} (${e.date_raw || "no date"})` })),
    ];

    openFormModal({
      title: "Log a find",
      fields: [
        { name: "title", label: "Title" },
        { name: "url", label: "URL" },
        { name: "author", label: "Author / repository" },
        { name: "page", label: "Page / reference" },
        { name: "quality", label: "Quality (0-3)" },
        { name: "applies_to", label: "Applies to", type: "select", options: applyOptions },
        { name: "note", label: "Note", type: "textarea" },
      ],
      values: { applies_to: "general" },
      submitLabel: "Save",
      onSubmit: async (data) => {
        const source = await api.createSource({
          title: data.title,
          author: data.author,
          repository_note: data.author,
          url: data.url,
        });
        const isEvent = data.applies_to && data.applies_to.startsWith("event:");
        await api.addCitation({
          source_id: source.id,
          event_id: isEvent ? Number(data.applies_to.split(":")[1]) : null,
          individual_id: isEvent ? null : person.id,
          page: data.page,
          quality: data.quality,
          note: data.note,
        });
        await refreshPerson();
      },
    });
  });
}
