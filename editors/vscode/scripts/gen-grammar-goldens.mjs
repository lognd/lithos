#!/usr/bin/env node
// One-time (and re-run-on-corpus-change) bootstrap for
// `test/goldens/*.tokens.golden`, using the exact same tokenizer as
// `test/grammar.test.ts`. Not part of the test itself -- the test only
// reads and compares.

import * as fs from "node:fs";
import * as path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const oniguruma = require("vscode-oniguruma");
const vsctm = require("vscode-textmate");
const extensionRoot = process.cwd();
const repoRoot = path.resolve(extensionRoot, "..", "..");
const syntaxesDir = path.join(extensionRoot, "syntaxes");
const goldenDir = path.join(extensionRoot, "test", "goldens");

const CORPUS = {
  hematite: "examples/tracks/hematite/manifold.hema",
  cuprite: "examples/tracks/cuprite/mux6to64.cupr",
  fluorite: "examples/tracks/fluorite/ullage_press.fluo",
  calcite: "examples/tracks/calcite/pole_barn.calx",
};

async function makeRegistry() {
  const wasmPath = require.resolve("vscode-oniguruma/release/onig.wasm");
  const wasmBin = fs.readFileSync(wasmPath).buffer;
  await oniguruma.loadWASM(wasmBin);
  const onigLib = Promise.resolve({
    createOnigScanner: (sources) => new oniguruma.OnigScanner(sources),
    createOnigString: (s) => new oniguruma.OnigString(s),
  });
  return new vsctm.Registry({
    onigLib,
    loadGrammar: async (scopeName) => {
      const languageId = scopeName.replace(/^source\./, "");
      const grammarPath = path.join(syntaxesDir, `${languageId}.tmLanguage.json`);
      return JSON.parse(fs.readFileSync(grammarPath, "utf8"));
    },
  });
}

function tokenizeFile(grammar, filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const lines = source.split(/\r?\n/).slice(0, 20);
  let ruleStack = vsctm.INITIAL;
  const out = [];
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

async function main() {
  fs.mkdirSync(goldenDir, { recursive: true });
  const registry = await makeRegistry();
  for (const [languageId, relPath] of Object.entries(CORPUS)) {
    const grammar = await registry.loadGrammar(`source.${languageId}`);
    const text = tokenizeFile(grammar, path.join(repoRoot, relPath));
    const outPath = path.join(goldenDir, `${languageId}.tokens.golden`);
    fs.writeFileSync(outPath, text);
    console.log(`wrote ${outPath}`);
  }
}

main();
