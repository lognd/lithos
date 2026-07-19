// WO-39 deliverable 5: `lithos: check/fmt/rules test` shell out to the
// `regolith` CLI in a VS Code task, using the one problem matcher
// declared in package.json (the same regolith-diag renderer as the LSP
// publishes -- D111, no second severity policy).
//
// WO-120 deliverable 1 extends this with the long-running verbs
// (build --release, ship, preview, optimize, test, health) run as a
// tracked child process instead of a bare task, so their D228 progress
// stream can be parsed and mirrored into VS Code's progress UI
// (`./cli-runner.ts`) -- diagnostics still flow through the existing
// LSP path (AD-7); this module only adds the summary output + progress
// bar, never a second diagnostic renderer.

import * as vscode from "vscode";
import { LithosStatusItem } from "./status";
import { runWithProgress } from "./cli-runner";
import { CensusTreeProvider } from "./census";
import { goToArtifactCommand } from "./goto-artifact";

const SUBCOMMANDS: Record<string, string[]> = {
  "lithos.check": ["check"],
  "lithos.build": ["build"],
  "lithos.fmt": ["fmt"],
  "lithos.rulesTest": ["rules", "test"],
};

/** WO-120 deliverable 1: the long-running verbs that get a progress bar
 * (streamed from `REGOLITH_LOG=DEBUG` stderr) instead of a plain task. */
const PROGRESS_COMMANDS: Record<string, { title: string; args: string[] }> = {
  "lithos.buildRelease": { title: "build --release", args: ["build", "--release"] },
  "lithos.ship": { title: "ship", args: ["ship"] },
  "lithos.preview": { title: "preview", args: ["preview"] },
  "lithos.optimize": { title: "optimize", args: ["optimize"] },
  "lithos.test": { title: "test", args: ["test"] },
  "lithos.health": { title: "health", args: ["health"] },
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

// frob:doc docs/modules/vscode-extension.md#commands
// frob:waive TEST001 reason="VS Code command-registration host API surface (vscode.commands.registerCommand); requires a @vscode/test-electron host harness not wired in this repo, see FROBLEMS.md"
export function registerCommands(
  context: vscode.ExtensionContext,
  status: LithosStatusItem,
  census: CensusTreeProvider,
  channel: vscode.OutputChannel,
): void {
  for (const [command, args] of Object.entries(SUBCOMMANDS)) {
    context.subscriptions.push(
      vscode.commands.registerCommand(command, () => runCliCommand(args, status)),
    );
  }
  for (const [command, { title, args }] of Object.entries(PROGRESS_COMMANDS)) {
    context.subscriptions.push(
      vscode.commands.registerCommand(command, async () => {
        const config = vscode.workspace.getConfiguration("lithos");
        const cli = config.get<string>("cliPath", "regolith");
        const folder = vscode.workspace.workspaceFolders?.[0];
        await runWithProgress(title, cli, args, folder?.uri.fsPath, channel);
        status.refresh();
        census.refresh();
      }),
    );
  }
  context.subscriptions.push(
    vscode.commands.registerCommand("lithos.goToArtifact", goToArtifactCommand),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("lithos.refreshCensus", () => census.refresh()),
  );
}
