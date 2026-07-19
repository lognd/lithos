//! The ONE diagnostic renderer (AD-7): rustc-style constructive output
//! via `annotate-snippets`. No second renderer exists anywhere; the
//! Python side prints these strings verbatim.
//!
//! Regolith reference: `docs/spec/regolith/09-build-and-lockfile.md`
//! sec. 4. Rendering shows the message, the primary and secondary
//! spans as source snippets, the matched-entity table, the 2-3 fixes,
//! and the related cross-references (the "edit blast radius at once").

use annotate_snippets::{Level, Renderer, Snippet};
use anstyle::{AnsiColor, Effects};
use camino::Utf8PathBuf;

use crate::diagnostic::Diagnostic;
use crate::Severity;

/// Whether to emit ANSI colour codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
// frob:doc docs/modules/regolith-diag.md#render
pub enum ColorMode {
    /// Plain text (goldens, `--json` neighbours, non-tty).
    Plain,
    /// ANSI-coloured (interactive terminal).
    Ansi,
}

/// Render one diagnostic to text, reading the referenced source so the
/// snippet lines can be shown.
///
/// `source_of` maps a file path to its full text; the renderer slices
/// the spans out of it. Returned string is the exact bytes printed --
/// the Python side never re-renders (AD-7).
#[must_use]
// frob:doc docs/modules/regolith-diag.md#render
pub fn render(
    diagnostic: &Diagnostic,
    color: ColorMode,
    source_of: &dyn Fn(&camino::Utf8Path) -> Option<String>,
) -> String {
    let code_str = diagnostic.code.to_string();
    let level = match diagnostic.severity {
        Severity::Error => Level::Error,
        Severity::Warning => Level::Warning,
    };

    // Footer lines (matched-entity table, fixes, related cross-refs) are
    // plain notes attached below the snippet -- built as owned strings
    // up front so they outlive the borrows the Message needs.
    let mut footer_lines: Vec<String> = Vec::new();
    for entity in &diagnostic.matched {
        footer_lines.push(format!(
            "matched: {} ({})",
            entity.origin,
            entity.measures.join(", ")
        ));
    }
    for fix in &diagnostic.fixes {
        footer_lines.push(format!("fix: {}", fix.message));
    }
    for related in &diagnostic.related {
        footer_lines.push(format!(
            "related {} at {}:{}-{}: {}",
            related.code, related.span.file, related.span.start, related.span.end, related.note
        ));
    }

    // Spans are grouped into one snippet per file, in first-seen order,
    // with the source text fetched once per file and kept alive for the
    // life of the render.
    let mut files: Vec<Utf8PathBuf> = Vec::new();
    for labeled in &diagnostic.spans {
        if !files.contains(&labeled.span.file) {
            files.push(labeled.span.file.clone());
        }
    }
    let sources: Vec<(Utf8PathBuf, String)> = files
        .into_iter()
        .map(|file| {
            let text = source_of(&file).unwrap_or_default();
            (file, text)
        })
        .collect();

    let mut message = level.title(&diagnostic.message).id(&code_str);
    for (file, source) in &sources {
        let mut snippet = Snippet::source(source.as_str())
            .origin(file.as_str())
            .fold(true);
        for (index, labeled) in diagnostic.spans.iter().enumerate() {
            if labeled.span.file != *file {
                continue;
            }
            // The first attached span is primary (rustc-style: shown at
            // the diagnostic's own severity); the rest are secondary
            // context, shown at Info.
            let annotation_level = if index == 0 { level } else { Level::Info };
            snippet = snippet.annotation(
                annotation_level
                    .span(labeled.span.start..labeled.span.end)
                    .label(&labeled.label),
            );
        }
        message = message.snippet(snippet);
    }
    for line in &footer_lines {
        message = message.footer(Level::Note.title(line));
    }

    let renderer = match color {
        ColorMode::Plain => Renderer::plain(),
        ColorMode::Ansi => styled_renderer(),
    };
    let output = renderer.render(message).to_string();
    output
}

/// The house palette (owner directive: "optional pretty colors for
/// TTY -- conservative, standard 8/16-color ANSI only"): error
/// red+bold, warning yellow+bold, note/help cyan, `file:line:col`
/// locations + line numbers bold, diagnostic codes in the severity
/// color (carried by `error`/`warning` since [`render`] sets the
/// title's `id` to the code string and annotate-snippets colors the id
/// with the level's style), everything else left at the terminal's
/// default (`Style::new()`, no color). Deliberately NOT
/// `Renderer::styled()`'s own default (its `note` is bright green,
/// not cyan) -- this is the ONE renderer's ONE palette (AD-7), spelled
/// out explicitly so it cannot drift from the spec.
fn styled_renderer() -> Renderer {
    Renderer::plain()
        .error(AnsiColor::Red.on_default().effects(Effects::BOLD))
        .warning(AnsiColor::Yellow.on_default().effects(Effects::BOLD))
        .note(AnsiColor::Cyan.on_default())
        .help(AnsiColor::Cyan.on_default())
        .info(AnsiColor::Cyan.on_default())
        .line_no(anstyle::Style::new().effects(Effects::BOLD))
        .emphasis(anstyle::Style::new().effects(Effects::BOLD))
}

/// Render a whole batch (already ordered by the sink) into one string,
/// diagnostics separated by a blank line.
#[must_use]
// frob:doc docs/modules/regolith-diag.md#render
pub fn render_batch(
    diagnostics: &[Diagnostic],
    color: ColorMode,
    source_of: &dyn Fn(&camino::Utf8Path) -> Option<String>,
) -> String {
    diagnostics
        .iter()
        .map(|diagnostic| render(diagnostic, color, source_of))
        .collect::<Vec<_>>()
        .join("\n\n")
}

