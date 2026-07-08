//! The feature/stage program IR (WO-29 deliverable 3): a schema-versioned,
//! `BuildPayload`-carried record of the domain feature ops a part's
//! `then:` claim scopes construct, with resolved scalar parameters and
//! their `Cause` (INV-21).
//!
//! SCOPE NOTE (recorded honestly, not invented around): this is the
//! subset of `python/regolith/realizer/mech/schema.py::FeatureProgram`
//! that `regolith-lower`'s CURRENT structured surface can populate --
//! the scalar measures a feature constructor spells (`diameter`,
//! `depth`, `angle`, `radius`, ...), the same well-known keys deliverable
//! 2's `Hole`/`Bend` entities carry. It does NOT carry sketch/profile
//! geometry (outline points, hole centers in a profile's own plane):
//! that geometry comes from a `profile`/`walk:` declaration, which is a
//! SEPARATE, still-opaque surface (WO-11's Walk -> SketchClosure
//! question, an explicit WO-29 non-goal). `examples/tracks/hematite/
//! sheet_bracket.hema` -- the WO-22 acceptance fixture named in this
//! WO's file -- constructs its `Blank`/`Pierce`/`Bend` features against
//! a `profile BracketFlat` `walk:` body exactly like that, so the
//! REALIZER'S full `FeatureProgram` (real `Sketch` outlines, real
//! `Point2` centers) cannot be produced end to end until that surface
//! is promoted too. This type is the real, schema-versioned producer
//! infrastructure Q2 decided on (a `BuildPayload` field, Rust-authored,
//! `SCHEMA_VERSION`-bumped, `make schema`-regenerated); wiring it to the
//! full realizer contract (`FEATURE_PROGRAM_SCHEMA_VERSION`'s richer
//! shape) is the next dispatch's job once the Walk surface lands.

use regolith_util::IndexMap;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// One resolved scalar parameter a feature constructor spelled, with its
/// `Cause` tag (INV-21). `text` is the raw quantity/keyword text as
/// parsed (e.g. `28mm`, `free`) -- this pass does not unit-convert or
/// numerically resolve it (that is the harness/DFM pack's job); it only
/// records WHAT was spelled and WHY (its provenance class).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct ResolvedFeatureParam {
    /// The raw parameter text as spelled in source.
    pub text: String,
    /// The INV-21 provenance class: `literal` for an ordinary spelled
    /// value, or one of `free`/`derived`/`allocated`/`planner` when the
    /// text itself is a value-source keyword (regolith/03 sec. 2's
    /// vocabulary) rather than a literal quantity.
    pub cause: String,
}

/// One feature op materialized from a `then:` claim-scope constructor
/// call (the SAME structured calls deliverable 2's entity projector
/// reads, `claim_scope::feature_calls_in_decl` -- one traversal, two
/// consumers, AD-17/NO DUPLICATION).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct FeatureOp {
    /// The domain kind this op materializes (`hole`, `bend`) -- mirrors
    /// `regolith_sem::EntityKind`'s two domain variants at the string
    /// level (this type does not depend on `regolith-sem`).
    pub kind: String,
    /// The feature's local binding (`pilot`, `mounts`, `flange`).
    pub name: String,
    /// The constructor verb actually spelled (`Bore`, `CBore`, `Pierce`,
    /// `Bend`, ...) -- a stable discriminant alongside the coarse kind.
    pub constructor: String,
    /// Orbit multiplicity: `n=N` for a `PatternOf<...>(n=N)` orbit, else
    /// 1 (matches deliverable 2's per-instance entity count).
    pub count: u32,
    /// The well-known scalar measures this constructor spelled
    /// (`diameter`/`depth`/`edge_distance` for a hole, `angle`/`radius`
    /// for a bend), each Cause-tagged.
    pub params: IndexMap<String, ResolvedFeatureParam>,
}

/// The (partial, per the scope note above) feature program for one
/// declaration: every `FeatureOp` its `then:` claim scopes construct, in
/// source order (AD-6).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct FeatureProgram {
    /// The declaration name this program belongs to.
    pub part_name: String,
    /// Feature ops in source order.
    pub features: Vec<FeatureOp>,
}
