import { renderSearch } from "./views/search.js";
import { renderPerson, showAddPersonModal } from "./views/person.js";
import { renderTree } from "./views/tree.js";
import { renderSources } from "./views/sources.js";
import { showError } from "./ui.js";

const app = document.getElementById("app");

function parseHash() {
  const raw = location.hash.slice(1) || "/";
  const [path, queryString] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  return { parts, query: new URLSearchParams(queryString || "") };
}

async function route() {
  const { parts, query } = parseHash();
  app.innerHTML = "";

  try {
    if (parts.length === 0) {
      await renderSearch(app);
    } else if (parts[0] === "person" && parts[1]) {
      await renderPerson(app, Number(parts[1]));
    } else if (parts[0] === "tree" && parts[1]) {
      const direction = query.get("direction") === "descendants" ? "descendants" : "ancestors";
      const generations = Math.max(2, Math.min(8, Number(query.get("generations")) || 5));
      await renderTree(app, Number(parts[1]), direction, generations);
    } else if (parts[0] === "sources") {
      await renderSources(app);
    } else {
      app.innerHTML = '<div class="card">Not found. <a href="#/">Go back</a></div>';
    }
  } catch (err) {
    showError(app, err);
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

document.getElementById("add-person-btn").addEventListener("click", showAddPersonModal);
