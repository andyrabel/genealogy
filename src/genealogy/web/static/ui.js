import { api } from "./api.js";

export const SEX_OPTIONS = [
  { value: "", label: "(unknown)" },
  { value: "M", label: "Male" },
  { value: "F", label: "Female" },
  { value: "U", label: "Unknown" },
];

export function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderField(field, values) {
  const value = values[field.name] ?? "";
  if (field.type === "select") {
    const options = field.options
      .map((o) => `<option value="${esc(o.value)}" ${value === o.value ? "selected" : ""}>${esc(o.label)}</option>`)
      .join("");
    return `<label>${esc(field.label)}<select name="${field.name}">${options}</select></label>`;
  }
  if (field.type === "textarea") {
    return `<label>${esc(field.label)}<textarea name="${field.name}" rows="3">${esc(value)}</textarea></label>`;
  }
  return `<label>${esc(field.label)}<input type="text" name="${field.name}" value="${esc(value)}" /></label>`;
}

/** A form modal for creating/editing a record. `onSubmit` receives a plain
 * object of {name: value}; empty strings are normalized to null. */
export function openFormModal({ title, fields, values = {}, onSubmit, submitLabel = "Save" }) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <h3>${esc(title)}</h3>
    <form>
      <div class="field-grid">${fields.map((f) => renderField(f, values)).join("")}</div>
      <div class="modal-actions">
        <button type="button" class="cancel">Cancel</button>
        <button type="submit" class="primary">${esc(submitLabel)}</button>
      </div>
    </form>
  `;
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  function close() {
    backdrop.remove();
  }
  modal.querySelector(".cancel").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });
  modal.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = {};
    for (const f of fields) {
      const raw = formData.get(f.name);
      data[f.name] = raw && raw.trim ? raw.trim() || null : raw || null;
    }
    const submitBtn = modal.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    try {
      await onSubmit(data);
      close();
    } catch (err) {
      submitBtn.disabled = false;
      showInlineError(modal, err.message);
    }
  });
}

function showInlineError(modal, message) {
  let banner = modal.querySelector(".error-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.className = "error-banner";
    modal.querySelector("form").prepend(banner);
  }
  banner.textContent = message;
}

export function confirmModal(message, { confirmLabel = "Delete", danger = true } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    const modal = document.createElement("div");
    modal.className = "modal";
    modal.innerHTML = `
      <p>${esc(message)}</p>
      <div class="modal-actions">
        <button type="button" class="cancel">Cancel</button>
        <button type="button" class="confirm ${danger ? "danger" : "primary"}">${esc(confirmLabel)}</button>
      </div>
    `;
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    function close(result) {
      backdrop.remove();
      resolve(result);
    }
    modal.querySelector(".cancel").addEventListener("click", () => close(false));
    modal.querySelector(".confirm").addEventListener("click", () => close(true));
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close(false);
    });
  });
}

/** Search-as-you-type person picker, with an option to create a brand-new
 * person instead of choosing an existing one. Resolves to the chosen (or
 * newly created) individual id, or null if cancelled. */
export function pickPerson({ excludeId = null, title = "Choose a person" } = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    const modal = document.createElement("div");
    modal.className = "modal";
    modal.innerHTML = `
      <h3>${esc(title)}</h3>
      <input type="text" id="picker-q" placeholder="Type a name…" style="width:100%" autocomplete="off" />
      <div id="picker-results" style="margin-top:0.75rem; max-height:260px; overflow-y:auto;"></div>
      <button type="button" class="link" id="picker-create-toggle" style="margin-top:0.75rem;">+ Create a new person instead</button>
      <form id="picker-create-form" style="display:none; margin-top:0.75rem;">
        <div class="field-grid">
          <label>Given names<input type="text" name="given_names" /></label>
          <label>Surname<input type="text" name="surname" /></label>
          <label>Sex<select name="sex">${SEX_OPTIONS.map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join("")}</select></label>
        </div>
        <div class="modal-actions"><button type="submit" class="primary">Create &amp; choose</button></div>
      </form>
      <div class="modal-actions"><button type="button" class="cancel">Cancel</button></div>
    `;
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    function close(result) {
      backdrop.remove();
      resolve(result);
    }
    modal.querySelector(".cancel").addEventListener("click", () => close(null));
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close(null);
    });

    const input = modal.querySelector("#picker-q");
    const results = modal.querySelector("#picker-results");
    const createToggle = modal.querySelector("#picker-create-toggle");
    const createForm = modal.querySelector("#picker-create-form");
    createToggle.addEventListener("click", () => {
      const switchingToCreate = createForm.style.display === "none";
      createForm.style.display = switchingToCreate ? "block" : "none";
      input.style.display = switchingToCreate ? "none" : "";
      results.style.display = switchingToCreate ? "none" : "";
      createToggle.textContent = switchingToCreate ? "← Search existing people instead" : "+ Create a new person instead";
      if (switchingToCreate) createForm.querySelector('[name="given_names"]').focus();
      else input.focus();
    });
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(createForm);
      const data = {
        given_names: formData.get("given_names").trim() || null,
        surname: formData.get("surname").trim() || null,
        sex: formData.get("sex") || null,
      };
      const submitBtn = createForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        const created = await api.createIndividual(data);
        close(created.id);
      } catch (err) {
        submitBtn.disabled = false;
        showInlineError(modal, err.message);
      }
    });

    let debounceHandle;
    input.addEventListener("input", () => {
      clearTimeout(debounceHandle);
      debounceHandle = setTimeout(async () => {
        const q = input.value.trim();
        if (!q) {
          results.innerHTML = "";
          return;
        }
        const data = await api.listIndividuals({ q, page_size: 10 });
        const matches = data.results.filter((r) => r.id !== excludeId);
        results.innerHTML =
          matches
            .map(
              (r) =>
                `<div class="list-item clickable" data-id="${r.id}"><span>${esc(r.name)}</span><span class="muted">${esc(r.birth_date_raw)}</span></div>`
            )
            .join("") || `<p class="muted">No matches.</p>`;
        results.querySelectorAll("[data-id]").forEach((node) => {
          node.addEventListener("click", () => close(Number(node.dataset.id)));
        });
      }, 200);
    });
    input.focus();
  });
}

export function showError(app, err) {
  console.error(err);
  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.textContent = err.message || String(err);
  app.prepend(banner);
}
