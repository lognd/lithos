#!/usr/bin/env node
// WO-39 deliverable 2: generate the per-language TextMate grammars from
// the ONE table export (`regolith-syntax grammar-json`, deliverable 1).
// AD-24: no hand-maintained grammar; the drift check in
// `check-grammar-drift.mjs` regenerates and diffs against the checked-in
// files, exactly like `_schema/`.
//
// Usage: node scripts/gen-grammar.mjs [--check]

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const extensionRoot = path.resolve(here, "..");
const repoRoot = path.resolve(extensionRoot, "..", "..");
const syntaxesDir = path.join(extensionRoot, "syntaxes");

function loadExport() {
  const raw = execFileSync(
    "cargo",
    ["run", "-q", "-p", "regolith-syntax", "--bin", "grammar-json"],
    { cwd: repoRoot, encoding: "utf8" },
  );
  return JSON.parse(raw);
}

function escapeRegexWords(words) {
  return words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
}

function keywordPattern(words, scope) {
  if (words.length === 0) return null;
  return {
    name: scope,
    match: `\\b(${escapeRegexWords(words).join("|")})\\b`,
  };
}

function buildGrammar(languageId, extension, exp) {
  const patterns = [
    { include: "#comments" },
    { include: "#strings" },
    { include: "#numbers-with-units" },
    keywordPattern(exp.keywords.decl, "keyword.other.decl.lithos"),
    keywordPattern(
      exp.keywords.value_source,
      "keyword.other.value-source.lithos",
    ),
    keywordPattern(exp.keywords.control, "keyword.control.lithos"),
  ].filter(Boolean);

  return {
    $schema:
      "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
    // GENERATED FILE -- DO NOT EDIT.
    // Regenerate: `npm run gen:grammar` in editors/vscode/.
    // Source of truth: `crates/regolith-syntax` (WO-39 deliverable 1/2,
    // AD-24). Hand-written parts are limited to the structural scopes
    // (comments, strings, numbers-with-units) below.
    generated: `regolith-syntax grammar-json -- ${exp.generated_by}`,
    name: languageId,
    scopeName: `source.${languageId}`,
    fileTypes: [extension],
    patterns,
    repository: {
      comments: {
        patterns: [
          {
            name: "comment.line.number-sign.lithos",
            match: `${exp.comment.line}.*$`,
          },
        ],
      },
      strings: {
        patterns: [
          {
            name: "string.quoted.double.lithos",
            begin: '"',
            end: '"',
            patterns: [{ name: "constant.character.escape.lithos", match: "\\\\." }],
          },
        ],
      },
      "numbers-with-units": {
        patterns: [
          {
            // number literal, optionally followed by a unit ident
            // (unit suffixes lex as a following Ident -- token.rs).
            name: "constant.numeric.lithos",
            match: `(${exp.number_regex})(\\s*(${exp.ident_regex}))?`,
            captures: {
              1: { name: "constant.numeric.lithos" },
              3: { name: "keyword.other.unit.lithos" },
            },
          },
        ],
      },
    },
  };
}

function main() {
  const checkOnly = process.argv.includes("--check");
  const exp = loadExport();
  mkdirSync(syntaxesDir, { recursive: true });

  let drift = false;
  for (const { id, extension } of exp.languages) {
    const grammar = buildGrammar(id, extension, exp);
    const text = `${JSON.stringify(grammar, null, 2)}\n`;
    const outPath = path.join(syntaxesDir, `${id}.tmLanguage.json`);

    if (checkOnly) {
      let existing = "";
      try {
        existing = readFileSync(outPath, "utf8");
      } catch {
        // missing file counts as drift
      }
      if (existing !== text) {
        console.error(`grammar drift: ${outPath} is stale or missing`);
        drift = true;
      }
    } else {
      writeFileSync(outPath, text);
      console.log(`wrote ${outPath}`);
    }
  }

  if (checkOnly && drift) {
    console.error(
      "Generated grammars are out of date. Run `npm run gen:grammar` and commit the result.",
    );
    process.exit(1);
  }
}

main();
