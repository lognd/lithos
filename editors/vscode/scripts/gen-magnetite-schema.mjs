#!/usr/bin/env node
// WO-39 deliverable 3: generate the `magnetite.toml` JSON schema from the
// pydantic `Manifest` model (`python/regolith/magnetite/manifest.py`) --
// the ONE model of the manifest shape, per ground rule 7 (no duplication).
//
// Usage: node scripts/gen-magnetite-schema.mjs [--check]

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const extensionRoot = path.resolve(here, "..");
const repoRoot = path.resolve(extensionRoot, "..", "..");
const outPath = path.join(extensionRoot, "schemas", "magnetite.schema.json");

function main() {
  const checkOnly = process.argv.includes("--check");
  const raw = execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      "import json; from regolith.magnetite.manifest import Manifest; print(json.dumps(Manifest.model_json_schema(), indent=2, sort_keys=True))",
    ],
    { cwd: repoRoot, encoding: "utf8" },
  );
  const text = `${raw.trim()}\n`;

  if (checkOnly) {
    let existing = "";
    try {
      existing = readFileSync(outPath, "utf8");
    } catch {
      // missing counts as drift
    }
    if (existing !== text) {
      console.error(`magnetite.toml schema drift: ${outPath} is stale or missing`);
      process.exit(1);
    }
    return;
  }

  writeFileSync(outPath, text);
  console.log(`wrote ${outPath}`);
}

main();
