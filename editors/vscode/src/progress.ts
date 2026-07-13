// WO-120 deliverable 1: the extension-side parser for the D228/D234.3
// progress wire shape. This is the ONE TypeScript parser site for that
// wire shape (house rule: no duplication) -- it exists only because the
// canonical parser (`python/regolith/progress.py: parse_line`) is a
// Python module the extension cannot import; every field, regex, and
// edge case below mirrors that module's docstring VERBATIM. Any future
// change to the wire shape must update both `progress.py` and this file
// in the same change.
//
// Wire shape (cited verbatim from `python/regolith/progress.py`):
//
//     progress v=<phase> phase=<phase> subject=<subject>
//         done=<done|-> total=<total|-> elapsed=<elapsed>
//
// emitted as ONE line, ANSI SGR escapes (if any) stripped before
// matching. `done`/`total` are `-` together for an indeterminate phase.

/** One parsed progress record (WIRE_VERSION v1, see module docstring). */
export interface ProgressEvent {
  v: number;
  phase: string;
  subject: string;
  done: number | null;
  total: number | null;
  elapsed: number;
}

/** The wire format version this parser understands (bump alongside
 * `PROGRESS_WIRE_VERSION` in `progress.py` on any incompatible change). */
export const PROGRESS_WIRE_VERSION = 1;

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[[0-9;]*m/g;

const LINE_RE =
  /progress v=(\d+) phase=(\S+) subject=(\S+) done=(-|\d+) total=(-|\d+) elapsed=([0-9.]+)/;

/** Parse one stderr line into a {@link ProgressEvent}, or `undefined` when
 * the line carries no progress record (the overwhelming majority of the
 * log stream) -- callers filter, never throw, on ordinary log noise. */
export function parseProgressLine(line: string): ProgressEvent | undefined {
  const plain = line.replace(ANSI_RE, "");
  const m = LINE_RE.exec(plain);
  if (!m) return undefined;
  const [, v, phase, subject, done, total, elapsed] = m;
  return {
    v: Number(v),
    phase,
    subject,
    done: done === "-" ? null : Number(done),
    total: total === "-" ? null : Number(total),
    elapsed: Number(elapsed),
  };
}

/** Human-readable progress fraction/message for a VS Code progress
 * report, e.g. "fleet: widget_a (3/15)" or "discharge: widget_b" for an
 * indeterminate phase. */
export function formatProgressMessage(event: ProgressEvent): string {
  if (event.done === null || event.total === null) {
    return `${event.phase}: ${event.subject}`;
  }
  return `${event.phase}: ${event.subject} (${event.done}/${event.total})`;
}

/** Increment (0-100 scale) this event represents relative to the
 * previous done count for the SAME phase -- `undefined` when the phase
 * is indeterminate (no total to compute a percentage against) or when
 * `total` is not positive. VS Code's `report({ increment })` is a
 * delta, so callers must track `previousDone` themselves per phase. */
export function progressIncrement(
  event: ProgressEvent,
  previousDone: number,
): number | undefined {
  if (event.done === null || event.total === null || event.total <= 0) {
    return undefined;
  }
  const delta = event.done - previousDone;
  if (delta <= 0) return undefined;
  return (delta / event.total) * 100;
}
