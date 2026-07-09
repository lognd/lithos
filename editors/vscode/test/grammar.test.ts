// WO-39 acceptance criterion: "tokenizing one corpus excerpt per
// language matches goldens; regenerating grammars from the export is
// byte-identical (drift check green)." Headless (no VS Code host
// needed) via vscode-textmate + vscode-oniguruma -- the always-on tier
// (the @vscode/test-electron path is the sandbox-gated tier, see
// activation.test.ts).

import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import * as oniguruma from "vscode-oniguruma";
import * as vsctm from "vscode-textmate";

// `npm test` (see package.json) always runs from `editors/vscode/`, so
// `process.cwd()` -- not `__dirname`, which is wrong once compiled
// under `dist-test/test/` -- is the extension root.
const extensionRoot = process.cwd();
const repoRoot = path.resolve(extensionRoot, "..", "..");
const syntaxesDir = path.join(extensionRoot, "syntaxes");
const goldenDir = path.join(extensionRoot, "test", "goldens");

const CORPUS: Record<string, string> = {
  hematite: "examples/tracks/hematite/manifold.hema",
  cuprite: "examples/tracks/cuprite/mux6to64.cupr",
  fluorite: "examples/tracks/fluorite/ullage_press.fluo",
  calcite: "examples/tracks/calcite/pole_barn.calx",
};

async function makeRegistry(): Promise<vsctm.Registry> {
  const wasmPath = require.resolve("vscode-oniguruma/release/onig.wasm");
  const wasmBin = fs.readFileSync(wasmPath).buffer;
  await oniguruma.loadWASM(wasmBin);
  const onigLib = Promise.resolve({
    createOnigScanner: (sources: string[]) => new oniguruma.OnigScanner(sources),
    createOnigString: (s: string) => new oniguruma.OnigString(s),
  });
  return new vsctm.Registry({
    onigLib,
    loadGrammar: async (scopeName: string) => {
      const languageId = scopeName.replace(/^source\./, "");
      const grammarPath = path.join(syntaxesDir, `${languageId}.tmLanguage.json`);
      return JSON.parse(fs.readFileSync(grammarPath, "utf8"));
    },
  });
}

function tokenizeFile(
  grammar: vsctm.IGrammar,
  filePath: string,
): string {
  const source = fs.readFileSync(filePath, "utf8");
  const lines = source.split(/\r?\n/).slice(0, 20); // one excerpt
  let ruleStack = vsctm.INITIAL;
  const out: string[] = [];
  for (const line of lines) {
    const result = grammar.tokenizeLine(line, ruleStack);
    ruleStack = result.ruleStack;
    for (const token of result.tokens) {
      const text = line.substring(token.startIndex, token.endIndex);
      out.push(`${token.scopes.join(" ")} ${JSON.stringify(text)}`);
    }
  }
  return `${out.join("\n")}\n`;
}

test("grammars tokenize one corpus excerpt per language (golden match)", async () => {
  const registry = await makeRegistry();
  for (const [languageId, relPath] of Object.entries(CORPUS)) {
    const grammar = await registry.loadGrammar(`source.${languageId}`);
    assert.ok(grammar, `grammar failed to load for ${languageId}`);
    const actual = tokenizeFile(grammar!, path.join(repoRoot, relPath));
    const goldenPath = path.join(goldenDir, `${languageId}.tokens.golden`);
    const expected = fs.readFileSync(goldenPath, "utf8");
    assert.equal(actual, expected, `token stream drifted for ${languageId}`);
  }
});

test("regenerating grammars from the export is byte-identical (drift check)", () => {
  assert.doesNotThrow(() => {
    execFileSync("node", ["scripts/gen-grammar.mjs", "--check"], {
      cwd: extensionRoot,
      stdio: "pipe",
    });
  });
});
