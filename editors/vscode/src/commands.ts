// WO-39 deliverable 5: `lithos: check/build/fmt/rules test` shell out to
// the `regolith` CLI in a VS Code task, using the one problem matcher
// declared in package.json (the same regolith-diag renderer as the LSP
// publishes -- D111, no second severity policy).

import * as vscode from "vscode";
import { LithosStatusItem } from "./status";

const SUBCOMMANDS: Record<string, string[]> = {
  "lithos.check": ["check"],
  "lithos.build": ["build"],
  "lithos.fmt": ["fmt"],
  "lithos.rulesTest": ["rules", "test"],
};

async function runCliCommand(args: string[], status: LithosStatusItem): Promise<void> {
  const config = vscode.workspace.getConfiguration("lithos");
  const cli = config.get<string>("cliPath", "regolith");
  const folder = vscode.workspace.workspaceFolders?.[0];

  const task = new vscode.Task(
    { type: "lithos", command: args[0] },
    folder ?? vscode.TaskScope.Workspace,
    args.join(" "),
    "lithos",
    new vscode.ShellExecution(cli, args, { cwd: folder?.uri.fsPath }),
    ["$regolith"],
  );
  const execution = await vscode.tasks.executeTask(task);
  const disposable = vscode.tasks.onDidEndTask((event) => {
    if (event.execution === execution) {
      status.refresh();
      disposable.dispose();
    }
  });
}

export function registerCommands(
  context: vscode.ExtensionContext,
  status: LithosStatusItem,
): void {
  for (const [command, args] of Object.entries(SUBCOMMANDS)) {
    context.subscriptions.push(
      vscode.commands.registerCommand(command, () => runCliCommand(args, status)),
    );
  }
}
