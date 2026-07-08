//! Pass 3c (WO-29 deliverable 4): the binding-requirement bridge payload
//! field. Projects each `.cupr` `architecture for <Computer>:`
//! declaration's abstract resource blocks (`resources:`/`memories:`/
//! `peripherals:` entries) into `regolith_ir::BlockRequirement` records,
//! reading the RAW capability demand off each entry's `promises:` keyword
//! argument (the typed `KeywordArg` CST node the syntax crate now
//! structures).
//!
//! Source construct (D4 investigation, 2026-07-08): cuprite/05 sec. 2 --
//! "execution resources are abstract blocks with promises" -- and
//! regolith/10 sec. 1's `interface promises`/`interface demands` rows,
//! NOT the `budget` row (a closure-arithmetic ceiling, the wrong
//! vocabulary). Split per Q3/D90: this Rust pass emits raw demands only;
//! Python (`regolith.realizer.elec.binding`) derives the candidate table
//! and the numeric screen. Raw-text discipline mirrors `feature_program`.

use regolith_ir::{BlockRequirement, CapabilityDemand};
use regolith_syntax::ast::{AstNode, File};
use regolith_syntax::cst::SyntaxElement;
use regolith_syntax::cst::SyntaxNode;
use regolith_syntax::syntax_kind::SyntaxKind;

use crate::output::ParsedFile;

/// The header word that introduces a computer-architecture declaration
/// (`architecture for <Computer>:`). Contextual, never a lexer keyword
/// (it parses as an opaque `Ident`-led `Decl`), so it is matched by text.
const ARCHITECTURE_WORD: &str = "architecture";

/// The sub-block headers whose entries are abstract resource blocks
/// carrying `promises:` capability demands (cuprite/05 sec. 2).
const RESOURCE_BLOCKS: [&str; 3] = ["resources", "memories", "peripherals"];

/// The keyword-argument name a resource entry spells its capability
/// demand under (`executor(promises: >= 20Mops ...)`).
const PROMISES_ARG: &str = "promises";

/// Build every [`BlockRequirement`] across every file's
/// `architecture for ...:` declarations, in sorted-file then source
/// order (AD-6). A resource entry without a `promises:` argument (e.g. a
/// bare peripheral demand vector) contributes nothing -- absence is
/// absence, never an empty placeholder.
#[must_use]
pub fn build_block_requirements(files: &[ParsedFile]) -> Vec<BlockRequirement> {
    let span = tracing::info_span!("lower.block_requirement");
    let _enter = span.enter();

    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            let node = decl.syntax();
            if !is_architecture_decl(node) {
                continue;
            }
            let owner = architecture_target(node);
            for demand in resource_requirements(node, &owner) {
                out.push(demand);
            }
        }
    }
    out
}

/// True when a declaration's first significant header token is the
/// contextual `architecture` word.
fn is_architecture_decl(node: &SyntaxNode) -> bool {
    node.children_with_tokens()
        .filter_map(SyntaxElement::into_token)
        .find(|t| !t.kind().is_trivia())
        .is_some_and(|t| t.kind() == SyntaxKind::Ident && t.text() == ARCHITECTURE_WORD)
}

