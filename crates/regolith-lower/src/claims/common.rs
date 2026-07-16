use super::{AstNode, Field, Span, SyntaxKind, Unit, Window};

/// The edge ids a transient/volume-budget predicate names (fluorite/03
/// sec. 1, sec. 3 table): `fluids.volume_consumed([<edges>], ...)`'s
/// bracketed edge-id list. Every other `fluids.*` predicate form names
/// no edge this check governs (E0203 scope: WO-32 deliverable 5 flips
/// exactly the `volume_consumed` fixture; a `peak(...)`-wrapped
/// transient claim over a fluid edge is a documented gap -- see the
/// WO-32 D5 close-out note -- left for a follow-up rather than guessed
/// at here).
pub(crate) fn transient_compliance_edges(predicate: &str) -> Vec<String> {
    let Some(call_start) = predicate.find("fluids.volume_consumed(") else {
        return Vec::new();
    };
    let after_call = &predicate[call_start..];
    let Some(lb) = after_call.find('[') else {
        return Vec::new();
    };
    let Some(rb) = after_call[lb..].find(']') else {
        return Vec::new();
    };
    after_call[lb + 1..lb + rb]
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

/// A primary span over a `Field` claim line's full text range.
pub(crate) fn field_span(path: &camino::Utf8Path, line: &Field) -> Span {
    let range = line.syntax().text_range();
    Span::new(path.to_owned(), range.start().into(), range.end().into())
}

/// Find `name(` at the head of `predicate` (after trimming) and return
/// the balanced-paren argument text plus whatever trails the closing
/// paren, or `None` if `predicate` does not start with that exact call.
pub(crate) fn match_call<'a>(predicate: &'a str, name: &str) -> Option<(&'a str, &'a str)> {
    let trimmed = predicate.trim_start();
    let rest = trimmed.strip_prefix(name)?;
    let rest = rest.strip_prefix('(')?;
    let mut depth = 1i32;
    for (idx, ch) in rest.char_indices() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => {
                depth -= 1;
                if depth == 0 {
                    // `ch` here is always `)` (the only way depth can
                    // reach zero starting from a `(`-opened call).
                    let args = &rest[..idx];
                    let after = &rest[idx + 1..];
                    return Some((args, after));
                }
            }
            _ => {}
        }
    }
    None
}

/// Split `args` on top-level commas (depth-0 only -- nested `(...)`/
/// `[...]` commas, e.g. `band=[10Hz, 1kHz]`, stay inside their piece).
pub(crate) fn split_top_level_args(args: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut depth = 0i32;
    let mut start = 0usize;
    for (idx, ch) in args.char_indices() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => depth -= 1,
            ',' if depth == 0 => {
                out.push(args[start..idx].trim().to_string());
                start = idx + 1;
            }
            _ => {}
        }
    }
    let tail = args[start..].trim();
    if !tail.is_empty() {
        out.push(tail.to_string());
    }
    out
}

/// Parse a positional `during <event>` or `within <dur> after <event>`
/// argument into a [`Window`]. Returns `None` for any other shape
/// (e.g. an `at=<location>` tag, which is not a temporal window).
pub(crate) fn parse_window_arg(arg: &str) -> Option<Window> {
    let arg = arg.trim();
    if let Some(event) = arg.strip_prefix("during ") {
        return Some(Window::During(event.trim().to_string()));
    }
    if let Some(rest) = arg.strip_prefix("within ") {
        let (duration, rest) = rest.split_once(" after ")?;
        // The bounding duration resolves through `regolith-qty` like
        // every other bound (`500us` -> `0.0005`), so the orchestrator
        // can read a containment window's limit as a bare numeral.
        return Some(Window::WithinAfter {
            duration: resolve_unit_suffix(duration.trim()),
            event: rest.trim().to_string(),
        });
    }
    if let Some(event) = arg.strip_prefix("until ") {
        return Some(Window::Until(event.trim().to_string()));
    }
    None
}

