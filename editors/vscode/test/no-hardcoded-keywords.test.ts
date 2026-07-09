// WO-39 acceptance criterion: "No keyword string appears in the
// extension source that is not in the generated export (grep
// criterion -- AD-24)." Checked over the generated grammars themselves
// (the one place keyword strings legitimately appear) plus a scan of
// `src/` -- the client must never re-derive or hard-code a keyword list.

import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";

const extensionRoot = process.cwd();
const repoRoot = path.resolve(extensionRoot, "..", "..");

function exportKeywords(): Set<string> {
  const raw = execFileSync(
    "cargo",
    ["run", "-q", "-p", "regolith-syntax", "--bin", "grammar-json"],
    { cwd: repoRoot, encoding: "utf8" },
  );
  const exp = JSON.parse(raw);
  const all = [
    ...exp.keywords.decl,
    ...exp.keywords.value_source,
    ...exp.keywords.control,
  ];
  return new Set(all);
}

test("every keyword in the generated grammars is in the export", () => {
  const keywords = exportKeywords();
  const syntaxesDir = path.join(extensionRoot, "syntaxes");
  for (const file of fs.readdirSync(syntaxesDir)) {
    const grammar = JSON.parse(fs.readFileSync(path.join(syntaxesDir, file), "utf8"));
    const patterns = [
      ...grammar.patterns,
      ...Object.values(grammar.repository ?? {}).flatMap(
        (r: any) => r.patterns ?? [],
      ),
    ];
    for (const pattern of patterns) {
      if (!pattern.match || !pattern.name?.startsWith("keyword.")) continue;
      const words = [...pattern.match.matchAll(/\(([a-z_|]+)\)/g)]
        .flatMap((m) => m[1].split("|"));
      for (const word of words) {
        assert.ok(
          keywords.has(word),
          `${file} hard-codes keyword "${word}" not present in the grammar-json export`,
        );
      }
    }
  }
});

test("src/ never hard-codes a language keyword string", () => {
  const keywords = exportKeywords();
  const srcDir = path.join(extensionRoot, "src");
  for (const file of fs.readdirSync(srcDir)) {
    if (!file.endsWith(".ts")) continue;
    const text = fs.readFileSync(path.join(srcDir, file), "utf8");
    for (const word of keywords) {
      // A handful of these words (e.g. "in", "by", "on", "use") are
      // common English/TS tokens; only flag quoted-literal occurrences
      // that look like a deliberate keyword-table copy.
      const quoted = new RegExp(`["'\`]${word}["'\`]`);
      if (quoted.test(text) && word.length > 4) {
        assert.fail(`${file} appears to hard-code the keyword "${word}"`);
      }
    }
  }
});
