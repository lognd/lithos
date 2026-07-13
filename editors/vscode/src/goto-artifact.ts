// WO-120 deliverable 2: `lithos: go to artifact` -- from a claim's
// source text (the current selection, or the line under the cursor),
// resolve and open the calc sheet / drawing / STEP / GLB viewer the
// WO-114 audit index says discharges it. Read-only resolution via
// `./artifacts.ts`; never recomputes a verdict.

import * as vscode from "vscode";
import { findDistProjects, findClaimRow, resolveArtifacts, ArtifactTarget } from "./artifacts";

function claimTextAt(editor: vscode.TextEditor): string {
  if (!editor.selection.isEmpty) {
    return editor.document.getText(editor.selection);
  }
  return editor.document.lineAt(editor.selection.active.line).text;
}

export async function goToArtifactCommand(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!editor || !folder) {
    void vscode.window.showInformationMessage("lithos: open a file in a workspace to go to an artifact.");
    return;
  }
  const needle = claimTextAt(editor).trim();
  if (!needle) {
    void vscode.window.showInformationMessage("lithos: place the cursor on a claim line first.");
    return;
  }
  const projects = findDistProjects(folder.uri.fsPath);
  const match = findClaimRow(projects, needle);
  if (!match) {
    void vscode.window.showWarningMessage(
      `lithos: no shipped claim matches "${needle}" (run "lithos: ship" first, or the claim's name may differ from its source text).`,
    );
    return;
  }
  const { project, row, sheet } = match;
  if (row.disposition === "accepted_deviation") {
    void vscode.window.showInformationMessage(
      `lithos: "${row.claim_name}" is an accepted deviation -- ${row.detail} (see acceptance_ledger.json).`,
    );
  } else if (row.disposition === "deferred" || row.disposition === "violated") {
    void vscode.window.showInformationMessage(
      `lithos: "${row.claim_name}" is ${row.disposition}: ${row.detail}`,
    );
  }
  const targets = resolveArtifacts(project, row, sheet);
  if (targets.length === 0) {
    void vscode.window.showInformationMessage(
      `lithos: "${row.claim_name}" resolved (${row.disposition}) but no artifact files were found under dist/.`,
    );
    return;
  }
  const chosen: ArtifactTarget | undefined =
    targets.length === 1
      ? targets[0]
      : await vscode.window.showQuickPick(
          targets.map((t) => ({ label: t.label, target: t })),
          { placeHolder: `Open which artifact for "${row.claim_name}"?` },
        ).then((pick) => pick?.target);
  if (!chosen) return;
  await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(chosen.filePath));
}
