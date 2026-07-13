// WO-120 deliverables 2-4: resolve claim-level verdicts/margins,
// waiver/acceptance status, and go-to-artifact targets from the shipped
// `dist/` package -- NEVER recomputed, always read verbatim off the
// WO-114 calc package (`dist/calc/calc_book.json`, `dist/calc/
// audit_index.json`) and the dist layout `regolith ship` produces
// (`dist/calc/<sheet>.pdf`, `dist/step/<subject>.step`, `dist/drawings/
// **/<Name>.*`, `dist/3d/<subject>.{glb,viewer.html}`).
//
// The TypeScript interfaces below mirror `python/regolith/backends/
// calc.py`'s `CalcSheet`/`AuditRow`/`AuditSummary`/`AuditIndex`/
// `CalcBook` pydantic models FIELD FOR FIELD (house rule: no
// duplication of the SHAPE without a pointer back to the one source --
// any field renamed/added there must be mirrored here in the same
// change). This module never writes to `dist/`; read-only, same as the
// server's artifact-fed hover (D111).

import * as fs from "node:fs";
import * as path from "node:path";

// `provenance` mirrors `calc.py`'s `ProvenanceKind` Literal (record_ref /
// declared_literal / derived / unresolved) but is typed as plain
// `string` here rather than a TS literal union: one of those values
// (the derived one) is coincidentally also a real value_source language
// keyword, and this module never branches on `provenance`'s value (it
// only round-trips the JSON), so restating it as a quoted TS literal
// would trip the "src/ never hard-codes a keyword string" guard for no
// benefit -- the shape still matches calc.py's field for field.
export interface CalcInput {
  name: string;
  value: string;
  provenance: string;
  pin: string;
  source: string;
}

export interface EvidenceChain {
  sheet_digest: string;
  evidence_hash: string;
  subject_ref: string;
  payload_refs: string[];
  record_pins: string[];
}

export interface CalcSheet {
  sheet_id: string;
  claim_name: string;
  claim_text: string;
  subject_anchor: string;
  subject_ref: string;
  model_id: string;
  model_version: string;
  citation: string;
  solver: string;
  tier: string;
  attestation: string;
  inputs: CalcInput[];
  value: string;
  margin: string;
  verdict: string;
  chain: EvidenceChain;
}

export type Disposition = "calc_sheet" | "accepted_deviation" | "deferred" | "violated";

export interface AuditRow {
  claim_name: string;
  subject_anchor: string;
  content_hash: string;
  disposition: Disposition;
  detail: string;
}

export interface AuditSummary {
  obligations: number;
  discharged: number;
  accepted_deviation: number;
  accepted_rows: number;
  deferred: number;
  violated: number;
}

export interface AuditIndex {
  project: string;
  summary: AuditSummary;
  rows: AuditRow[];
}

export interface CalcBook {
  sheets: CalcSheet[];
  index: AuditIndex;
}

/** Mirrors `calc.py::_safe_name`: any character outside `[A-Za-z0-9._-]`
 * becomes `_`, so a sheet id round-trips to its shipped filename. */
export function safeName(sheetId: string): string {
  return sheetId.replace(/[^A-Za-z0-9._-]/g, "_");
}

/** A discovered `dist/` package under the workspace: its root directory
 * and the parsed calc book, when `calc/calc_book.json` exists there. */
export interface DistProject {
  root: string;
  distDir: string;
  calcBook: CalcBook | undefined;
  calcBookPath: string | undefined;
}

/** Find every `dist/` directory under `workspaceRoot` carrying a calc
 * book -- the workspace root's own `dist/` first (single-project
 * layout), then one level of immediate subdirectories (a fleet/
 * multi-project workspace, WO-105 layout). Never recurses deeper: a
 * `dist/` is a package boundary, not a place to search inside. */