/// Split a `key=value` argument, or `None` if `arg` carries no `=`.
pub(crate) fn split_kwarg(arg: &str) -> Option<(&str, &str)> {
    let (key, value) = arg.split_once('=')?;
    Some((key.trim(), value.trim()))
}

pub(crate) fn full_predicate_text(field: &Field) -> String {
    // WO-80 deliverable 2: a trailing `, model=<ident>` rung-5 pin is now
    // a typed `ModelPin` child (WO-80 deliverable 1) instead of raw text
    // -- exclude its span here so it never re-enters the comparison RHS
    // (WO-76's audit finding: it used to be swallowed whole into the
    // predicate/rhs text). Every other trailing attribute (`sf=`,
    // `scatter_factor=`) is still un-typed `OpaqueIsland` text and stays
    // exactly as before.
    let mut full = String::new();
    for elem in field.syntax().children_with_tokens() {
        match elem {
            rowan::NodeOrToken::Node(n) if n.kind() == SyntaxKind::ModelPin => {}
            rowan::NodeOrToken::Node(n) => full.push_str(&n.text().to_string()),
            rowan::NodeOrToken::Token(t) => full.push_str(t.text()),
        }
    }
    match full.split_once(':') {
        Some((_, rest)) => rest.trim().to_string(),
        None => String::new(),
    }
}

/// Resolve every unit-suffixed numeral in `text` to its bare SI-base
/// magnitude via `regolith-qty` (regolith/02 sec. 1), leaving every other
/// token (comparators, keywords, entity references, unrecognized suffixes
/// such as `dB` or `%`) exactly as written. This is a textual pass, not a
/// full expression parse (WO-05's typed AST is not yet wired to claim
/// predicates): it finds each `<number><unit-like-suffix>` run and
/// replaces it in place when the suffix is a unit `regolith-qty` accepts.
pub(crate) fn resolve_unit_suffix(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = String::with_capacity(text.len());
    let mut i = 0usize;
    while i < bytes.len() {
        let start = i;
        let mut j = i;
        if j < bytes.len() && (bytes[j] == b'+' || bytes[j] == b'-') {
            j += 1;
        }
        let digits_start = j;
        while j < bytes.len() && bytes[j].is_ascii_digit() {
            j += 1;
        }
        if j < bytes.len() && bytes[j] == b'.' {
            let k = j + 1;
            if k < bytes.len() && bytes[k].is_ascii_digit() {
                j = k;
                while j < bytes.len() && bytes[j].is_ascii_digit() {
                    j += 1;
                }
            }
        }
        if j == digits_start {
            // No digits here: copy one char through and keep scanning.
            let ch_len = text[start..].chars().next().map_or(1, char::len_utf8);
            out.push_str(&text[start..start + ch_len]);
            i = start + ch_len;
            continue;
        }
        let number_end = j;
        // A single space is allowed between the magnitude and its unit
        // (`6800 N`), matching the corpus's spelling of both spaced and
        // unspaced forms (`20mV`).
        let unit_start = if number_end < bytes.len() && bytes[number_end] == b' ' {
            number_end + 1
        } else {
            number_end
        };
        // A unit-like suffix: letters, `/`, `.` (compound units), and
        // digits (unit exponents `m2`), but a digit only continues the
        // run once at least one letter has appeared -- otherwise it is
        // the START of the NEXT number, not part of this unit.
        let mut k = unit_start;
        let mut saw_letter = false;
        loop {
            if k < bytes.len() && (bytes[k].is_ascii_alphabetic()) {
                saw_letter = true;
                k += 1;
            } else if k < bytes.len() && saw_letter && (bytes[k] == b'/' || bytes[k] == b'.') {
                k += 1;
                saw_letter = false; // require a letter again before another digit
            } else if k < bytes.len() && saw_letter && bytes[k].is_ascii_digit() {
                k += 1;
            } else {
                break;
            }
        }
        let suffix = &text[unit_start..k];
        let number_text = &text[start..number_end];
        if !suffix.is_empty() {
            if let (Ok(magnitude), Ok(unit)) =
                (number_text.parse::<f64>(), Unit::parse_expr(suffix))
            {
                let si = magnitude * ratio_f64(unit.scale) + ratio_f64(unit.offset);
                out.push_str(&format_si(si));
                // D256: re-attach the canonical SI-base unit token so
                // downstream (calc sheets, bring-up packs, the sheet
                // renderer) can name what a threshold measures --
                // `45ohm` used to become the bare `45`; it now stays
                // `45ohm` (already base-scale) and `20mV` becomes
                // `0.02V` (the base symbol, not the original prefixed
                // spelling, which would mislabel the reduced value).
                // Every existing bare-numeral Python-side bound reader
                // (`_resolve_bound`/`_split_bound_term`, WO-122;
                // `unit_from_claim`, WO-123) already parses a leading
                // magnitude and an attached trailing unit token as its
                // PRIMARY shape (a unit `Unit::parse_expr` does not
                // recognize, e.g. `rpm`/`dB`, always passed through
                // un-normalized this way), so this is not a new text
                // shape crossing the FFI boundary, only a previously-
                // suppressed case of an existing one.
                out.push_str(&unit.base_symbol());
                i = k;
                continue;
            }
        }
        out.push_str(number_text);
        i = number_end;
    }
    out
}

