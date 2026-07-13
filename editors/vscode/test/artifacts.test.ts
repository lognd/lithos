// WO-120 deliverables 2-4: dist/ resolution reads real files off a
// fabricated calc package -- exercises safeName, findDistProjects,
// findClaimRow, and resolveArtifacts against a temp directory shaped
// like a real `regolith ship` output, never against VS Code APIs.

import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  safeName,
  findDistProjects,
  findClaimRow,
  resolveArtifacts,
  CalcBook,
} from "../src/artifacts";

function makeCalcBook(): CalcBook {
  return {
    sheets: [
      {
        sheet_id: "mass under_limit::abc123def456",
        claim_name: "mass under_limit",
        claim_text: "mass < 5 kg",
        subject_anchor: "Widget",
        subject_ref: "abc123def456",
        model_id: "std.mech.mass",
        model_version: "1",
        citation: "uncited built-in",
        solver: "closed-form",
        tier: "certified",
        attestation: "",
        inputs: [],
        value: "3.2 kg",
        margin: "1.8 kg",
        verdict: "PASS",
        chain: {
          sheet_digest: "d1",
          evidence_hash: "d2",
          subject_ref: "abc123def456",
          payload_refs: [],
          record_pins: [],
        },
      },
    ],
    index: {
      project: "widget-fleet",
      summary: {
        obligations: 2,
        discharged: 1,
        accepted_deviation: 1,
        accepted_rows: 1,
        deferred: 0,
        violated: 0,
      },
      rows: [
        {
          claim_name: "mass under_limit",
          subject_anchor: "Widget",
          content_hash: "h1",
          disposition: "calc_sheet",
          detail: "mass under_limit::abc123def456",
        },
        {
          claim_name: "clearance ok",
          subject_anchor: "Bracket",
          content_hash: "h2",
          disposition: "accepted_deviation",
          detail: "waiver:bracket-clearance memo=acc-2026-07-01",
        },
      ],
    },
  };
}

function withTempDist(fn: (root: string) => void): void {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "lithos-wo120-"));
  try {
    fn(root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test("safeName mirrors calc.py's _safe_name character class", () => {
  assert.equal(safeName("mass under_limit::abc123def456"), "mass_under_limit__abc123def456");
  assert.equal(safeName("a.b-c_D9"), "a.b-c_D9");
});

test("findDistProjects reads calc_book.json from the workspace root", () => {
  withTempDist((root) => {
    fs.mkdirSync(path.join(root, "dist", "calc"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "dist", "calc", "calc_book.json"),
      JSON.stringify(makeCalcBook()),
    );
    const projects = findDistProjects(root);
    assert.equal(projects.length, 1);
    assert.equal(projects[0].calcBook?.index.project, "widget-fleet");
  });
});

test("findDistProjects finds a fleet layout one level down and skips dist/ itself", () => {
  withTempDist((root) => {
    fs.mkdirSync(path.join(root, "widget-a", "dist", "calc"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "widget-a", "dist", "calc", "calc_book.json"),
      JSON.stringify(makeCalcBook()),
    );
    const projects = findDistProjects(root);
    assert.equal(projects.length, 1);
    assert.equal(path.basename(projects[0].root), "widget-a");
  });
});

test("findClaimRow matches on normalized claim_name and resolves the discharging sheet", () => {
  withTempDist((root) => {
    fs.mkdirSync(path.join(root, "dist", "calc"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "dist", "calc", "calc_book.json"),
      JSON.stringify(makeCalcBook()),
    );
    const projects = findDistProjects(root);
    const match = findClaimRow(projects, "  mass  under_limit ");
    assert.ok(match);
    assert.equal(match?.row.disposition, "calc_sheet");
    assert.equal(match?.sheet?.verdict, "PASS");
  });
});

test("findClaimRow returns undefined for a claim never shipped", () => {
  withTempDist((root) => {
    fs.mkdirSync(path.join(root, "dist", "calc"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "dist", "calc", "calc_book.json"),
      JSON.stringify(makeCalcBook()),
    );
    const projects = findDistProjects(root);
    assert.equal(findClaimRow(projects, "nonexistent claim"), undefined);
  });
});

test("resolveArtifacts finds only files that actually exist on disk", () => {
  withTempDist((root) => {
    const distDir = path.join(root, "dist");
    fs.mkdirSync(path.join(distDir, "calc"), { recursive: true });
    fs.mkdirSync(path.join(distDir, "step"), { recursive: true });
    const book = makeCalcBook();
    fs.writeFileSync(path.join(distDir, "calc", "calc_book.json"), JSON.stringify(book));
    fs.writeFileSync(
      path.join(distDir, "calc", `${safeName(book.sheets[0].sheet_id)}.pdf`),
      "fake pdf",
    );
    fs.writeFileSync(path.join(distDir, "step", "Widget.step"), "fake step");
    const projects = findDistProjects(root);
    const match = findClaimRow(projects, "mass under_limit");
    assert.ok(match);
    const targets = resolveArtifacts(match!.project, match!.row, match!.sheet);
    const labels = targets.map((t) => t.label).sort();
    assert.deepEqual(labels, ["calc book (JSON)", "calc sheet (PDF)", "step/Widget.step"]);
  });
});

test("resolveArtifacts for an accepted_deviation row yields no calc sheet target", () => {
  withTempDist((root) => {
    fs.mkdirSync(path.join(root, "dist", "calc"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "dist", "calc", "calc_book.json"),
      JSON.stringify(makeCalcBook()),
    );
    const projects = findDistProjects(root);
    const match = findClaimRow(projects, "clearance ok");
    assert.ok(match);
    assert.equal(match?.sheet, undefined);
    const targets = resolveArtifacts(match!.project, match!.row, match!.sheet);
    assert.equal(targets.length, 0);
  });
});