#[cfg(test)]
mod tests {
    use super::{render, render_batch, ColorMode};
    use crate::code::codes;
    use crate::diagnostic::Diagnostic;
    use crate::span::{LabeledSpan, Span};

    // The acceptance snapshot: three cross-referenced diagnostics
    // rendered as the spec's "edit blast radius at once" shape. Wired
    // now, un-ignored once render() lands (insta snapshot in WO-06).
    // frob:tests crates/regolith-diag/src/render.rs::render_batch kind="unit"
    #[test]
    fn three_cross_referenced_diagnostics_render() {
        let src = "supply v(3.3V)\nborrow rail\nborrow rail\n";
        let source_of = move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let batch = vec![
            Diagnostic::error(codes::BORROW_CONFLICT, "rail borrowed twice").with_span(
                LabeledSpan::new(Span::new("eps.cupr", 15, 26), "first borrow"),
            ),
            Diagnostic::error(codes::BORROW_CONFLICT, "conflicting borrow").with_span(
                LabeledSpan::new(Span::new("eps.cupr", 27, 38), "second borrow"),
            ),
            Diagnostic::error(codes::CAPABILITY_VS_DEMAND, "rail overcommitted").with_span(
                LabeledSpan::new(Span::new("eps.cupr", 0, 14), "supplies 3.3V"),
            ),
        ];
        let out = render_batch(&batch, ColorMode::Plain, &source_of);
        assert!(out.contains("E0302"));
        assert!(out.contains("E0410"));
    }

    // Deliverable 1a: color-off output is untouched by this WO -- every
    // existing golden/snapshot test that renders Plain keeps passing
    // byte-for-byte (no ANSI escape can slip into the Plain path).
    #[test]
    fn plain_output_has_no_ansi_escapes() {
        let src = "supply v(3.3V)\nborrow rail\n";
        let source_of = move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let diagnostic = Diagnostic::error(codes::BORROW_CONFLICT, "rail borrowed twice")
            .with_span(LabeledSpan::new(Span::new("eps.cupr", 15, 26), "here"));
        let out = render(&diagnostic, ColorMode::Plain, &source_of);
        assert!(
            !out.contains('\u{1b}'),
            "plain render must contain no ESC byte: {out:?}"
        );
    }

    // Deliverable 1b: color-on output for an error diagnostic carries
    // the red+bold escape sequences (`\x1b[1m\x1b[31m` -- SGR bold(1)
    // then red(31), the standard 8-color ANSI code, no 256/truecolor
    // SGR like `38;5;` or `38;2;`).
    #[test]
    fn ansi_error_is_red_and_bold() {
        let src = "supply v(3.3V)\nborrow rail\n";
        let source_of = move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let diagnostic = Diagnostic::error(codes::BORROW_CONFLICT, "rail borrowed twice")
            .with_span(LabeledSpan::new(Span::new("eps.cupr", 15, 26), "here"));
        let out = render(&diagnostic, ColorMode::Ansi, &source_of);
        assert!(
            out.contains('\u{1b}'),
            "ansi render must contain ESC: {out:?}"
        );
        assert!(
            out.contains("\u{1b}[1m\u{1b}[31m"),
            "expected bold-red SGR: {out:?}"
        );
        assert!(
            !out.contains("38;5;") && !out.contains("38;2;"),
            "must stay 8/16-color ANSI, no 256/truecolor SGR: {out:?}"
        );
    }

    // Deliverable 1b: color-on output for a warning diagnostic carries
    // the yellow+bold escape (`\x1b[1;33m`).
    #[test]
    fn ansi_warning_is_yellow_and_bold() {
        let src = "supply v(3.3V)\nborrow rail\n";
        let source_of = move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let diagnostic = Diagnostic::warning(codes::UNJOINED_TERMINAL, "dangling terminal")
            .with_span(LabeledSpan::new(Span::new("eps.cupr", 15, 26), "here"));
        let out = render(&diagnostic, ColorMode::Ansi, &source_of);
        assert!(
            out.contains("\u{1b}[1m\u{1b}[33m"),
            "expected bold-yellow SGR: {out:?}"
        );
    }

    // Deliverable 1c: the diagnostic CODE (the `id`, e.g. "E0302")
    // renders in the severity color -- the title line's id inherits
    // the level's style in annotate-snippets, so the same bold-red SGR
    // that wraps the message also wraps (or immediately precedes) the
    // code text; underlines/spans use the same level style (verified
    // indirectly: the whole message uses exactly the error style, never
    // a plain, uncolored code sitting outside any SGR run).
    #[test]
    fn ansi_code_and_underline_carry_severity_color() {
        let src = "supply v(3.3V)\nborrow rail\n";
        let source_of = move |_p: &camino::Utf8Path| -> Option<String> { Some(src.to_string()) };
        let diagnostic = Diagnostic::error(codes::BORROW_CONFLICT, "rail borrowed twice")
            .with_span(LabeledSpan::new(Span::new("eps.cupr", 15, 26), "here"));
        let out = render(&diagnostic, ColorMode::Ansi, &source_of);
        // The code string appears, and at least one red SGR run exists
        // that is not just the title text -- annotate-snippets colors
        // the id + underline carets with the same `error` style.
        assert!(out.contains("E0302"));
        let red_runs = out.matches("\u{1b}[1m\u{1b}[31m").count();
        assert!(
            red_runs >= 2,
            "expected the code AND the underline/title to each open a \
             bold-red run: {out:?}"
        );
    }
}
