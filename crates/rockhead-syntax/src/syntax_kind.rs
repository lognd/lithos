//! `SyntaxKind`: the tag on every rowan CST node and token (AD-3). One
//! flat `repr(u16)` enum covering terminals (post-layout tokens and
//! keywords) and non-terminals (grammar nodes), rust-analyzer style.
//!
//! Substrate reference: `docs/substrate/08`, `docs/mech/02`,
//! `docs/elec/07`. The keyword set and node list grow with the grammar
//! (WO-05); adding a construct is: a `SyntaxKind`, a parser production,
//! a typed AST view, and a grammar.ebnf rule.

/// The kind of a CST node or token. `repr(u16)` so rowan can store it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[repr(u16)]
#[allow(missing_docs)] // variant names are self-describing terminals/nodes
pub enum SyntaxKind {
    // -- trivia + layout tokens --
    Whitespace,
    Comment,
    Newline,
    Indent,
    Dedent,

    // -- literal + name tokens --
    Ident,
    Number,
    String,

    // -- punctuation tokens --
    Colon,
    Eq,
    EqEqTok,
    Comma,
    DotDot,
    Dot,
    LParen,
    RParen,
    LBracket,
    RBracket,
    PlusMinus,
    Percent,
    LtEq,
    GtEq,
    Lt,
    Gt,
    Plus,
    Minus,
    Star,
    Slash,

    // -- keyword tokens (contextually recognized from Ident) --
    ImportKw,
    NamespaceKw,
    QuantityKw,
    SignatureKw,
    PartKw,
    ProfileKw,
    InterfaceKw,
    MatingKw,
    AssemblyKw,
    SystemKw,
    BlockKw,
    ImplKw,
    ComponentKw,
    ProtocolKw,
    ComputerKw,
    ImageKw,
    BoardKw,
    TargetKw,
    DatumKw,
    EventKw,
    ThenKw,
    OnKw,
    RequireKw,
    BudgetKw,
    WaiveKw,
    PolicyKw,
    PreferKw,
    ForbidKw,
    MinimizeKw,
    MaximizeKw,
    LockedKw,
    ExternKw,
    ModelKw,
    HostedOnKw,
    InKw,
    FreeKw,
    DerivedKw,
    AllocatedKw,
    WithinKw,
    UseKw,
    OverrideKw,
    ByKw,
    DefaultKw,
    DuringKw,

    // -- nodes (non-terminals) --
    File,
    ImportStmt,
    Decl,
    DeclHeader,
    Field,
    CtorStmt,
    ThenScope,
    RequireClaim,
    ClaimLine,
    DuringClause,
    BudgetStmt,
    WaiveBlock,
    PolicyBlock,
    LockedBlock,
    Query,
    ValueSource,
    CauseValue,
    ToleranceExpr,
    IntervalExpr,
    RangeExpr,
    WindowExpr,
    CountExpr,
    UnitExpr,
    Literal,
    QuantityLit,
    NameRef,
    Path,
    Expr,
    BinExpr,
    UnaryExpr,
    ParenExpr,
    CallExpr,
    ArgList,

