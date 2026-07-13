// WO-120 deliverable 3: a tree view of per-project discharged/waived
// counts, read verbatim off each `dist/calc/calc_book.json`'s audit
// index summary (WO-114) -- never recomputed. A project's row is
// stale-flagged when its calc book is older than any source file
// (`.hema`/`.cupr`/`.fluo`/`.calx`) under that project root, since a
// stale report is a fact about the workspace, not a verdict change.

import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { findDistProjects, DistProject } from "./artifacts";

const SOURCE_EXTENSIONS = [".hema", ".cupr", ".fluo", ".calx"];

function newestSourceMtime(root: string): number {
  let newest = 0;
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    if (!dir) continue;
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (entry.name === "dist" || entry.name.startsWith(".")) continue;
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(p);
      } else if (SOURCE_EXTENSIONS.includes(path.extname(entry.name))) {
        try {
          const mtime = fs.statSync(p).mtimeMs;
          if (mtime > newest) newest = mtime;
        } catch {
          // Race with a concurrent delete/edit: skip, do not fail the tree.
        }
      }
    }
  }
  return newest;
}

class CensusItem extends vscode.TreeItem {
  constructor(label: string, description: string, tooltip: string, stale: boolean) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.description = description;
    this.tooltip = tooltip;
    this.iconPath = new vscode.ThemeIcon(stale ? "warning" : "verified");
  }
}

/** WO-120 deliverable 3: per-project discharged/waived/deferred counts
 * in a tree view, sourced from each project's own shipped audit index. */
export class CensusTreeProvider implements vscode.TreeDataProvider<CensusItem> {
  private readonly emitter = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly workspaceRoot: string | undefined) {}

  refresh(): void {
    this.emitter.fire();
  }

  getTreeItem(element: CensusItem): vscode.TreeItem {
    return element;
  }

  getChildren(): CensusItem[] {
    if (!this.workspaceRoot) return [];
    const projects = findDistProjects(this.workspaceRoot).filter((p) => p.calcBook);
    if (projects.length === 0) {
      return [
        new CensusItem(
          "no shipped packages",
          "",
          'Run "lithos: ship" to populate dist/calc/audit_index.json.',
          false,
        ),
      ];
    }
    return projects.map((project) => this.itemFor(project));
  }

  private itemFor(project: DistProject): CensusItem {
    const book = project.calcBook!;
    const s = book.index.summary;
    const label = path.basename(project.root) || project.root;
    const description = `${s.discharged}/${s.obligations} discharged, ${s.accepted_deviation} waived, ${s.deferred} deferred`;
    const reportMtime = project.calcBookPath ? fs.statSync(project.calcBookPath).mtimeMs : 0;
    const stale = newestSourceMtime(project.root) > reportMtime;
    const tooltip = stale
      ? "STALE: a source file changed after this calc book was shipped -- re-run \"lithos: ship\"."
      : `Project: ${book.index.project}\nBalanced: ${
          s.discharged + s.accepted_rows + s.deferred + s.violated === s.obligations
        }`;
    return new CensusItem(label, stale ? `${description} (stale)` : description, tooltip, stale);
  }
}
