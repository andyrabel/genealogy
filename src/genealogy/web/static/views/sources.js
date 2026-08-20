import { api } from "../api.js";
import { esc, openFormModal, confirmModal, showError } from "../ui.js";

const SOURCE_FIELDS = [
  { name: "title", label: "Title" },
  { name: "author", label: "Author" },
  { name: "publication_info", label: "Publication info" },
  { name: "repository_note", label: "Repository" },
  { name: "url", label: "URL" },
];

export async function renderSources(app) {
  const container = document.createElement("div");
  app.appendChild(container);

  async function refresh() {
    let sources;
    try {
      sources = (await api.listSources()).results;
    } catch (err) {
      container.innerHTML = "";
      showError(container, err);
      return;
    }

    container.innerHTML = `
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h2>Sources</h2>
          <button id="add-source-btn" class="primary">+ Add source</button>
        </div>
        <table>
          <thead><tr><th>Title</th><th>Author</th><th>Publication</th><th>Link</th><th></th></tr></thead>
          <tbody>
            ${sources
              .map(
                (s) => `
              <tr>
                <td>${esc(s.title) || `<span class="muted">Source #${s.id}</span>`}</td>
                <td>${esc(s.author)}</td>
                <td>${esc(s.publication_info)}</td>
                <td>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">open</a>` : ""}</td>
                <td class="actions">
                  <button class="link edit-source" data-id="${s.id}">edit</button>
                  <button class="link delete-source" data-id="${s.id}">delete</button>
                </td>
              </tr>`
              )
              .join("") || `<tr><td colspan="5" class="muted">No sources yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;

    container.querySelector("#add-source-btn").addEventListener("click", () => {
      openFormModal({
        title: "Add source",
        fields: SOURCE_FIELDS,
        submitLabel: "Create",
        onSubmit: async (data) => {
          await api.createSource(data);
          await refresh();
        },
      });
    });

    container.querySelectorAll(".edit-source").forEach((btn) => {
      btn.addEventListener("click", () => {
        const source = sources.find((s) => s.id === Number(btn.dataset.id));
        openFormModal({
          title: "Edit source",
          fields: SOURCE_FIELDS,
          values: source,
          onSubmit: async (data) => {
            await api.updateSource(source.id, data);
            await refresh();
          },
        });
      });
    });

    container.querySelectorAll(".delete-source").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ok = await confirmModal("Delete this source? Any citations referencing it will be removed too.");
        if (!ok) return;
        await api.deleteSource(Number(btn.dataset.id));
        await refresh();
      });
    });
  }

  await refresh();
}
