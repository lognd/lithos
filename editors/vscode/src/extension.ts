// WO-39: the `lithos` VS Code extension. Client half only -- the
// language server (`regolith-ls`, WO-38) is a separate Rust binary this
// module launches over stdio (AD-24: one front end, no logic here).

// frob:waive TEST003 reason="21 real node:test unit tests exist under editors/vscode/test/ (progress/artifacts/server-path) and pass via `node --test`, but frob's TS test collector has no [[test.runner]] entry wired in frob.toml (same root-cause class as the documented crates/** cargo-collector gap, FROBLEMS.md); a package-level integration test would need the same collector wiring to be counted, not a real coverage gap -- see FROBLEMS.md"

import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";
import { resolveServerPath } from "./server-path";
import { LithosStatusItem } from "./status";
import { registerCommands } from "./commands";
import { CensusTreeProvider } from "./census";

const LITHOS_LANGUAGES = ["hematite", "cuprite", "fluorite", "calcite"];

let client: LanguageClient | undefined;
let degradationNoticeShown = false;

function outputChannel(): vscode.OutputChannel {
  return vscode.window.createOutputChannel("lithos");
}

async function startClient(
  context: vscode.ExtensionContext,
  channel: vscode.OutputChannel,
): Promise<void> {
  const config = vscode.workspace.getConfiguration("lithos");
  const settingPath = config.get<string | null>("serverPath", null);
  const resolution = resolveServerPath(context.extensionPath, settingPath);

  if (!resolution.path) {
    // Grammar-only highlighting still works (the TextMate grammars are
    // registered independently of the client); this is the ONE
    // degradation notice the acceptance criteria require -- never an
    // error loop on every activation.
    if (!degradationNoticeShown) {
      degradationNoticeShown = true;
      void vscode.window.showWarningMessage(
        "lithos: no regolith-ls binary found (bundled, $PATH, or lithos.serverPath). " +
          "Syntax highlighting still works; diagnostics/hover/completion are unavailable.",
      );
    }
    channel.appendLine("regolith-ls not found; degrading to grammar-only mode.");
    return;
  }

  channel.appendLine(`launching regolith-ls (${resolution.source}): ${resolution.path}`);

  const serverOptions: ServerOptions = {
    run: { command: resolution.path, transport: TransportKind.stdio },
    debug: { command: resolution.path, transport: TransportKind.stdio },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: LITHOS_LANGUAGES.map((language) => ({
      scheme: "file",
      language,
    })),
    outputChannel: channel,
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher(
        "**/{magnetite.toml,*.hema,*.cupr,*.fluo,*.calx,.regolith/**}",
      ),
    },
  };

  client = new LanguageClient(
    "lithos",
    "lithos language server",
    serverOptions,
    clientOptions,
  );
  await client.start();
  context.subscriptions.push({ dispose: () => void client?.stop() });
}

// frob:doc docs/modules/vscode-extension.md#extension
// frob:waive TEST001 reason="VS Code extension activation host API surface (ExtensionContext, registerTreeDataProvider, LanguageClient.start); requires a @vscode/test-electron host harness not wired in this repo, see FROBLEMS.md"
export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const channel = outputChannel();
  context.subscriptions.push(channel);

  const status = new LithosStatusItem();
  context.subscriptions.push(status);

  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const census = new CensusTreeProvider(workspaceRoot);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("lithosCensus", census),
  );

  registerCommands(context, status, census, channel);

  await startClient(context, channel);
}

// frob:doc docs/modules/vscode-extension.md#extension
// frob:waive TEST001 reason="VS Code extension deactivation host API surface (LanguageClient.stop); requires a @vscode/test-electron host harness not wired in this repo, see FROBLEMS.md"
export async function deactivate(): Promise<void> {
  if (client) {
    await client.stop();
  }
}
