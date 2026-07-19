// WO-39 deliverable 5: the status-bar item, reading obligation counts /
// evidence state from build artifacts (same read-only artifact rule as
// the server, D111 -- never a guess, never invoking Python directly).

import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";

interface EvidenceSummary {
  obligations: number;
  discharged: number;
}

/** Best-effort read of `.regolith/` evidence counts; undefined when the
 * workspace has never been built (mirrors the server's hover degradation:
 * missing artifacts are a fact, not an error). */
function readEvidenceSummary(workspaceRoot: string): EvidenceSummary | undefined {
  const evidenceDir = path.join(workspaceRoot, ".regolith");
  if (!fs.existsSync(evidenceDir)) return undefined;
  try {
    const files = fs.readdirSync(evidenceDir).filter((f) => f.endsWith(".json"));
    let obligations = 0;
    let discharged = 0;
    for (const file of files) {
      const raw = JSON.parse(fs.readFileSync(path.join(evidenceDir, file), "utf8"));
      if (Array.isArray(raw?.obligations)) {
        obligations += raw.obligations.length;
        discharged += raw.obligations.filter(
          (o: { status?: string }) => o?.status === "discharged",
        ).length;
      }
    }
    return { obligations, discharged };
  } catch {
    // A malformed or partial artifact is read-only input, not a hard
    // error surfaced to the user; the status item just falls back to
    // "no build artifacts".
    return undefined;
  }
}

// frob:doc docs/modules/vscode-extension.md#status
export class LithosStatusItem implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  // frob:doc docs/modules/vscode-extension.md#status
  // frob:waive TEST001 reason="VS Code status-bar host API surface (vscode.window.createStatusBarItem); requires a @vscode/test-electron host harness not wired in this repo, see FROBLEMS.md"
  constructor() {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this.item.name = "lithos build state";
    this.item.command = "lithos.check";
    this.refresh();
    this.item.show();
  }

  // frob:doc docs/modules/vscode-extension.md#status
  // frob:waive TEST001 reason="VS Code status-bar host API surface (vscode.workspace.workspaceFolders, StatusBarItem.text); requires a @vscode/test-electron host harness not wired in this repo, see FROBLEMS.md"
  refresh(): void {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
      this.item.text = "$(circle-slash) lithos";
      this.item.tooltip = "No workspace folder open.";
      return;
    }
    const summary = readEvidenceSummary(folder.uri.fsPath);
    if (!summary) {
      this.item.text = "$(circle-outline) lithos: no build artifacts";
      this.item.tooltip = "Run \"lithos: build\" to populate .regolith/.";
      return;
    }
    this.item.text = `$(check) lithos: ${summary.discharged}/${summary.obligations} discharged`;
    this.item.tooltip = "Obligation status read from .regolith/ (click to re-check).";
  }

  // frob:doc docs/modules/vscode-extension.md#status
  // frob:waive TEST001 reason="trivial VS Code Disposable passthrough (StatusBarItem.dispose); VS Code host API contract method"
  dispose(): void {
    this.item.dispose();
  }
}