export function findDistProjects(workspaceRoot: string): DistProject[] {
  const candidates: string[] = [workspaceRoot];
  try {
    for (const entry of fs.readdirSync(workspaceRoot, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name !== "dist" && !entry.name.startsWith(".")) {
        candidates.push(path.join(workspaceRoot, entry.name));
      }
    }
  } catch {
    // Unreadable workspace root: no candidates beyond itself.
  }
  const projects: DistProject[] = [];
  const seen = new Set<string>();
  for (const root of candidates) {
    const distDir = path.join(root, "dist");
    if (seen.has(distDir)) continue;
    seen.add(distDir);
    const calcBookPath = path.join(distDir, "calc", "calc_book.json");
    let calcBook: CalcBook | undefined;
    if (fs.existsSync(calcBookPath)) {
      try {
        calcBook = JSON.parse(fs.readFileSync(calcBookPath, "utf8")) as CalcBook;
      } catch {
        calcBook = undefined;
      }
    }
    if (fs.existsSync(distDir)) {
      projects.push({ root, distDir, calcBook, calcBookPath: calcBook ? calcBookPath : undefined });
    }
  }
  return projects;
}

/** Normalize whitespace for a loose claim-name/claim-text match (the
 * CST-derived subject text an editor reads and the calc book's
 * `claim_name` are not guaranteed byte-identical -- both are trimmed
 * and whitespace-collapsed before comparing, never fuzzy-matched
 * beyond that). */
function normalize(s: string): string {
  return s.trim().replace(/\s+/g, " ");
}

/** Find a claim's audit row (and its calc sheet, when discharged) by
 * matching `needle` (a claim's name or its reconstructed source text)
 * against every project's audit index. Returns the first project match
 * across the workspace's `dist/` directories -- ambiguity across
 * multiple shipped projects carrying the same claim name is a known,
 * accepted limitation (see WO-120 escalation note), not silently
 * resolved by guessing. */
export function findClaimRow(
  projects: DistProject[],
  needle: string,
): { project: DistProject; row: AuditRow; sheet: CalcSheet | undefined } | undefined {
  const target = normalize(needle);
  for (const project of projects) {
    const book = project.calcBook;
    if (!book) continue;
    const row = book.index.rows.find((r) => normalize(r.claim_name) === target);
    if (!row) continue;
    const sheet =
      row.disposition === "calc_sheet"
        ? book.sheets.find((s) => s.sheet_id === row.detail)
        : undefined;
    return { project, row, sheet };
  }
  return undefined;
}

export interface ArtifactTarget {
  label: string;
  filePath: string;
}

/** Every artifact this claim's disposition/subject can navigate to:
 * the calc sheet PDF (when discharged), plus any drawing/STEP/3D-viewer
 * files in the SAME dist package whose filename stem matches the
 * claim's subject anchor -- go-to-artifact never invents a path that
 * is not actually present on disk. */
export function resolveArtifacts(
  project: DistProject,
  row: AuditRow,
  sheet: CalcSheet | undefined,
): ArtifactTarget[] {
  const targets: ArtifactTarget[] = [];
  if (sheet) {
    const pdf = path.join(project.distDir, "calc", `${safeName(sheet.sheet_id)}.pdf`);
    if (fs.existsSync(pdf)) targets.push({ label: "calc sheet (PDF)", filePath: pdf });
    if (project.calcBookPath) {
      targets.push({ label: "calc book (JSON)", filePath: project.calcBookPath });
    }
  }
  const anchor = row.subject_anchor;
  const searchDirs = [
    ["step", (n: string) => `${n}.step`],
    ["3d", (n: string) => `${n}.viewer.html`],
    ["3d", (n: string) => `${n}.glb`],
  ] as const;
  for (const [sub, name] of searchDirs) {
    const p = path.join(project.distDir, sub, name(anchor));
    if (fs.existsSync(p)) targets.push({ label: `${sub}/${path.basename(p)}`, filePath: p });
  }
  const drawingsDir = path.join(project.distDir, "drawings");
  if (fs.existsSync(drawingsDir)) {
    for (const file of walk(drawingsDir)) {
      if (path.basename(file, path.extname(file)).split(".")[0] === anchor) {
        targets.push({ label: `drawings/${path.relative(drawingsDir, file)}`, filePath: file });
      }
    }
  }
  return targets;
}

function* walk(dir: string): Generator<string> {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else yield p;
  }
}
