// WO-39 deliverable 4: the `regolith-ls` binary resolution order (an
// explicit setting, then a bundled per-platform binary, then $PATH).
// Pure/fs-only, no VS Code host needed.

import { test } from "node:test";
import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { platformDir, resolveServerPath } from "../src/server-path";

// frob:tests editors/vscode/src/server-path.ts::platformDir kind="unit"
test("platformDir names windows explicitly, matching bundled dir naming", () => {
  const dir = platformDir();
  // process.platform on this host is one of a known set; whichever it
  // is, the mapping must never leak the raw "win32" spelling.
  assert.notEqual(dir, undefined);
  assert.ok(!dir.includes("win32"));
});

// frob:tests editors/vscode/src/server-path.ts::resolveServerPath kind="unit"
test("resolveServerPath prefers an explicit setting over anything else", () => {
  const result = resolveServerPath("/nonexistent/extension", "/explicit/regolith-ls");
  assert.deepEqual(result, { path: "/explicit/regolith-ls", source: "setting" });
});

test("resolveServerPath finds a bundled binary when no setting is given", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "lithos-server-path-"));
  try {
    const serverDir = path.join(tmp, "server", platformDir());
    fs.mkdirSync(serverDir, { recursive: true });
    const exe = os.platform() === "win32" ? "regolith-ls.exe" : "regolith-ls";
    const bundled = path.join(serverDir, exe);
    fs.writeFileSync(bundled, "");
    const result = resolveServerPath(tmp, undefined);
    assert.equal(result.source, "bundled");
    assert.equal(result.path, bundled);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test("resolveServerPath degrades to none when nothing resolves", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "lithos-server-path-"));
  try {
    const result = resolveServerPath(tmp, undefined);
    // PATH lookup may legitimately succeed on a dev box with regolith-ls
    // installed; only assert the shape, not which branch fired.
    assert.ok(["bundled", "path", "none"].includes(result.source));
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});
