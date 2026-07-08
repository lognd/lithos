//! `SyntaxKind`: the tag on every rowan CST node and token (AD-3). One
//! flat `repr(u16)` enum covering terminals (post-layout tokens and
//! keywords) and non-terminals (grammar nodes), rust-analyzer style.
//!
//! Regolith reference: `docs/regolith/08`, `docs/hematite/02`,
//! `docs/cuprite/07`. The keyword set and node list grow with the grammar
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
    AtTok,
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
    /// A use-site generic instantiation (`TappedHole<M3>`,
    /// `PatternOf<Decoder<3, 8>>`): a head [`SyntaxKind::NameRef`]/
    /// [`SyntaxKind::Path`] followed by a typed [`SyntaxKind::GenericArgs`]
    /// argument list. Recognized ONLY when `<` is glued to the head name
    /// and the angle group scans as a balanced, type-like argument list
    /// (so claim comparisons `a < b` stay `BinExpr`); INV-11 use sites.
    InstExpr,
    /// A use-site generic-argument list (`<M3>`, `<3, 8>`,
    /// `<TappedHole<screw>, n, along>`): balanced angle nesting, nested
    /// instantiations promoted to [`SyntaxKind::InstExpr`]. Mirrors the
    /// decl-header [`SyntaxKind::GenericParams`] on the use side.
    GenericArgs,

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

    // -- typed ownership/region/symmetry statements (WO-05 residual
    //    promotion, WO-19 delta/region population; INV-04/05/23) --
    /// A single-line ownership statement: `bind <entity>` (a borrow --
    /// query consumption / role binding) or `modify <entity>` (a feature
    /// transferring ownership). The leading verb token distinguishes the
    /// two; feeds `PredictedDelta.modifies` + `BorrowTable` (INV-05).
    OwnershipStmt,
    /// A single-line region statement: `region <name> [exclusion|
    /// arbitration]` / `keepout <name>` (a first-class owned region
    /// entity) or `route <name> (into|join) <region>` (a placement/route
    /// touching a region). Feeds `EntityKind::Region` +
    /// `PredictedDelta.regions_touched` (INV-23).
    RegionStmt,
    /// A single-line symmetry statement: `pattern <name> (circular|
    /// linear) <n>` (declares an orbit contribution), `break <pattern>`
    /// (a symmetry-breaking delta), `any <pattern>` (an orbit-extension
    /// request), or the neutral `symmetric(...)`/`mirror ...`/`flip ...`
    /// promotions. Feeds `PredictedDelta.symmetry` + `OrbitTable`
    /// (INV-04). The leading verb token distinguishes them.
    SymmetryStmt,
    /// A single-line query statement (WO-08 resolution wiring, INV-06/18):
    /// `feature <name>` declares a named entity into the enclosing scope's
    /// entity-DB snapshot, and `refer <name>` is a `.only` query resolved
    /// against that scope-entry snapshot. The leading verb distinguishes
    /// them; the lowering pass (`regolith-lower::query`) reads the verb and
    /// argument name back off the node's tokens to build the snapshot and
    /// resolve the reference (E0301 on over/under-match; a sibling scope's
    /// feature is not name-resolvable, so a cross-scope `refer` under-
    /// matches -- snapshot isolation).
    QueryStmt,
    /// A single-line hint statement: `@hint(<free text>)` (regolith/12
    /// rung 3). Recognized at statement-start by its leading `@` sigil and
    /// swallowed whole. It is verdict-inert BY CONSTRUCTION: the lowering
    /// passes never read it, so it contributes no entity, obligation,
    /// snapshot, or resolution -- the structural proof of INV-03 (a hint
    /// cannot carry a load-bearing fact because nothing downstream consumes
    /// its tokens).
    HintStmt,

    // -- typed elec behavioral-layer statements (WO-05 residual
    //    promotion, WO-19 converter-graph population; INV-16) --
    /// A clocked `on <event>:` behavioral body (cuprite/03 sec. 1): a
    /// synchronous-reactive island firing at the named event instant.
    /// Header (`on ctrl_clk.rise:`) + an indented stmt-block whose
    /// non-blocking `<=` [`RegAssign`] lines are register deltas and
    /// whose `=` [`CtorStmt`] lines are combinational, all in the clock
    /// domain named by the event. Feeds `ConverterGraph` (INV-16). `on`
    /// is the registered spatial/temporal-guard overload (cuprite/03).
    OnBlock,
    /// A non-blocking register assignment `<lhs> <= <expr>` inside an
    /// `on <event>:` body (cuprite/03 sec. 1a): the update commits at
    /// instant end, so it is a ZOH delta that cannot close a zero-delay
    /// cycle. Feeds a `ConverterGraph` register edge (INV-16).
    RegAssign,

    // -- typed cuprite computer-track nodes (workloads/realizes
    //    promotion, cuprite/05 sec. 1; INV-15 workload/intent ledger) --
    /// A `workloads:` block (cuprite/05 sec. 1): a contextually
    /// recognized domain block, like `parts:`/`zones:`, whose body is
    /// one [`WorkloadStmt`] per line. Declares the computer's boundary
    /// demand -- implementation-free.
    WorkloadsBlock,
    /// One workload line inside a [`WorkloadsBlock`]: `<name>:
    /// <kind>(<params>) [realizes <intent>[, <intent>...]]`, `<kind>` in
    /// `{loop, stream, event, batch}`. The parameter group is recorded
    /// as a balanced, non-decomposed [`WorkloadParams`] node (the same
    /// "structure recorded, not further decomposed" idiom as
    /// `GenericParams`/`parts:` orbit constructors -- WO-05 report
    /// note); a trailing `realizes` clause nests as a [`RealizesStmt`]
    /// child. Feeds the workload/intent ledger (cuprite/05 sec. 1a).
    WorkloadStmt,
    /// The balanced `(...)` parameter group of a [`WorkloadStmt`]
    /// (`rate=1kHz, work=200kops f32, jitter <= 50us, state: 64kB`):
    /// recorded whole, not decomposed further (mirrors
    /// [`GenericParams`]) since the params mix claim (`<=`/`>=`), field
    /// (`:`), and ctor (`=`) shapes the statement value-grammar does not
    /// unify. Lowering re-tokenizes this node's contents as needed.
    WorkloadParams,
    /// A `realizes <intent>[, <intent>...]` statement (cuprite/05 sec.
    /// 1a; EOPEN-15 resolved): claims a workload serves the named
    /// compute intents (an exactly-one-realization ledger, like flows).
    /// Recognized CONTEXTUALLY -- like the ownership/region/symmetry
    /// verbs -- only at statement-start with an `Ident` follower, so a
    /// coincidental `realizes: value` field is never mis-promoted. Also
    /// parses nested as the trailing clause of a [`WorkloadStmt`] line
    /// (the corpus shape: `att: loop(...) realizes decide`). The
    /// leading verb + argument idents are read back off the node's
    /// tokens (like `OwnershipStmt`/`SymmetryStmt`).
    RealizesStmt,

    // -- typed rule-pack constructs (WO-28 deliverable 2; hematite/02
    //    sec. 10, cuprite/04 sec. 4, design 21-rule-packs D-B/AD-21) --
    /// A `capability:` block inside a `process` decl body: the
    /// process's provider envelope table (demand <= capability), one
    /// `Field` per line. Recognized CONTEXTUALLY inside process bodies
    /// only (cycle 18 D85: no new lexer keywords), so `capability:`
    /// fields elsewhere (matings) keep today's `Field` shape.
    CapabilityBlock,
    /// A `dfm:`/`drc:`/`erc:` rule-pack block inside a `process` decl
    /// body: header word (the pack family, read back off the leading
    /// token) + a body of [`RuleDecl`]s. The three family words are
    /// contextual, recognized only at statement-start in process
    /// bodies (`dfm(rule)` waive targets stay value-position paths).
    RulePackBlock,
    /// One `rule <name>:` declaration inside a [`RulePackBlock`]: the
    /// citable identity (`waive dfm(<pack>.<name>)`, lockfile causes,
    /// E06xx provenance) + a body of rule fields ([`ForallClause`],
    /// `demand:`/`advise:`/`per:`/`why:` as ordinary `Field`s,
    /// [`ResolvesClause`], [`ExpectBlock`]).
    RuleDecl,
    /// The `forall <var> in <query>` line of a rule: the settled claim
    /// quantifier extended with an entity query as the match domain.
    /// The query parses with the expression grammar; any unmodeled
    /// tail (boolean connectives in filters) is swept losslessly
    /// INSIDE the clause (cycle 18 F95) for the engine to read back.
    ForallClause,
    /// A `resolves: <field> from free` line: marks the enclosing rule
    /// as the eager resolver of that `free` slot (regolith/03; cause
    /// `dfm(<pack>.<rule>)`/`drc(<pack>.<rule>)`, the INV-21 API).
    ResolvesClause,
    /// An `expect:` block inside a rule: in-pack fixtures, one
    /// [`ExpectCase`] per line; both a pass and a fail case are
    /// lint-required (engine wave).
    ExpectBlock,
    /// One `pass: <fixture>` / `fail: <fixture>` line inside an
    /// [`ExpectBlock`]; the verdict word is the leading token and the
    /// fixture parses with the value grammar (a `CallExpr` sketch).
    ExpectCase,

    // -- typed fluorite (fluid-circuit) constructs (WO-31; fluorite/02
    //    RATIFIED v1, D93). All fluorite keyword words are CONTEXTUAL
    //    idents recognized at statement/decl-start (cycle 18 D85 idiom),
    //    never new lexer keywords: `medium`/`flownet`/`reference`/
    //    `nodes`/`edges`/`states` also occur as ordinary path segments
    //    and field names. --
    /// A top-level `medium <name>: <phase>` declaration (fluorite/02
    /// sec. 1): names a fluid, binds its `props: registry(...)` records.
    /// The phase word (`liquid`/`gas`) rides in the header line.
    MediumDecl,
    /// A top-level `flownet <name>(medium=<ref>):` declaration
    /// (fluorite/02 sec. 4): the relational join over the AD-23 net
    /// core, body holds `reference:`/`nodes:` fields plus the typed
    /// [`SyntaxKind::EdgesBlock`] and [`SyntaxKind::StatesBlock`].
    FlownetDecl,
    /// A top-level `require <Group>:` claim group in a `.fluo` file
    /// (fluorite/02 sec. 6): the same claim vocabulary as the nested
    /// [`SyntaxKind::RequireClaim`], hoisted to declaration position.
    RequireDecl,
    /// The `edges:` block inside a flownet (fluorite/02 sec. 4): one
    /// [`SyntaxKind::EdgeStmt`] per declared edge.
    EdgesBlock,
    /// One edge line inside an [`SyntaxKind::EdgesBlock`]: `<name>:
    /// <constructor>(<params>) (<a> -> <b>)` -- the component
    /// constructor plus the arrow-shaped positive-sense naming pair
    /// (a NAMING convention, not a flow-direction assertion; fluorite/02
    /// sec. 4), typed as a trailing [`SyntaxKind::SensePair`].
    EdgeStmt,
    /// The `states:` block inside a flownet (fluorite/02 sec. 4): one
    /// [`SyntaxKind::StateStmt`] per line (edge-parameter domains,
    /// net-level `state <name> in {...}` declarations, and `event`
    /// lines).
    StatesBlock,
    /// One line inside a [`SyntaxKind::StatesBlock`]: an edge-parameter
    /// domain (`<edge>.<param> in {...}`), a net-level state declaration
    /// (`state <name> in {...}`), or a commanded `event` (fluorite/02
    /// sec. 4/5). Recorded whole; the lowering pass reads it back.
    StateStmt,
    /// The arrow-shaped positive-sense naming pair on an
    /// [`SyntaxKind::EdgeStmt`]: `(<a> -> <b>)` (fluorite/02 sec. 4). A
    /// NAMING convention, not a flow-direction assertion. Structured
    /// at parse time from the existing token stream (`->` is `Minus`
    /// then `Gt`, no lexer change): `LParen`, a name-path `Ident`, the
    /// `Minus`+`Gt` pair, a name-path `Ident`, `RParen`.
    SensePair,
    /// A brace-delimited discrete domain set: `{a, b, c}` (a state
    /// variable's domain, `state <name> in {...}`, or a
    /// `states={open, closed}` constructor record value; fluorite/02
    /// sec. 4/5). `{`/`}` are unclassified `Error` bytes at the lexer
    /// (no lexer change); this node structures them at parse time by
    /// their text, wrapping the comma-separated `Ident` list between
    /// the two brace bytes.
    DomainSet,

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
    SyntaxKind::AtTok,
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
    SyntaxKind::InstExpr,
    SyntaxKind::GenericArgs,
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
    SyntaxKind::OwnershipStmt,
    SyntaxKind::RegionStmt,
    SyntaxKind::SymmetryStmt,
    SyntaxKind::QueryStmt,
    SyntaxKind::HintStmt,
    SyntaxKind::OnBlock,
    SyntaxKind::RegAssign,
    SyntaxKind::WorkloadsBlock,
    SyntaxKind::WorkloadStmt,
    SyntaxKind::WorkloadParams,
    SyntaxKind::RealizesStmt,
    SyntaxKind::CapabilityBlock,
    SyntaxKind::RulePackBlock,
    SyntaxKind::RuleDecl,
    SyntaxKind::ForallClause,
    SyntaxKind::ResolvesClause,
    SyntaxKind::ExpectBlock,
    SyntaxKind::ExpectCase,
    SyntaxKind::MediumDecl,
    SyntaxKind::FlownetDecl,
    SyntaxKind::RequireDecl,
    SyntaxKind::EdgesBlock,
    SyntaxKind::EdgeStmt,
    SyntaxKind::StatesBlock,
    SyntaxKind::StateStmt,
    SyntaxKind::SensePair,
    SyntaxKind::DomainSet,
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