/// The architecture's target name: the `Ident` after the `for` token on
/// the header line (`architecture for FlightCore:` -> `FlightCore`).
/// Falls back to the second header `Ident` when no `for` is present, and
/// to an empty string when the header is malformed (never a panic).
fn architecture_target(node: &SyntaxNode) -> String {
    let header_idents: Vec<_> = node
        .children_with_tokens()
        .filter_map(SyntaxElement::into_token)
        .take_while(|t| t.kind() != SyntaxKind::Colon)
        .filter(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .collect();
    // `architecture for FlightCore` -> ["architecture", "for", "FlightCore"].
    if let Some(pos) = header_idents.iter().position(|w| w == "for") {
        if let Some(name) = header_idents.get(pos + 1) {
            return name.clone();
        }
    }
    header_idents.get(1).cloned().unwrap_or_default()
}

/// Every [`BlockRequirement`] a decl's `resources:`/`memories:`/
/// `peripherals:` sub-blocks yield: one per resource entry whose value is
/// a block-contract call carrying a `promises:` argument.
fn resource_requirements(node: &SyntaxNode, owner: &str) -> Vec<BlockRequirement> {
    let mut out = Vec::new();
    for field in node.children().filter(|c| c.kind() == SyntaxKind::Field) {
        if !RESOURCE_BLOCKS.contains(&field_name(&field).as_str()) {
            continue;
        }
        // Each inner Field is one resource entry (`cpu0: executor(...)`).
        for entry in field.children().filter(|c| c.kind() == SyntaxKind::Field) {
            let block = field_name(&entry);
            let Some(call) = entry.children().find(|c| c.kind() == SyntaxKind::CallExpr) else {
                continue;
            };
            let contract = call_callee(&call);
            let Some(promises) = promises_arg(&call) else {
                continue;
            };
            let demands = parse_demands(&promises);
            if demands.is_empty() {
                continue;
            }
            tracing::debug!(
                owner = %owner,
                block = %block,
                contract = %contract,
                demands = demands.len(),
                "block requirement projected from architecture resource promises"
            );
            out.push(BlockRequirement {
                owner: owner.to_string(),
                block,
                contract,
                demands,
            });
        }
    }
    out
}

/// A `Field` node's leading name token text (the identifier before `:`).
fn field_name(field: &SyntaxNode) -> String {
    field
        .children_with_tokens()
        .filter_map(SyntaxElement::into_token)
        .take_while(|t| t.kind() != SyntaxKind::Colon)
        .find(|t| t.kind() == SyntaxKind::Ident)
        .map(|t| t.text().to_string())
        .unwrap_or_default()
}

/// The callee name of a `CallExpr` (its head `NameRef`/`Path` text): the
/// stdlib block-contract kind (`executor`, `memory`, `mover`).
fn call_callee(call: &SyntaxNode) -> String {
    call.children()
        .find(|c| matches!(c.kind(), SyntaxKind::NameRef | SyntaxKind::Path))
        .map(|n| {
            n.children_with_tokens()
                .filter_map(SyntaxElement::into_token)
                .filter(|t| matches!(t.kind(), SyntaxKind::Ident | SyntaxKind::Dot))
                .map(|t| t.text().to_string())
                .collect::<String>()
        })
        .unwrap_or_default()
}

/// The `promises:` [`SyntaxKind::KeywordArg`] node inside a call's
/// `ArgList`, if present.
fn promises_arg(call: &SyntaxNode) -> Option<SyntaxNode> {
    let arg_list = call.children().find(|c| c.kind() == SyntaxKind::ArgList)?;
    arg_list
        .children()
        .filter(|c| c.kind() == SyntaxKind::KeywordArg)
        .find(|kw| keyword_arg_name(kw) == PROMISES_ARG)
}

/// A `KeywordArg`'s name (its leading `NameRef` text).
fn keyword_arg_name(kw: &SyntaxNode) -> String {
    kw.children()
        .find(|c| c.kind() == SyntaxKind::NameRef)
        .map(|n| n.text().to_string())
        .unwrap_or_default()
}

/// Parse the raw demands off a `promises:` keyword argument's value. The
/// value text after the `:` is split on top-level commas (a single
/// `promises:` may spell several bounds), each bound parsed into a
/// [`CapabilityDemand`] by locating its comparator: text before it is the
/// (possibly empty) capability subject, text after it the raw value. A
/// fragment with no comparator is skipped (not a demand -- never
/// invented).
fn parse_demands(kw: &SyntaxNode) -> Vec<CapabilityDemand> {
    let rhs = keyword_arg_rhs_text(kw);
    let mut out = Vec::new();
    for fragment in split_top_level_commas(&rhs) {
        if let Some(demand) = parse_one_demand(&fragment) {
            out.push(demand);
        }
    }
    out
}

/// The text of a `KeywordArg` after its `:` separator, trimmed (the raw
/// bound spelling, `>= 20Mops f32 sustained`).
fn keyword_arg_rhs_text(kw: &SyntaxNode) -> String {
    let full = kw.text().to_string();
    full.split_once(':')
        .map_or_else(String::new, |(_, rhs)| rhs.trim().to_string())
}

/// Split a bound spelling on commas that are not nested inside parens or
/// brackets (a `[lo, hi]` interval keeps its comma).
fn split_top_level_commas(text: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut depth = 0i32;
    let mut start = 0usize;
    for (i, ch) in text.char_indices() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => depth -= 1,
            ',' if depth == 0 => {
                parts.push(text[start..i].trim().to_string());
                start = i + ch.len_utf8();
            }
            _ => {}
        }
    }
    let tail = text[start..].trim();
    if !tail.is_empty() {
        parts.push(tail.to_string());
    }
    parts
}

/// The comparator spellings a promise bound may use, longest first so
/// `>=` matches before `>`.
const COMPARATORS: [&str; 5] = [">=", "<=", "==", ">", "<"];

/// Parse one bound fragment into a [`CapabilityDemand`], or `None` when it
/// carries no comparator.
fn parse_one_demand(fragment: &str) -> Option<CapabilityDemand> {
    for cmp in COMPARATORS {
        if let Some(idx) = fragment.find(cmp) {
            let capability = fragment[..idx].trim().to_string();
            let value = fragment[idx + cmp.len()..].trim().to_string();
            if value.is_empty() {
                return None;
            }
            return Some(CapabilityDemand {
                capability,
                comparator: cmp.to_string(),
                value,
            });
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::build_block_requirements;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.cupr");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    #[test]
    fn executor_promise_becomes_a_primary_demand() {
        let src = "architecture for FlightCore:\n    resources:\n        cpu0: executor(promises: >= 20Mops f32 sustained)\n";
        let reqs = build_block_requirements(&parsed(src));
        assert_eq!(reqs.len(), 1);
        let req = &reqs[0];
        assert_eq!(req.owner, "FlightCore");
        assert_eq!(req.block, "cpu0");
        assert_eq!(req.contract, "executor");
        assert_eq!(req.demands.len(), 1);
        let d = &req.demands[0];
        assert_eq!(d.capability, "");
        assert_eq!(d.comparator, ">=");
        assert_eq!(d.value, "20Mops f32 sustained");
    }

    #[test]
    fn memory_named_bound_keeps_its_capability_subject() {
        let src = "architecture for A:\n    memories:\n        sram: memory(320kB, promises: latency <= 2 cycles)\n";
        let reqs = build_block_requirements(&parsed(src));
        assert_eq!(reqs.len(), 1);
        let d = &reqs[0].demands[0];
        assert_eq!(reqs[0].contract, "memory");
        assert_eq!(d.capability, "latency");
        assert_eq!(d.comparator, "<=");
        assert_eq!(d.value, "2 cycles");
    }

    #[test]
    fn a_resource_without_promises_yields_no_requirement() {
        let src = "architecture for A:\n    peripherals:\n        buses: spi x 1\n";
        assert!(build_block_requirements(&parsed(src)).is_empty());
    }

    #[test]
    fn non_architecture_decls_are_ignored() {
        let src = "board B:\n    then:\n        u = vendor(x)\n";
        assert!(build_block_requirements(&parsed(src)).is_empty());
    }
}