    // -- typed domain constructs (WO-05 residual promotion, WO-11 walk) --
    /// `stage <name>: <config>` machining stage (header + stmt-block body).
    StageStmt,
    /// `setup <name>:` work-holding setup nested in a stage.
    SetupStmt,
    /// `impl <Trait>[<generics>] for <target> [as <alias>]:` role binding.
    ImplStmt,
    /// `connect:` mating/connection block (assembly-level).
    ConnectBlock,
    /// `parts:` orbit/instance constructor block (assembly-level).
    PartsBlock,
    /// `zones [over <expr>]:` region-partition block.
    ZonesBlock,
    /// `boundary:` operating-envelope block.
    BoundaryBlock,
    /// `flows:` demand/supply flow block.
    FlowsBlock,
    /// One `a -> b` flow line inside a `flows:` block.
    FlowArrow,
    /// `walk:` profile sketch walk body (WO-11).
    WalkBody,
    /// One walk step (`from <datum>`, `line <dir>`, `close`, ...) (WO-11).
    WalkStep,
    /// `hole <name>:` a named hole sub-profile (WO-11, one nesting level).
    HoleBlock,
    /// `regions:` profile region-expression block (WO-11).
    RegionsBlock,
    /// `constraints:` sketch-constraint block (WO-11).
    ConstraintsBlock,
    /// `exports:` profile export block (WO-11).
    ExportsBlock,
    /// A `policy:` rule line (`prefer ... over ...`, `forbid ...`,
    /// `minimize ...`, `maximize ...`, `use ...`).
    PolicyRule,
    /// A declaration-header generic parameter list (`<screw: thread,
    /// n: int>`); recorded as one node, params not further decomposed.
    GenericParams,
    /// A malformed statement inside a declaration body: an error node
    /// attributed to its enclosing declaration subject (INV-20 gating).
    SubjectError,
    /// A domain payload parsed as an opaque typed island (WO-05 scope:
    /// structure recorded, semantics deferred to WO-11 / behavioral).
    OpaqueIsland,

    /// Lexer/parser error placeholder; keeps the CST byte-complete.
    Error,

    /// Sentinel upper bound; never constructed. Keep last.
    Tombstone,
}

