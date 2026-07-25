import { esc } from "../ui.js";

const ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"];
const DOTS_PER_GENERATION = 6;

export const DATE_MODES = [
  { value: "full", label: "Full (birth + death)" },
  { value: "birth-date", label: "Birth date only" },
  { value: "birth-year", label: "Birth year only" },
  { value: "lifespan", label: "Birth–death years only" },
  { value: "lifespan-marriage", label: "Birth–death & marriage years" },
];
export const DEFAULT_DATE_MODE = "lifespan";

function ordinal(n) {
  return ORDINALS[n - 1] || `${n}th`;
}

function datesOf(person, dateMode) {
  switch (dateMode) {
    case "birth-date":
      return person.birth_date_raw ? `b: ${person.birth_date_raw}` : "";
    case "birth-year":
      return person.birth_year ? `b: ${person.birth_year}` : "";
    case "lifespan":
    case "lifespan-marriage": {
      if (!person.birth_year && !person.death_year) return "";
      const end = person.death_year || (person.is_living ? "" : "?");
      return `${person.birth_year || "?"}-${end}`;
    }
    case "full":
    default:
      return [person.birth_date_raw ? `b: ${person.birth_date_raw}` : null, person.death_date_raw ? `d: ${person.death_date_raw}` : null]
        .filter(Boolean)
        .join("  ");
  }
}

function marriageOf(union, dateMode) {
  if (dateMode === "lifespan") return "";
  if (dateMode === "lifespan-marriage") {
    return union.marriage_year ? `m: ${union.marriage_year}` : "";
  }
  return union.marriage_date_raw ? `m: ${union.marriage_date_raw}` : "";
}

function line(dotCount, marker, person, extra, dateMode) {
  const dots = ".".repeat(Math.max(dotCount, 0));
  const link = `<a href="#/person/${person.id}">${esc(person.name)}</a>`;
  const bits = [datesOf(person, dateMode), extra].filter(Boolean).join("  ");
  return `<div class="outline-line"><span class="dots">${esc(dots)}</span>${marker}${link}${bits ? ` <span class="muted">${esc(bits)}</span>` : ""}</div>`;
}

function spouseRoleLabel(person) {
  if (person.sex === "F") return "Husband";
  if (person.sex === "M") return "Wife";
  return "Spouse";
}

function renderUnion(node, union, depth, dateMode, out) {
  const spouseDots = depth * DOTS_PER_GENERATION + DOTS_PER_GENERATION / 2;

  if (union.total_unions > 1) {
    const dots = ".".repeat(Math.max(spouseDots, 0));
    out.push(
      `<div class="outline-line union-marker"><span class="dots">${esc(dots)}</span>*${ordinal(union.ordinal)} ${esc(spouseRoleLabel(node))} of ${esc(node.name)}:</div>`
    );
  }

  if (union.spouse) {
    out.push(line(spouseDots, "+", union.spouse, marriageOf(union, dateMode), dateMode));
  }

  union.children.forEach((child) => renderDescendant(child, depth + 1, dateMode, out));
}

function renderDescendant(node, depth, dateMode, out) {
  out.push(line(depth * DOTS_PER_GENERATION, `${node.generation} `, node, "", dateMode));
  node.unions.forEach((union) => renderUnion(node, union, depth, dateMode, out));
}

/** Full outline descendant chart (numbered by generation, dot-leader
 * indentation), matching the classic desktop-genealogy-software report
 * layout. `root` is the nested structure returned by
 * GET /api/reports/descendants/{id}. `dateMode` is one of DATE_MODES. */
export function renderOutlineHtml(root, dateMode = DEFAULT_DATE_MODE) {
  const out = [];
  renderDescendant(root, 0, dateMode, out);
  return out.join("");
}

/** Single-lineage "direct descendants" report: root ancestor down to one
 * chosen descendant, with only the spouse relevant to that lineage shown
 * at each generation. `steps` is the array from
 * GET /api/reports/direct-line. `dateMode` is one of DATE_MODES. */
export function renderDirectLineHtml(steps, dateMode = DEFAULT_DATE_MODE) {
  const out = [];
  steps.forEach((step, i) => {
    out.push(line(i * DOTS_PER_GENERATION, `${step.generation} `, step, "", dateMode));
    if (step.spouse) {
      out.push(line(i * DOTS_PER_GENERATION + DOTS_PER_GENERATION / 2, "+", step.spouse, marriageOf(step, dateMode), dateMode));
    }
  });
  return out.join("");
}
