//! Pass 3b (WO-29 deliverable 3): the feature/stage program payload
//! field, built from the SAME `then:` claim-scope walk deliverable 2's
//! entity projector reads (`claim_scope::feature_calls_in_decl` --
//! ONE traversal, two consumers, AD-17/NO DUPLICATION).
//!
//! See `regolith_ir::feature_program`'s module doc for the SCOPE NOTE:
//! this emits scalar feature-op parameters only, not sketch/profile
//! geometry (a separate, still-opaque surface, WO-11's territory).

use regolith_ir::{FeatureOp, FeatureProgram, ResolvedFeatureParam};
use regolith_sem::EntityKind;
use regolith_syntax::ast::{AstNode, Decl, File};
use regolith_util::IndexMap;

use crate::claim_scope::{keyword_value, positional_value, FeatureCall};
use crate::entities::decl_is_poisoned;
use crate::output::ParsedFile;

/// Build the (partial) feature program for every declaration across
/// every file whose `then:` claim scopes construct at least one domain
/// feature, in sorted-file then source-decl order (AD-6). A declaration
/// with no feature calls contributes no program (never an empty
/// placeholder -- absence is absence).
#[must_use]
pub fn build_feature_programs(files: &[ParsedFile]) -> Vec<FeatureProgram> {
    let span = tracing::info_span!("lower.feature_program");
    let _enter = span.enter();

    let mut out = Vec::new();
    for pf in files {
        let Some(file) = File::cast(pf.parse.syntax()) else {
            continue;
        };
        for decl in file.decls() {
            if decl_is_poisoned(&decl) {
                continue;
            }
            let Some(name) = decl.name() else { continue };
            let features = feature_ops(&decl);
            if features.is_empty() {
                continue;
            }
            tracing::debug!(
                part = %name,
                features = features.len(),
                "feature program built from then: claim scopes"
            );
            out.push(FeatureProgram {
                part_name: name,
                features,
            });
        }
    }
    out
}

/// Every `FeatureOp` a declaration's `then:` claim scopes construct,
/// mirroring `entities.rs::feature_entities`'s orbit expansion (a
/// `PatternOf<...>(n=N)` call becomes one `FeatureOp` with `count = N`,
/// NOT N separate ops -- the entity projector expands per-instance;
/// this payload keeps the op as one deterministic record with its
/// multiplicity, matching the mech schema's own `PatternOp` shape).
fn feature_ops(decl: &Decl) -> Vec<FeatureOp> {
    let mut out = Vec::new();
    for call in crate::claim_scope::feature_calls_in_decl(decl) {
        let Some(kind) = EntityKind::from_constructor_word(call.effective_constructor()) else {
            continue;
        };
        let kind_word = match kind {
            EntityKind::Hole => "hole",
            EntityKind::Bend => "bend",
            _ => continue,
        };
        out.push(FeatureOp {
            kind: kind_word.to_string(),
            name: call.binding.clone(),
            constructor: call.effective_constructor().to_string(),
            count: u32::try_from(call.count).unwrap_or(u32::MAX),
            params: feature_params(kind_word, &call),
        });
    }
    out
}

/// The well-known scalar params for one feature call, Cause-tagged
/// (INV-21): a param whose spelled text is a recognized value-source
/// keyword (`free`/`derived`/`allocated`, or an `in [..]` planner form)
/// carries that Cause; anything else is `literal` (an ordinary spelled
/// quantity, e.g. `28mm`). Shares the exact measure-key set
/// `entities.rs::feature_measures` uses so the two never disagree on
/// which keys a kind carries.
fn feature_params(kind_word: &str, call: &FeatureCall) -> IndexMap<String, ResolvedFeatureParam> {
    let mut params = IndexMap::new();
    let args = &call.args_text;
    match kind_word {
        "hole" => {
            if let Some(v) = positional_value(args, "dia") {
                params.insert("diameter".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "depth") {
                params.insert("depth".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "edge_distance") {
                params.insert("edge_distance".to_string(), resolved_param(v));
            }
        }
        "bend" => {
            if let Some(v) = keyword_value(args, "angle") {
                params.insert("angle".to_string(), resolved_param(v));
            }
            if let Some(v) = keyword_value(args, "radius") {
                params.insert("radius".to_string(), resolved_param(v));
            }
        }
        _ => {}
    }
    params
}

/// Wrap one spelled param value with its INV-21 Cause, decided
/// structurally from the value-source keyword vocabulary
/// (regolith/03 sec. 2): `free`/`derived`/`allocated` verbatim, an
/// `in [...]` interval as `planner`, anything else `literal`.
fn resolved_param(text: String) -> ResolvedFeatureParam {
    let cause = match text.as_str() {
        "free" => "free",
        "derived" => "derived",
        "allocated" => "allocated",
        _ if text.starts_with('[') => "planner",
        _ => "literal",
    };
    ResolvedFeatureParam {
        text,
        cause: cause.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::build_feature_programs;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    fn parsed(src: &str) -> Vec<ParsedFile> {
        let path = Utf8PathBuf::from("t.hema");
        vec![ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        }]
    }

    #[test]
    fn bore_and_bend_become_cause_tagged_feature_ops() {
        let src = "part p:\n    stage s1:\n        then:\n            pilot = Bore(dia 28mm, depth=12mm)\n    stage s2:\n        then:\n            flange = Bend(edge=cut.top, angle=90deg, radius=free)\n";
        let files = parsed(src);
        let programs = build_feature_programs(&files);
        assert_eq!(programs.len(), 1);
        let program = &programs[0];
        assert_eq!(program.part_name, "p");
        assert_eq!(program.features.len(), 2);

        let hole = program.features.iter().find(|f| f.kind == "hole").unwrap();
        assert_eq!(
            hole.params.get("diameter").map(|p| p.text.as_str()),
            Some("28mm")
        );
        assert_eq!(
            hole.params.get("diameter").map(|p| p.cause.as_str()),
            Some("literal")
        );

        let bend = program.features.iter().find(|f| f.kind == "bend").unwrap();
        assert_eq!(
            bend.params.get("radius").map(|p| p.text.as_str()),
            Some("free")
        );
        assert_eq!(
            bend.params.get("radius").map(|p| p.cause.as_str()),
            Some("free")
        );
    }

    #[test]
    fn patternof_orbit_is_one_op_with_its_count() {
        let src = "part p:\n    stage s1:\n        then:\n            mounts = PatternOf<CBore<M8>>(n=4, rect(100mm x 70mm))\n";
        let files = parsed(src);
        let programs = build_feature_programs(&files);
        let op = &programs[0].features[0];
        assert_eq!(op.count, 4);
        assert_eq!(op.kind, "hole");
    }

    #[test]
    fn a_part_with_no_features_yields_no_program() {
        let src = "part p:\n    x: 1\n";
        let files = parsed(src);
        assert!(build_feature_programs(&files).is_empty());
    }
}
