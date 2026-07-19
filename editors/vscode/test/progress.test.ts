// WO-120: the extension-side D228 wire-shape parser must parse
// identically to `python/regolith/progress.py`'s reference parser for
// every case that module's own docstring documents. Pure function,
// no VS Code host needed -- the always-on tier.

import { test } from "node:test";
import * as assert from "node:assert/strict";
import { parseProgressLine, formatProgressMessage, progressIncrement } from "../src/progress";

// frob:tests editors/vscode/src/progress.ts::parseProgressLine kind="unit"
test("parses a determinate progress line", () => {
  const event = parseProgressLine(
    "progress v=1 phase=fleet subject=widget_a done=3 total=15 elapsed=1.234",
  );
  assert.deepEqual(event, {
    v: 1,
    phase: "fleet",
    subject: "widget_a",
    done: 3,
    total: 15,
    elapsed: 1.234,
  });
});

test("parses an indeterminate progress line", () => {
  const event = parseProgressLine(
    "progress v=1 phase=discharge subject=widget_b done=- total=- elapsed=0.001",
  );
  assert.equal(event?.done, null);
  assert.equal(event?.total, null);
});

test("strips ANSI color escapes before matching", () => {
  const line = "\x1b[2mprogress v=1 phase=ship subject=board_c done=1 total=2 elapsed=0.500\x1b[0m";
  const event = parseProgressLine(line);
  assert.equal(event?.phase, "ship");
  assert.equal(event?.subject, "board_c");
});

test("ordinary log lines are not progress records", () => {
  assert.equal(parseProgressLine("DEBUG regolith.compiler: parsed 12 files"), undefined);
  assert.equal(parseProgressLine(""), undefined);
});

// frob:tests editors/vscode/src/progress.ts::formatProgressMessage kind="unit"
test("formatProgressMessage renders determinate and indeterminate forms", () => {
  assert.equal(
    formatProgressMessage({ v: 1, phase: "fleet", subject: "a", done: 3, total: 15, elapsed: 0 }),
    "fleet: a (3/15)",
  );
  assert.equal(
    formatProgressMessage({ v: 1, phase: "fleet", subject: "a", done: null, total: null, elapsed: 0 }),
    "fleet: a",
  );
});

// frob:tests editors/vscode/src/progress.ts::progressIncrement kind="unit"
test("progressIncrement computes a delta percentage, ignoring non-advancing events", () => {
  const event = { v: 1, phase: "fleet", subject: "a", done: 5, total: 10, elapsed: 0 };
  assert.equal(progressIncrement(event, 3), 20);
  assert.equal(progressIncrement(event, 5), undefined);
  assert.equal(
    progressIncrement({ ...event, done: null, total: null }, 0),
    undefined,
  );
});
