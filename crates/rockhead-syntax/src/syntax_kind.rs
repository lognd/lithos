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

    // -- nodes (non-terminals) --
    File,
    ImportStmt,
    Decl,
    DeclHeader,
    Field,
    CtorStmt,
    ThenScope,
    RequireClaim,
    BudgetStmt,
    WaiveBlock,
    PolicyBlock,
    LockedBlock,
    Query,
    ValueSource,
    IntervalExpr,
    RangeExpr,
    WindowExpr,
    CountExpr,
    UnitExpr,
    Literal,
    NameRef,
    Path,
    Expr,
    ArgList,
    /// A domain payload parsed as an opaque typed island (WO-05 scope:
    /// structure recorded, semantics deferred to WO-11 / behavioral).
    OpaqueIsland,

    /// Lexer/parser error placeholder; keeps the CST byte-complete.
    Error,

    /// Sentinel upper bound; never constructed. Keep last.
    Tombstone,
}

impl SyntaxKind {
    /// Reconstruct a kind from its `u16` tag (rowan round-trip).
    ///
    /// # Panics
    /// Panics if `raw` exceeds the largest `SyntaxKind` tag -- that is a
    /// compiler bug (a raw value only ever comes from `kind_to_raw`).
    #[must_use]
    pub fn from_raw(raw: u16) -> SyntaxKind {
        assert!(raw <= SyntaxKind::Tombstone as u16, "raw SyntaxKind out of range");
        // SAFETY-free: exhaustive repr(u16) with a checked bound. A
        // match table would desync on every edit; the bound check plus
        // repr(u16) contiguity is the maintained invariant (WO-05 impl
        // may replace with a generated table).
        todo!("STUB WO-05: map checked u16 -> SyntaxKind (transmute w/ bound, or generated table)")
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
        DatumKw, DerivedKw, EventKw, ExternKw, ForbidKw, FreeKw, HostedOnKw, ImageKw, ImplKw,
        ImportKw, InKw, InterfaceKw, LockedKw, MatingKw, MaximizeKw, MinimizeKw, ModelKw,
        NamespaceKw, OnKw, OverrideKw, PartKw, PolicyKw, PreferKw, ProfileKw, ProtocolKw,
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
    fn trivia_is_flagged() {
        assert!(SyntaxKind::Whitespace.is_trivia());
        assert!(SyntaxKind::Comment.is_trivia());
        assert!(!SyntaxKind::PartKw.is_trivia());
    }
}
