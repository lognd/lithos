//! `SyntaxKind`: the tag on every rowan CST node and token (AD-3). One
//! flat `repr(u16)` enum covering terminals (post-layout tokens and
//! keywords) and non-terminals (grammar nodes), rust-analyzer style.
//!
//! Regolith reference: `docs/spec/regolith/08`, `docs/spec/hematite/02`,
//! `docs/spec/cuprite/07`. The keyword set and node list grow with the grammar
//! (WO-05); adding a construct is: a `SyntaxKind`, a parser production,
//! a typed AST view, and a grammar.ebnf rule.

/// The kind of a CST node or token. `repr(u16)` so rowan can store it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[repr(u16)]
#[allow(missing_docs)] // variant names are self-describing terminals/nodes
                       // frob:doc docs/modules/regolith-syntax.md#syntax-kind
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
    /// `select` (WO-56, D161): the sixth impl strategy keyword,
    /// `impl <Iface> by select(<impl-ref>, <impl-ref>, ...)`. Beside
    /// `spec`/`composing`/`circuit`/`vendor`/`extern` (regolith/08
    /// sec. 4). Tokenized the same way `extern` is (a bare lexer
    /// keyword; the header stays generic-token rest-of-line, read
    /// back by `regolith-syntax::checks`/`regolith-lower::contracts`).
    SelectKw,

    // -- nodes (non-terminals) --
    File,
    ImportStmt,
    Decl,
    DeclHeader,
    Field,
    CtorStmt,
    ThenScope,
    RequireClaim,
    /// `compute <name>: <quantity kind> over <index domain>` (WO-33
    /// D98): a claim line that produces a named indexed field instead
    /// of asserting a bound. Lives inside a `RequireClaim` group,
    /// contextually recognized like `Field` (`compute` is not a
    /// reserved keyword -- it is disambiguated by its `Ident` follower,
    /// mirroring the ordinary `subject: predicate` shape).
    ComputeField,
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
    /// A keyword argument inside a [`SyntaxKind::ArgList`]:
    /// `name: <value-expr>` (`promises: >= 20Mops f32 sustained`,
    /// cuprite/05 sec. 2 architecture-resource block contracts). The
    /// name is the leading [`SyntaxKind::NameRef`]; the value is the
    /// full value/expression grammar after the colon (a comparison-
    /// bearing promise bound, a tolerance, a plain quantity). Distinct
    /// from a positional argument, which is a bare expression.
    KeywordArg,

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
    /// A `forall <var> in <domain>:` BLOCK claim inside a `require`
    /// group (regolith/03; WO-68 emission fix): the header line (bound
    /// variable + domain text, the same query/set-ref grammar as
    /// [`ForallClause`]) plus a nested body of ordinary named claim
    /// [`Field`]s (`<name>: <predicate>`), parsed via the shared
    /// generic statement-block machinery so every nested claim is a
    /// real structured `Field`, not swallowed whole into an
    /// [`SyntaxKind::OpaqueIsland`]. Distinct from `ForallClause`
    /// (which has no body of its own -- it is one field of a
    /// `RuleDecl`) and from the D105a single-line `forall ... in
    /// [...]: <predicate>` claim-line PREFIX (which stays inside one
    /// `Field`'s own text, unaffected by this node).
    ForallSweepClaim,
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
    /// A claim's trailing `, model=<ident>` rung-5 pin (regolith/12
    /// sec. 2 rung 5; WO-80 deliverable 1): `Comma`, `ModelKw`, `Eq`,
    /// `Ident`, structured out of the generic `OpaqueIsland` tail
    /// sweep so lowering can read `model_pin` back off the typed node
    /// instead of the swallowed-into-rhs text WO-76 found. Only this
    /// exact shape is recognized; every other trailing attribute
    /// (`sf=`, `scatter_factor=`, ...) still degrades to
    /// `OpaqueIsland` text unchanged (AD-3, no new mechanism beyond
    /// the WO's stated scope).
    ModelPin,
    /// A brace-delimited discrete domain set: `{a, b, c}` (a state
    /// variable's domain, `state <name> in {...}`, or a
    /// `states={open, closed}` constructor record value; fluorite/02
    /// sec. 4/5). `{`/`}` are unclassified `Error` bytes at the lexer
    /// (no lexer change); this node structures them at parse time by
    /// their text, wrapping the comma-separated `Ident` list between
    /// the two brace bytes.
    DomainSet,

    // -- typed cuprite routed-run constructs (WO-34 deliverable 1; D99,
    // cuprite/04 -- the `harness:` block lands beside `board`. All
    // words (`harness`, `run`, `along`, `bundle`, `route`,
    // `environment`) are CONTEXTUAL idents recognized at decl/stmt-
    // start (D85 idiom), never new lexer keywords -- they also occur
    // as ordinary path segments/field names (e.g. `route` is already
    // reused by `RegionStmt`'s `route <name> (into|join) <region>`
    // line form; the two are disambiguated purely by nesting position,
    // top-level-harness-body `run`/`environment` lines vs. an ordinary
    // statement-block line). AD-17/AD-22/AD-23 (runs are NOT nets). --
    /// A top-level `harness <name>:` declaration (D99): names a wiring
    /// harness, body holds one [`SyntaxKind::RunStmt`] per declared run
    /// plus [`SyntaxKind::EnvironmentStmt`] connector-environment class
    /// declarations. Mirrors [`SyntaxKind::FlownetDecl`]'s decl-header +
    /// typed-body shape.
    HarnessDecl,
    /// One `run <name>: from <ep> to <ep>` line inside a
    /// [`SyntaxKind::HarnessDecl`] body (D99): the header (name +
    /// endpoints) is recorded whole -- `from`/`to` are not lexer
    /// keywords and the header rest is the WO-05 "structure recorded,
    /// not further decomposed" idiom already used for interface/decl
    /// header tails -- and the indented body holds the run's routed
    /// PATH ([`SyntaxKind::AlongClause`]) and co-routing
    /// ([`SyntaxKind::BundleClause`]) lines. Elaboration (WO-34
    /// deliverable 2, out of this grammar's scope) re-tokenizes the
    /// header to resolve the two endpoint refs.
    RunStmt,
    /// One `along <structural refs>` or `along route: free` line inside
    /// a [`SyntaxKind::RunStmt`] body (D99): the routed PATH, either a
    /// comma list of structural waypoint refs or the planner-routed
    /// marker. AMBIGUITY NOTE (documented, not invented): D99's prose
    /// describes these as two alternate forms (`along <refs>` XOR bare
    /// `route: free`), but its own worked example spells the
    /// planner-routed run as `along route: free` (both words). Rather
    /// than silently pick one reading, this grammar accepts the line
    /// whole under the `along` leading word (the same "recorded whole,
    /// re-tokenized downstream" idiom as [`SyntaxKind::WorkloadParams`]/
    /// generic header tails) -- it covers the ref-list form, the
    /// combined `along route: free` form from the example, AND a bare
    /// `route: free`/`route <name>` line (also typed as
    /// [`SyntaxKind::AlongClause`] when it is the run body's path line,
    /// distinct from the ordinary statement-position `route` verb of
    /// [`SyntaxKind::RegionStmt`]). Elaboration (D2) decides ref-list vs.
    /// planner-free by re-parsing the recorded text; no claim is made
    /// here about which reading D99 intended.
    AlongClause,
    /// A `bundle <group>` co-routing line inside a [`SyntaxKind::RunStmt`]
    /// body (D99): declares the run's bundle-factor group membership;
    /// the group name is not further decomposed (elaboration reads the
    /// name back off the line).
    BundleClause,
    /// A top-level `environment <name>: [<lo>, <hi>]` connector
    /// environment-class declaration inside a [`SyntaxKind::HarnessDecl`]
    /// body (D99): an ordinary `subject: value` line whose value is the
    /// existing `[a, b]` bracket grammar ([`SyntaxKind::IntervalExpr`]),
    /// typed distinctly so elaboration and the parse-time
    /// required-field check (`checks.rs`) can find it without scanning
    /// for a coincidental field named `environment`.
    EnvironmentStmt,

    // -- typed calcite (civil/architectural) constructs (WO-47;
    //    calcite/02 RATIFIED v1, D149). All calcite keyword words are
    //    CONTEXTUAL idents recognized at decl-start (cycle 18 D85
    //    idiom), never new lexer keywords: `site`/`grid`/`level`/
    //    `space`/`adjacent`/`access`/`circulation`/`member`/
    //    `structure`/`loads`/`assembly` also occur as ordinary path
    //    segments and field names. Most bodies reuse the shared generic
    //    field/statement grammar unchanged (site's `boundary:`/`soil:`,
    //    space's fields, member's `section:`/`material:`, loads'
    //    entries, assembly's `layers:`/`promises:` -- calcite/02 secs.
    //    1-2, 4, 7-8 are pure vocabulary over existing machinery, no new
    //    syntax). Only `structure`'s `transfers:` and `access`'s edge
    //    lines get typed net-edge structure, reusing
    //    [`SyntaxKind::EdgesBlock`]/[`SyntaxKind::EdgeStmt`]/
    //    [`SyntaxKind::SensePair`] verbatim (the same mating-shaped
    //    `name: Ctor(...) (a -> b)` line the fluorite `edges:` block
    //    already types -- NO DUPLICATION). --
    /// A top-level `site <name>:` declaration (calcite/02 sec. 1):
    /// declared civil boundary truth + soil records. Body is the shared
    /// generic statement grammar (`boundary:`/`soil:` are ordinary
    /// nested blocks, unchanged).
    SiteDecl,
    /// A top-level `grid <name>: <idents> spacing <qty>` declaration
    /// (calcite/02 sec. 1): a datum family. Header-only (no body).
    GridDecl,
    /// A top-level `level <name>: <qty>` declaration (calcite/02
    /// sec. 1): a datum. Header-only (no body).
    LevelDecl,
    /// A top-level `space <name>:` declaration (calcite/02 sec. 2): the
    /// architectural program unit. Body is the shared generic statement
    /// grammar (`area:`, `occupancy:`, `at:`, `bounded_by`, `offers:`).
    SpaceDecl,
    /// A top-level `adjacent <a>, <b>: <predicate>` declaration
    /// (calcite/02 sec. 2): an adjacency contract between spaces.
    /// Header-only (no body).
    AdjacentDecl,
    /// A top-level `access:` block (calcite/02 sec. 2): opening
    /// declarations, the edges of a circulation net. Its lines are the
    /// SAME shape as a flownet [`SyntaxKind::EdgesBlock`]'s
    /// [`SyntaxKind::EdgeStmt`]s (`<name>: <Ctor>(...) (<a> -> <b>)`)
    /// but hoisted directly to decl-body position (no intermediate
    /// `edges:` field header): the decl's body IS the edge list.
    AccessDecl,
    /// A top-level `circulation <name>:` declaration (calcite/02
    /// sec. 3): the egress net over the AD-23 core (a third
    /// `NetDiscipline`, D139). Body is the shared generic statement
    /// grammar (`reference:`, `nodes:`, `edges:` are plain comma-list
    /// fields naming existing [`SyntaxKind::AccessDecl`] entries, not a
    /// nested edge block -- calcite/02 sec. 3's `edges:` differs from
    /// fluorite's `edges:` block in exactly this way).
    CirculationDecl,
    /// A top-level `member <name>: <role>` declaration (calcite/02
    /// sec. 4): a structural element. Body is the shared generic
    /// statement grammar (`section:`, `material:`, the `from ... to
    /// ... at ...` anchor line).
    MemberDecl,
    /// A top-level `structure <name>:` declaration (calcite/02 sec. 6):
    /// the load-path net over the AD-23 core (a fourth `NetDiscipline`,
    /// D139). Body holds `support:`/`members:` fields plus the typed
    /// [`SyntaxKind::EdgesBlock`] under `transfers:` (member-to-member
    /// load transfer edges, the same mating-shaped line the fluorite
    /// `edges:` block types).
    StructureDecl,
    /// A top-level `loads:` block (calcite/02 sec. 7): load case
    /// magnitudes (boundary truth + pack model refs). Body is the
    /// shared generic statement grammar.
    LoadsDecl,
    // NOTE: calcite's `assembly <name>: <kind>` (calcite/02 sec. 8) has
    // NO typed SyntaxKind here on purpose: `assembly` is a settled
    // cross-track homonym with hematite's existing system artifact
    // (calcite/02 sec. 11), and both stay the generic
    // [`SyntaxKind::Decl`] to keep hematite's goldens byte-identical
    // (see the parser dispatch's own comment for the full argument).

    // -- typed design-test constructs (WO-83 deliverable 1; charter
    //    toolchain/37-design-testing.md, D190) --
    /// A top-level `test <name>:` declaration: a cross-track,
    /// author-written design test (charter 37). Ident-led, like
    /// `process` (`test` is a CONTEXTUAL word, never a lexer keyword --
    /// it stays a legal field/subject name elsewhere). Body holds one
    /// [`SyntaxKind::ScenarioBlock`] and one [`SyntaxKind::TestExpectBlock`]
    /// over the shared generic statement grammar.
    TestDecl,
    /// The `scenario:` block of a [`SyntaxKind::TestDecl`]: config-axis
    /// selections, rung-1 assertions (`path = value`, ordinary
    /// [`SyntaxKind::CtorStmt`]), rung-2 pins (`locked:`/`use`/
    /// `sequence:`/`merge()`/`hosted_on`, already-typed constructs),
    /// `seed = <n>` / `budget_evals = <n>`, and realized-input
    /// digest-pinned refs (an ordinary [`SyntaxKind::Field`] whose value
    /// is a `CallExpr` carrying a `digest=` keyword arg) -- the ladder
    /// IS the scenario vocabulary (regolith/12), so no test-only
    /// backdoor syntax exists: the body is the shared statement grammar
    /// verbatim, mirroring [`SyntaxKind::CapabilityBlock`]'s idiom of a
    /// contextual header over an otherwise-generic body.
    ScenarioBlock,
    /// The `expect:` block of a [`SyntaxKind::TestDecl`]: one
    /// [`SyntaxKind::TestExpectCase`] per line (distinct from a rule
    /// pack's [`SyntaxKind::ExpectBlock`]/[`SyntaxKind::ExpectCase`]
    /// pass/fail fixture pair -- design-test expectations observe five
    /// different shapes, never a bare pass/fail).
    TestExpectBlock,
    /// One expectation line inside a [`SyntaxKind::TestExpectBlock`]:
    /// leading contextual word (`diagnostic`/`verdict`/`value`/`count`/
    /// `winner`) + the rest of the line recorded whole (the WO-05
    /// header-rest idiom also used by `along-clause`/`run-stmt`: each
    /// form's shape -- `diagnostic <CODE> on <subject>`; `verdict
    /// <claim-path> = discharged|violated|indeterminate`; `value <path>
    /// within [lo, hi] [cause <class>]`; `count <what> = N`; `winner
    /// <choice-path> = <candidate>` -- is too varied to unify under one
    /// field/ctor production, so the typed AST view
    /// ([`crate::ast::TestExpectCase`]) splits the recorded text back
    /// into `form()`/`subject()`/`tail()` rather than inventing five
    /// separate node kinds).
    TestExpectCase,
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
    SyntaxKind::SelectKw,
    SyntaxKind::File,
    SyntaxKind::ImportStmt,
    SyntaxKind::Decl,
    SyntaxKind::DeclHeader,
    SyntaxKind::Field,
    SyntaxKind::CtorStmt,
    SyntaxKind::ThenScope,
    SyntaxKind::RequireClaim,
    SyntaxKind::ComputeField,
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
    SyntaxKind::KeywordArg,
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
    SyntaxKind::ForallSweepClaim,
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
    SyntaxKind::ModelPin,
    SyntaxKind::DomainSet,
    SyntaxKind::HarnessDecl,
    SyntaxKind::RunStmt,
    SyntaxKind::AlongClause,
    SyntaxKind::BundleClause,
    SyntaxKind::EnvironmentStmt,
    SyntaxKind::SiteDecl,
    SyntaxKind::GridDecl,
    SyntaxKind::LevelDecl,
    SyntaxKind::SpaceDecl,
    SyntaxKind::AdjacentDecl,
    SyntaxKind::AccessDecl,
    SyntaxKind::CirculationDecl,
    SyntaxKind::MemberDecl,
    SyntaxKind::StructureDecl,
    SyntaxKind::LoadsDecl,
    SyntaxKind::TestDecl,
    SyntaxKind::ScenarioBlock,
    SyntaxKind::TestExpectBlock,
    SyntaxKind::TestExpectCase,
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
    // frob:doc docs/modules/regolith-syntax.md#syntax-kind
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    #[must_use]
    pub fn from_raw(raw: u16) -> SyntaxKind {
        ALL_KINDS
            .get(usize::from(raw))
            .copied()
            .unwrap_or_else(|| panic!("raw SyntaxKind out of range: {raw}"))
    }

    /// True when this kind is trivia (whitespace or comment): skipped by
    /// the typed AST layer but present in the CST.
    // frob:doc docs/modules/regolith-syntax.md#syntax-kind
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    #[must_use]
    pub fn is_trivia(self) -> bool {
        matches!(self, SyntaxKind::Whitespace | SyntaxKind::Comment)
    }
}

