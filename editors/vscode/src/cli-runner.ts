// WO-120 deliverable 1: run a long `regolith` verb (build/ship/preview/
// optimize/test/health) as a child process with `REGOLITH_LOG=DEBUG` so
// the D228 progress channel is live on its stderr, parse that stream
// through the ONE parser site (`./progress.ts`), and mirror it into VS
// Code's work-done progress UI (`vscode.window.withProgress`). Full
// stdout/stderr always lands in the output channel (the summary view);
// diagnostics themselves keep flowing through the existing LSP path
// (AD-7 -- this module never renders a diagnostic, only progress text).

import * as vscode from "vscode";
import { spawn } from "node:child_process";
import { parseProgressLine, formatProgressMessage, progressIncrement } from "./progress";

export interface CliRunResult {
  exitCode: number | null;
  cancelled: boolean;
}

/** Spawn `<cliPath> <args>` in `cwd` with progress logging enabled,
 * streaming `$/progress`-equivalent updates into a VS Code notification
 * progress bar while the command runs. Resolves once the process exits
 * or the user cancels (in which case the child is killed). */
export async function runWithProgress(
  title: string,
  cliPath: string,
  args: string[],
  cwd: string | undefined,
  channel: vscode.OutputChannel,
): Promise<CliRunResult> {
  channel.appendLine(`$ ${cliPath} ${args.join(" ")}`);
  return vscode.window.withProgress<CliRunResult>(
    {
      location: vscode.ProgressLocation.Notification,
      title: `lithos: ${title}`,
      cancellable: true,
    },
    (progress, token) =>
      new Promise<CliRunResult>((resolve) => {
        const child = spawn(cliPath, args, {
          cwd,
          env: { ...process.env, REGOLITH_LOG: "DEBUG" },
        });
        const doneByPhase = new Map<string, number>();
        let cancelled = false;

        token.onCancellationRequested(() => {
          cancelled = true;
          child.kill();
        });

        let stderrTail = "";
        child.stderr.on("data", (chunk: Buffer) => {
          const text = chunk.toString("utf8");
          channel.append(text);
          stderrTail += text;
          const lines = stderrTail.split("\n");
          stderrTail = lines.pop() ?? "";
          for (const line of lines) {
            const event = parseProgressLine(line);
            if (!event) continue;
            const previous = doneByPhase.get(event.phase) ?? 0;
            const increment = progressIncrement(event, previous);
            if (event.done !== null) doneByPhase.set(event.phase, event.done);
            progress.report({ message: formatProgressMessage(event), increment });
          }
        });
        child.stdout.on("data", (chunk: Buffer) => {
          channel.append(chunk.toString("utf8"));
        });
        child.on("error", (err) => {
          channel.appendLine(`lithos: failed to launch ${cliPath}: ${err.message}`);
          resolve({ exitCode: null, cancelled });
        });
        child.on("close", (code) => {
          channel.appendLine(`lithos: ${title} exited ${code ?? "(killed)"}`);
          resolve({ exitCode: code, cancelled });
        });
      }),
  );
}