/// Every `SyntaxKind` variant, in declaration (and thus discriminant)
/// order -- the round-trip table for [`SyntaxKind::from_raw`]. Kept as
/// a plain array (no `unsafe`, per house style); the compiler's
/// exhaustiveness elsewhere is what actually guards this against
/// desync (see the type's own variant list).
const ALL_KINDS: &[SyntaxKind] = &[
    SyntaxKind::Whitespace,
    SyntaxKind::Comment,
    SyntaxKind::Newline,
    SyntaxKind::Indent,
    SyntaxKind::Dedent,
    SyntaxKind::Ident,
    SyntaxKind::Number,
    SyntaxKind::String,
    SyntaxKind::Colon,
    SyntaxKind::Eq,
    SyntaxKind::EqEqTok,
    SyntaxKind::Comma,
    SyntaxKind::DotDot,
    SyntaxKind::Dot,
    SyntaxKind::LParen,
    SyntaxKind::RParen,
    SyntaxKind::LBracket,
    SyntaxKind::RBracket,
    SyntaxKind::PlusMinus,
    SyntaxKind::Percent,
    SyntaxKind::LtEq,
    SyntaxKind::GtEq,
    SyntaxKind::Lt,
    SyntaxKind::Gt,
    SyntaxKind::Plus,
    SyntaxKind::Minus,
    SyntaxKind::Star,
    SyntaxKind::Slash,
    SyntaxKind::ImportKw,
    SyntaxKind::NamespaceKw,
    SyntaxKind::QuantityKw,
    SyntaxKind::SignatureKw,
    SyntaxKind::PartKw,
    SyntaxKind::ProfileKw,
    SyntaxKind::InterfaceKw,
    SyntaxKind::MatingKw,
    SyntaxKind::AssemblyKw,
    SyntaxKind::SystemKw,
    SyntaxKind::BlockKw,
    SyntaxKind::ImplKw,
    SyntaxKind::ComponentKw,
    SyntaxKind::ProtocolKw,
    SyntaxKind::ComputerKw,
    SyntaxKind::ImageKw,
    SyntaxKind::BoardKw,
    SyntaxKind::TargetKw,
    SyntaxKind::DatumKw,
    SyntaxKind::EventKw,
    SyntaxKind::ThenKw,
    SyntaxKind::OnKw,
    SyntaxKind::RequireKw,
    SyntaxKind::BudgetKw,
    SyntaxKind::WaiveKw,
    SyntaxKind::PolicyKw,
    SyntaxKind::PreferKw,
    SyntaxKind::ForbidKw,
    SyntaxKind::MinimizeKw,
    SyntaxKind::MaximizeKw,
    SyntaxKind::LockedKw,
    SyntaxKind::ExternKw,
    SyntaxKind::ModelKw,
    SyntaxKind::HostedOnKw,
    SyntaxKind::InKw,
    SyntaxKind::FreeKw,
    SyntaxKind::DerivedKw,
    SyntaxKind::AllocatedKw,
    SyntaxKind::WithinKw,
    SyntaxKind::UseKw,
    SyntaxKind::OverrideKw,
    SyntaxKind::ByKw,
    SyntaxKind::DefaultKw,
    SyntaxKind::DuringKw,
    SyntaxKind::File,
    SyntaxKind::ImportStmt,
    SyntaxKind::Decl,
    SyntaxKind::DeclHeader,
    SyntaxKind::Field,
    SyntaxKind::CtorStmt,
    SyntaxKind::ThenScope,
    SyntaxKind::RequireClaim,
    SyntaxKind::ClaimLine,
    SyntaxKind::DuringClause,
    SyntaxKind::BudgetStmt,
    SyntaxKind::WaiveBlock,
    SyntaxKind::PolicyBlock,
    SyntaxKind::LockedBlock,
    SyntaxKind::Query,
    SyntaxKind::ValueSource,
    SyntaxKind::CauseValue,
    SyntaxKind::ToleranceExpr,
    SyntaxKind::IntervalExpr,
    SyntaxKind::RangeExpr,
    SyntaxKind::WindowExpr,
    SyntaxKind::CountExpr,
    SyntaxKind::UnitExpr,
    SyntaxKind::Literal,
    SyntaxKind::QuantityLit,
    SyntaxKind::NameRef,
    SyntaxKind::Path,
    SyntaxKind::Expr,
    SyntaxKind::BinExpr,
    SyntaxKind::UnaryExpr,
    SyntaxKind::ParenExpr,
    SyntaxKind::CallExpr,
    SyntaxKind::ArgList,
    SyntaxKind::StageStmt,
    SyntaxKind::SetupStmt,
    SyntaxKind::ImplStmt,
    SyntaxKind::ConnectBlock,
    SyntaxKind::PartsBlock,
    SyntaxKind::ZonesBlock,
    SyntaxKind::BoundaryBlock,
    SyntaxKind::FlowsBlock,
    SyntaxKind::FlowArrow,
    SyntaxKind::WalkBody,
    SyntaxKind::WalkStep,
    SyntaxKind::HoleBlock,
    SyntaxKind::RegionsBlock,
    SyntaxKind::ConstraintsBlock,
    SyntaxKind::ExportsBlock,
    SyntaxKind::PolicyRule,
    SyntaxKind::GenericParams,
    SyntaxKind::SubjectError,
    SyntaxKind::OpaqueIsland,
    SyntaxKind::Error,
    SyntaxKind::Tombstone,
];

impl SyntaxKind {
    /// Reconstruct a kind from its `u16` tag (rowan round-trip).
    ///
    /// A plain match table (no `unsafe`, per house style: library crates
    /// avoid `unsafe`); the compiler's exhaustiveness check on the
    /// `SyntaxKind` match is exactly the anti-desync property a
    /// hand-maintained table needs. Replace with a generated table if
    /// this list grows unwieldy.
    ///
    /// # Panics
    /// Panics if `raw` names no `SyntaxKind` variant -- that is a
    /// compiler bug (a raw value only ever comes from `kind_to_raw`).
    #[must_use]
    pub fn from_raw(raw: u16) -> SyntaxKind {
        ALL_KINDS
            .get(usize::from(raw))
            .copied()
            .unwrap_or_else(|| panic!("raw SyntaxKind out of range: {raw}"))
    }

    /// True when this kind is trivia (whitespace or comment): skipped by
    /// the typed AST layer but present in the CST.
    #[must_use]
    pub fn is_trivia(self) -> bool {
        matches!(self, SyntaxKind::Whitespace | SyntaxKind::Comment)
    }
}

