// WO-39 deliverable 4: resolve the `regolith-ls` binary to launch.
//
// Order (charter sec. 4 / WO-39 acceptance criteria): an explicit
// `lithos.serverPath` setting, then a bundled per-platform binary shipped
// in the .vsix (`server/<platform>-<arch>/regolith-ls[.exe]`), then
// `$PATH`. If none resolve, the caller degrades to grammar-only
// highlighting with exactly one notice -- never an error loop.

import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

// frob:doc docs/modules/vscode-extension.md#server-path
/** Platform/arch triple used for the bundled binary directory name. */
export function platformDir(): string {
  const plat = process.platform === "win32" ? "windows" : process.platform;
  const arch = process.arch;
  return `${plat}-${arch}`;
}

function bundledServerPath(extensionPath: string): string | undefined {
  const exe = os.platform() === "win32" ? "regolith-ls.exe" : "regolith-ls";
  const candidate = path.join(extensionPath, "server", platformDir(), exe);
  return fs.existsSync(candidate) ? candidate : undefined;
}

function pathLookup(): string | undefined {
  const exe = os.platform() === "win32" ? "regolith-ls.exe" : "regolith-ls";
  const entries = (process.env.PATH ?? "").split(path.delimiter);
  for (const dir of entries) {
    const candidate = path.join(dir, exe);
    if (fs.existsSync(candidate)) return candidate;
  }
  return undefined;
}

// frob:doc docs/modules/vscode-extension.md#server-path
export interface ServerResolution {
  path: string | undefined;
  source: "setting" | "bundled" | "path" | "none";
}

// frob:doc docs/modules/vscode-extension.md#server-path
/** Resolve the server binary, in the documented priority order. */
export function resolveServerPath(
  extensionPath: string,
  settingPath: string | null | undefined,
): ServerResolution {
  if (settingPath) {
    return { path: settingPath, source: "setting" };
  }
  const bundled = bundledServerPath(extensionPath);
  if (bundled) {
    return { path: bundled, source: "bundled" };
  }
  const onPath = pathLookup();
  if (onPath) {
    return { path: onPath, source: "path" };
  }
  return { path: undefined, source: "none" };
}