/// `regolith-qty`'s exact-rational scale/offset as `f64`; the unit table's
/// factors are small SI-prefix ratios, well within `f64`'s exact range.
pub(crate) fn ratio_f64(r: regolith_qty::Scale) -> f64 {
    regolith_qty::unit::ratio_to_f64(r)
}

/// Render a resolved SI magnitude as a compact ASCII numeral (no trailing
/// zeros/point), keeping the lowered obligation text byte-stable and
/// diffable (INV-10 note: the orchestrator hashes this as parsed text, not
/// this string, so a shorter render never perturbs determinism).
pub(crate) fn format_si(value: f64) -> String {
    let mut s = format!("{value:.10}");
    if s.contains('.') {
        while s.ends_with('0') {
            s.pop();
        }
        if s.ends_with('.') {
            s.pop();
        }
    }
    // A nonzero magnitude that rounded to zero at 10 decimals (sub-1e-10
    // SI values: the WO-78 termination claims size capacitors in pF)
    // falls back to Rust's deterministic scientific rendering -- a claim
    // bound is never silently zeroed by formatting.
    if value != 0.0 && (s == "0" || s == "-0") {
        return format!("{value:e}");
    }
    s
}

#[cfg(test)]
mod resolve_unit_suffix_tests {
    // D256: the unit-token repair. `resolve_unit_suffix` used to parse
    // a bound's unit for its SI scale factor and then discard the
    // token (`45ohm` -> `45`); it now re-attaches the canonical SI-base
    // unit so the lowered obligation text still names what it measures.
    use super::resolve_unit_suffix;

    #[test]
    fn preserves_an_unprefixed_unit_token() {
        assert_eq!(resolve_unit_suffix("45ohm"), "45ohm");
    }

    #[test]
    fn reduces_a_prefixed_unit_to_its_base_symbol() {
        // 20mV -> 0.02 V: the base symbol, never the original
        // prefixed spelling (which would mislabel the reduced value).
        assert_eq!(resolve_unit_suffix("20mV"), "0.02V");
    }

    #[test]
    fn preserves_the_unit_on_both_sides_of_a_comparison() {
        assert_eq!(
            resolve_unit_suffix("elec.impedance(refclk) >= 45ohm"),
            "elec.impedance(refclk) >= 45ohm"
        );
    }

    #[test]
    fn leaves_an_unrecognized_suffix_untouched() {
        // `regolith-qty` does not know `rpm` (WO122-F1); the pre-D256
        // behavior (pass the text through unchanged) is preserved.
        assert_eq!(resolve_unit_suffix("9200rpm"), "9200rpm");
    }

    #[test]
    fn leaves_a_bare_dimensionless_bound_unchanged() {
        assert_eq!(resolve_unit_suffix(">= 1.5"), ">= 1.5");
    }

    #[test]
    fn resolves_a_spaced_magnitude_and_unit() {
        assert_eq!(resolve_unit_suffix("6800 N"), "6800N");
    }
}