/// The one keyword table: every reserved word and its `SyntaxKind`, in
/// declaration order. `keyword_kind` and the WO-39 grammar-json export
/// both read this -- no second copy of the keyword strings anywhere
/// (ground rule 7 / AD-24).
// frob:doc docs/modules/regolith-syntax.md#syntax-kind
pub const KEYWORD_TABLE: &[(&str, SyntaxKind)] = &[
    ("import", SyntaxKind::ImportKw),
    ("namespace", SyntaxKind::NamespaceKw),
    ("quantity", SyntaxKind::QuantityKw),
    ("signature", SyntaxKind::SignatureKw),
    ("part", SyntaxKind::PartKw),
    ("profile", SyntaxKind::ProfileKw),
    ("interface", SyntaxKind::InterfaceKw),
    ("mating", SyntaxKind::MatingKw),
    ("assembly", SyntaxKind::AssemblyKw),
    ("system", SyntaxKind::SystemKw),
    ("block", SyntaxKind::BlockKw),
    ("impl", SyntaxKind::ImplKw),
    ("component", SyntaxKind::ComponentKw),
    ("protocol", SyntaxKind::ProtocolKw),
    ("computer", SyntaxKind::ComputerKw),
    ("image", SyntaxKind::ImageKw),
    ("board", SyntaxKind::BoardKw),
    ("target", SyntaxKind::TargetKw),
    ("datum", SyntaxKind::DatumKw),
    ("event", SyntaxKind::EventKw),
    ("then", SyntaxKind::ThenKw),
    ("on", SyntaxKind::OnKw),
    ("require", SyntaxKind::RequireKw),
    ("budget", SyntaxKind::BudgetKw),
    ("waive", SyntaxKind::WaiveKw),
    ("policy", SyntaxKind::PolicyKw),
    ("prefer", SyntaxKind::PreferKw),
    ("forbid", SyntaxKind::ForbidKw),
    ("minimize", SyntaxKind::MinimizeKw),
    ("maximize", SyntaxKind::MaximizeKw),
    ("locked", SyntaxKind::LockedKw),
    ("extern", SyntaxKind::ExternKw),
    ("model", SyntaxKind::ModelKw),
    ("hosted_on", SyntaxKind::HostedOnKw),
    ("in", SyntaxKind::InKw),
    ("free", SyntaxKind::FreeKw),
    ("derived", SyntaxKind::DerivedKw),
    ("allocated", SyntaxKind::AllocatedKw),
    ("within", SyntaxKind::WithinKw),
    ("use", SyntaxKind::UseKw),
    ("override", SyntaxKind::OverrideKw),
    ("by", SyntaxKind::ByKw),
    ("default", SyntaxKind::DefaultKw),
    ("during", SyntaxKind::DuringKw),
    ("select", SyntaxKind::SelectKw),
];

