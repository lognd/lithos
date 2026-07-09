#!/usr/bin/env node
// Bundles the extension entry point into dist/extension.js. Kept
// separate from tsc so `tsc -p ./` still gives full type-checking
// (`npm run compile` runs both).

import { build } from "esbuild";

await build({
  entryPoints: ["src/extension.ts"],
  bundle: true,
  outfile: "dist/extension.js",
  external: ["vscode"],
  format: "cjs",
  platform: "node",
  sourcemap: true,
  target: "node18",
});
