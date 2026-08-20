const BASE = "/api";

async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(BASE + path, opts);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${method} ${path} failed: ${detail}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  listIndividuals: (params = {}) =>
    request("GET", `/individuals?${new URLSearchParams(params)}`),
  getIndividual: (id) => request("GET", `/individuals/${id}`),
  createIndividual: (body) => request("POST", "/individuals", body),
  updateIndividual: (id, body) => request("PUT", `/individuals/${id}`, body),
  updateVitals: (id, body) => request("PUT", `/individuals/${id}/vitals`, body),
  deleteIndividual: (id) => request("DELETE", `/individuals/${id}`),

  listFamilies: (params = {}) => request("GET", `/families?${new URLSearchParams(params)}`),
  getFamily: (id) => request("GET", `/families/${id}`),
  createFamily: (body) => request("POST", "/families", body),
  updateMarriage: (id, body) => request("PUT", `/families/${id}`, body),
  updateSpouse: (id, body) => request("PUT", `/families/${id}/spouse`, body),
  addChild: (familyId, childId) =>
    request("POST", `/families/${familyId}/children`, { child_id: childId }),
  removeChild: (familyId, childId) =>
    request("DELETE", `/families/${familyId}/children/${childId}`),
  deleteFamily: (id) => request("DELETE", `/families/${id}`),

  addEvent: (body) => request("POST", "/events", body),
  updateEvent: (id, body) => request("PUT", `/events/${id}`, body),
  deleteEvent: (id) => request("DELETE", `/events/${id}`),

  listSources: () => request("GET", "/sources"),
  getSource: (id) => request("GET", `/sources/${id}`),
  createSource: (body) => request("POST", "/sources", body),
  updateSource: (id, body) => request("PUT", `/sources/${id}`, body),
  deleteSource: (id) => request("DELETE", `/sources/${id}`),

  addCitation: (body) => request("POST", "/citations", body),
  deleteCitation: (id) => request("DELETE", `/citations/${id}`),

  getTree: (id, direction, generations) =>
    request("GET", `/tree/${id}?direction=${direction}&generations=${generations}`),

  getDescendantsOutline: (id) => request("GET", `/reports/descendants/${id}`),
  getDirectLine: (fromId, toId) =>
    request("GET", `/reports/direct-line?from_id=${fromId}&to_id=${toId}`),

  getPatriline: (id) => request("GET", `/individuals/${id}/patriline`),
  getResearchLinks: (id) => request("GET", `/individuals/${id}/research-links`),
};