/// Map an identifier's text to its keyword kind, or `None` if it is a
/// plain identifier. Reads `KEYWORD_TABLE`, the one keyword table.
// frob:doc docs/modules/regolith-syntax.md#syntax-kind
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
#[must_use]
pub fn keyword_kind(text: &str) -> Option<SyntaxKind> {
    KEYWORD_TABLE
        .iter()
        .find_map(|&(word, kind)| (word == text).then_some(kind))
}

#[cfg(test)]
mod tests {
    use super::{keyword_kind, SyntaxKind};

    // frob:tests crates/regolith-syntax/src/syntax_kind.rs::keyword_kind kind="unit"
    #[test]
    fn keywords_map_and_idents_do_not() {
        assert_eq!(keyword_kind("part"), Some(SyntaxKind::PartKw));
        assert_eq!(keyword_kind("hosted_on"), Some(SyntaxKind::HostedOnKw));
        assert_eq!(keyword_kind("within"), Some(SyntaxKind::WithinKw));
        assert_eq!(keyword_kind("flange"), None);
    }

    // frob:tests crates/regolith-syntax/src/syntax_kind.rs::SyntaxKind.from_raw kind="unit"
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

    // frob:tests crates/regolith-syntax/src/syntax_kind.rs::SyntaxKind.is_trivia kind="unit"
    #[test]
    fn trivia_is_flagged() {
        assert!(SyntaxKind::Whitespace.is_trivia());
        assert!(SyntaxKind::Comment.is_trivia());
        assert!(!SyntaxKind::PartKw.is_trivia());
    }
}