/// Map an identifier's text to its keyword kind, or `None` if it is a
/// plain identifier. The one keyword table (no inline literals elsewhere).
#[must_use]
pub fn keyword_kind(text: &str) -> Option<SyntaxKind> {
    use SyntaxKind::{
        AllocatedKw, AssemblyKw, BlockKw, BoardKw, BudgetKw, ByKw, ComponentKw, ComputerKw,
        DatumKw, DefaultKw, DerivedKw, DuringKw, EventKw, ExternKw, ForbidKw, FreeKw, HostedOnKw,
        ImageKw, ImplKw, ImportKw, InKw, InterfaceKw, LockedKw, MatingKw, MaximizeKw, MinimizeKw,
        ModelKw, NamespaceKw, OnKw, OverrideKw, PartKw, PolicyKw, PreferKw, ProfileKw, ProtocolKw,
        QuantityKw, RequireKw, SignatureKw, SystemKw, TargetKw, ThenKw, UseKw, WaiveKw, WithinKw,
    };
    let kind = match text {
        "import" => ImportKw,
        "namespace" => NamespaceKw,
        "quantity" => QuantityKw,
        "signature" => SignatureKw,
        "part" => PartKw,
        "profile" => ProfileKw,
        "interface" => InterfaceKw,
        "mating" => MatingKw,
        "assembly" => AssemblyKw,
        "system" => SystemKw,
        "block" => BlockKw,
        "impl" => ImplKw,
        "component" => ComponentKw,
        "protocol" => ProtocolKw,
        "computer" => ComputerKw,
        "image" => ImageKw,
        "board" => BoardKw,
        "target" => TargetKw,
        "datum" => DatumKw,
        "event" => EventKw,
        "then" => ThenKw,
        "on" => OnKw,
        "require" => RequireKw,
        "budget" => BudgetKw,
        "waive" => WaiveKw,
        "policy" => PolicyKw,
        "prefer" => PreferKw,
        "forbid" => ForbidKw,
        "minimize" => MinimizeKw,
        "maximize" => MaximizeKw,
        "locked" => LockedKw,
        "extern" => ExternKw,
        "model" => ModelKw,
        "hosted_on" => HostedOnKw,
        "in" => InKw,
        "free" => FreeKw,
        "derived" => DerivedKw,
        "allocated" => AllocatedKw,
        "within" => WithinKw,
        "use" => UseKw,
        "override" => OverrideKw,
        "by" => ByKw,
        "default" => DefaultKw,
        "during" => DuringKw,
        _ => return None,
    };
    Some(kind)
}

#[cfg(test)]
mod tests {
    use super::{keyword_kind, SyntaxKind};

    #[test]
    fn keywords_map_and_idents_do_not() {
        assert_eq!(keyword_kind("part"), Some(SyntaxKind::PartKw));
        assert_eq!(keyword_kind("hosted_on"), Some(SyntaxKind::HostedOnKw));
        assert_eq!(keyword_kind("within"), Some(SyntaxKind::WithinKw));
        assert_eq!(keyword_kind("flange"), None);
    }

    #[test]
    fn from_raw_round_trips_every_discriminant() {
        for raw in 0..=(SyntaxKind::Tombstone as u16) {
            assert_eq!(SyntaxKind::from_raw(raw) as u16, raw, "mismatch at {raw}");
        }
    }

    #[test]
    #[should_panic(expected = "out of range")]
    fn from_raw_panics_past_tombstone() {
        let _ = SyntaxKind::from_raw(SyntaxKind::Tombstone as u16 + 1);
    }

    #[test]
    fn trivia_is_flagged() {
        assert!(SyntaxKind::Whitespace.is_trivia());
        assert!(SyntaxKind::Comment.is_trivia());
        assert!(!SyntaxKind::PartKw.is_trivia());
    }
}
