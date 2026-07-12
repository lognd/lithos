//! The declared material-removal vocabulary (charter 34 phase 1,
//! D200/WO-77): the ONE home for the four family constructors'
//! parameter signatures, slot-form parsing, and constructive
//! validation. Both consumers of the AD-17 claim-scope traversal --
//! the `lower.programs` projection (`feature_program.rs`) and the
//! entity projector (`entities.rs`) -- read family parameters through
//! this module, so an emitted `FeatureOp` and the rule-pack entity
//! that quantifies over it can never disagree (NO DUPLICATION).
//!
//! Slot forms are EXACTLY the existing value-slot vocabulary (D200:
//! "the existing literal / `in [lo, hi]` / `in {a, b}` slot forms the
//! optimizer already consumes"):
//!
//! - `count=6` / `pitch=18mm` / `cell=gyroid` -- a literal;
//! - `count in [4, 12]` (also spelled `count = in [4, 12]`, the
//!   profile-constraint style) -- a bounded planner slot;
//! - `cell in {gyroid, honeycomb}` -- a discrete planner slot.
//!
//! Anything else -- a missing required slot, an unknown or duplicate
//! slot, a wrong-dimension value, a `density` outside `[0, 1]`, an
//! unknown lattice `cell` name -- is MALFORMED: the caller emits the
//! constructive `E0451` naming the family's full signature, and the
//! op is omitted (never a guessed value, never silent truncation).

use regolith_ir::ResolvedFeatureParam;
use regolith_qty::{BaseDimension, Dimension, Qty, Unit};
use regolith_util::IndexMap;

/// The v1 lattice cell families (charter 34 sec. 2 / D200). An
/// unsupported cell family is a NAMED skip downstream, but an unknown
/// cell NAME is malformed here -- the discrete domain is closed.
pub const LATTICE_CELLS: &[&str] = &["gyroid", "honeycomb", "cubic"];

/// What value class a family slot accepts.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SlotType {
    /// A positive integer count (`count`, `nx`, `ny`).
    Int,
    /// A length quantity (`pitch`, `thickness`, `wall`, ...).
    Length,
    /// A dimensionless fraction in `[0, 1]` (`density`).
    Fraction,
    /// A lattice cell name from [`LATTICE_CELLS`].
    Cell,
}

/// One slot of a family signature.
#[derive(Debug, Clone, Copy)]
pub struct SlotSpec {
    /// The slot name as spelled in source (`count`, `t`).
    pub name: &'static str,
    /// The emitted `FeatureOp::params` / `Entity::measures` key --
    /// usually `name`, but `Shell(t)` emits under `thickness` (the
    /// rule-pack vocabulary key, `EntityKind::known_measure_keys`).
    pub key: &'static str,
    /// The accepted value class.
    pub ty: SlotType,
    /// Whether the slot must be spelled.
    pub required: bool,
}

/// One material-removal family: constructor verb, emitted kind word,
/// human signature (the E0451 text), and slots.
#[derive(Debug, Clone, Copy)]
pub struct FamilySpec {
    /// The constructor verb (`Ribs`).
    pub ctor: &'static str,
    /// The emitted `FeatureOp::kind` word (`ribs`).
    pub kind_word: &'static str,
    /// The full signature rendered into the E0451 diagnostic.
    pub signature: &'static str,
    /// The slots, in signature order.
    pub slots: &'static [SlotSpec],
}

/// The four family signatures (D200 verbatim; charter 34 sec. 2).
pub const FAMILIES: &[FamilySpec] = &[
    FamilySpec {
        ctor: "Ribs",
        kind_word: "ribs",
        signature: "Ribs(count: int, pitch: length, thickness: length, height?: length)",
        slots: &[
            SlotSpec {
                name: "count",
                key: "count",
                ty: SlotType::Int,
                required: true,
            },
            SlotSpec {
                name: "pitch",
                key: "pitch",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "thickness",
                key: "thickness",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "height",
                key: "height",
                ty: SlotType::Length,
                required: false,
            },
        ],
    },
    FamilySpec {
        ctor: "PocketGrid",
        kind_word: "pocket_grid",
        signature: "PocketGrid(nx: int, ny: int, wall: length, floor: length, depth?: length)",
        slots: &[
            SlotSpec {
                name: "nx",
                key: "nx",
                ty: SlotType::Int,
                required: true,
            },
            SlotSpec {
                name: "ny",
                key: "ny",
                ty: SlotType::Int,
                required: true,
            },
            SlotSpec {
                name: "wall",
                key: "wall",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "floor",
                key: "floor",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "depth",
                key: "depth",
                ty: SlotType::Length,
                required: false,
            },
        ],
    },
    FamilySpec {
        ctor: "Shell",
        kind_word: "shell",
        signature: "Shell(t: length)",
        slots: &[SlotSpec {
            name: "t",
            key: "thickness",
            ty: SlotType::Length,
            required: true,
        }],
    },
    FamilySpec {
        ctor: "RectPocket",
        kind_word: "rect_pocket",
        signature:
            "RectPocket(width: length, depth_xy: length, height: length, corner_radius?: length)",
        slots: &[
            SlotSpec {
                name: "width",
                key: "width",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "depth_xy",
                key: "depth_xy",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "height",
                key: "height",
                ty: SlotType::Length,
                required: true,
            },
            SlotSpec {
                name: "corner_radius",
                key: "corner_radius",
                ty: SlotType::Length,
                required: false,
            },
        ],
    },
    FamilySpec {
        ctor: "Lattice",
        kind_word: "lattice",
        signature: "Lattice(cell: {gyroid, honeycomb, cubic}, density: [0, 1])",
        slots: &[
            SlotSpec {
                name: "cell",
                key: "cell",
                ty: SlotType::Cell,
                required: true,
            },
            SlotSpec {
                name: "density",
                key: "density",
                ty: SlotType::Fraction,
                required: true,
            },
        ],
    },
];

/// The family a constructor verb names, if any.
#[must_use]
pub fn family_for_constructor(ctor: &str) -> Option<&'static FamilySpec> {
    FAMILIES.iter().find(|f| f.ctor == ctor)
}

/// One parsed slot value, before validation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SlotValue {
    /// `k=v` -- a spelled literal.
    Literal(String),
    /// `k in [lo, hi]` -- a bounded planner slot (raw endpoint texts).
    Bounded(String, String),
    /// `k in {a, b}` -- a discrete planner slot (raw member texts).
    Discrete(Vec<String>),
}

impl SlotValue {
    /// The `ResolvedFeatureParam` this slot emits: literals keep their
    /// text with the `literal` cause; bounded/discrete slots normalize
    /// to their envelope spelling with the `planner` cause (the
    /// optimizer decides, regolith/03 sec. 2 -- exactly the Cause class
    /// `feature_program::resolved_param` already assigns `[..]` texts).
    #[must_use]
    pub fn to_param(&self) -> ResolvedFeatureParam {
        match self {
            SlotValue::Literal(text) => ResolvedFeatureParam {
                text: text.clone(),
                cause: "literal".to_string(),
            },
            SlotValue::Bounded(lo, hi) => ResolvedFeatureParam {
                text: format!("[{lo}, {hi}]"),
                cause: "planner".to_string(),
            },
            SlotValue::Discrete(items) => ResolvedFeatureParam {
                text: format!("{{{}}}", items.join(", ")),
                cause: "planner".to_string(),
            },
        }
    }
}

/// Parse + validate one family call's argument text. `args_text` is
/// the claim-scope traversal's raw RHS (`Ribs(count in [4, 12], ...)`),
/// exactly what every other projection scans.
///
/// # Errors
/// The constructive malformation messages (each names the offending
/// slot; the caller renders them with the family signature into ONE
/// `E0451`). An `Err` means the op must be omitted -- partial
/// projection of a malformed family op is never done.
pub fn validate_family_params(
    family: &FamilySpec,
    args_text: &str,
) -> Result<IndexMap<String, ResolvedFeatureParam>, Vec<String>> {
    let mut errors = Vec::new();
    let mut slots: IndexMap<&'static str, SlotValue> = IndexMap::new();

    for item in split_top_level_args(inner_args(args_text)) {
        let item = item.trim();
        if item.is_empty() {
            continue;
        }
        match parse_slot_item(item) {
            Some((name, value)) => {
                let Some(spec) = family.slots.iter().find(|s| s.name == name) else {
                    errors.push(format!("unknown slot `{name}`"));
                    continue;
                };
                if slots.contains_key(spec.name) {
                    errors.push(format!("slot `{name}` spelled more than once"));
                    continue;
                }
                if let Err(e) = validate_slot_value(spec, &value) {
                    errors.push(e);
                    continue;
                }
                slots.insert(spec.name, value);
            }
            None => errors.push(format!(
                "argument `{item}` is not a `name=value`, `name in [lo, hi]`, \
                 or `name in {{a, b}}` slot"
            )),
        }
    }

    for spec in family.slots {
        if spec.required && !slots.contains_key(spec.name) {
            errors.push(format!("required slot `{}` is missing", spec.name));
        }
    }

    if !errors.is_empty() {
        return Err(errors);
    }
    // Emit in SIGNATURE order (AD-6 determinism), keyed by the
    // measure-vocabulary key.
    let mut params = IndexMap::new();
    for spec in family.slots {
        if let Some(value) = slots.get(spec.name) {
            params.insert(spec.key.to_string(), value.to_param());
        }
    }
    Ok(params)
}

/// The parsed slot values keyed by measure-vocabulary key -- the
/// entity projector's form (measure TEXTS, envelopes verbatim), from
/// the same single parse. Malformed calls yield whatever slots did
/// validate (the E0451 is `lower.programs`' job; entities stay
/// best-effort like every other projector input).
#[must_use]
pub fn family_measures(family: &FamilySpec, args_text: &str) -> IndexMap<String, String> {
    match validate_family_params(family, args_text) {
        Ok(params) => params.into_iter().map(|(k, v)| (k, v.text)).collect(),
        Err(_) => IndexMap::new(),
    }
}

/// The text inside the call's outermost parentheses (`Ribs(a, b)` ->
/// `a, b`); the whole text when no parens are spelled.
fn inner_args(args_text: &str) -> &str {
    let Some(open) = args_text.find('(') else {
        return "";
    };
    let Some(close) = args_text.rfind(')') else {
        return args_text[open + 1..].trim();
    };
    if close <= open {
        return "";
    }
    args_text[open + 1..close].trim()
}

/// Split on commas at bracket depth zero (`[..]`/`{..}`/`(..)` nest).
fn split_top_level_args(text: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut depth = 0i32;
    let mut start = 0usize;
    for (i, c) in text.char_indices() {
        match c {
            '[' | '{' | '(' => depth += 1,
            ']' | '}' | ')' => depth -= 1,
            ',' if depth == 0 => {
                out.push(&text[start..i]);
                start = i + 1;
            }
            _ => {}
        }
    }
    out.push(&text[start..]);
    out
}

/// Parse one argument item into `(slot name, value)`, accepting the
/// three slot forms (module doc). `None` when the item fits none.
fn parse_slot_item(item: &str) -> Option<(&str, SlotValue)> {
    let name_end = item
        .find(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
        .unwrap_or(item.len());
    let name = &item[..name_end];
    if name.is_empty() || name.as_bytes()[0].is_ascii_digit() {
        return None;
    }
    let mut rest = item[name_end..].trim_start();
    // `name = in [..]` (the profile-constraint style) and `name = v`.
    if let Some(after_eq) = rest.strip_prefix('=') {
        rest = after_eq.trim_start();
        if let Some(env) = rest.strip_prefix("in ").map(str::trim_start) {
            return parse_envelope(env).map(|v| (name, v));
        }
        if rest.is_empty() {
            return None;
        }
        return Some((name, SlotValue::Literal(rest.trim().to_string())));
    }
    // `name in [..]` / `name in {..}`.
    if let Some(env) = rest.strip_prefix("in ").map(str::trim_start) {
        return parse_envelope(env).map(|v| (name, v));
    }
    None
}

/// Parse a `[lo, hi]` or `{a, b, ...}` envelope text.
fn parse_envelope(text: &str) -> Option<SlotValue> {
    let text = text.trim();
    if let Some(inner) = text.strip_prefix('[').and_then(|t| t.strip_suffix(']')) {
        let parts: Vec<&str> = inner.split(',').map(str::trim).collect();
        if parts.len() == 2 && parts.iter().all(|p| !p.is_empty()) {
            return Some(SlotValue::Bounded(
                parts[0].to_string(),
                parts[1].to_string(),
            ));
        }
        return None;
    }
    if let Some(inner) = text.strip_prefix('{').and_then(|t| t.strip_suffix('}')) {
        let items: Vec<String> = inner
            .split(',')
            .map(|p| p.trim().to_string())
            .filter(|p| !p.is_empty())
            .collect();
        if items.is_empty() {
            return None;
        }
        return Some(SlotValue::Discrete(items));
    }
    None
}

/// Validate one slot's value against its declared class; the error is
/// the constructive per-slot message.
fn validate_slot_value(spec: &SlotSpec, value: &SlotValue) -> Result<(), String> {
    let name = spec.name;
    match (spec.ty, value) {
        (SlotType::Int, SlotValue::Literal(v)) => check_int(name, v),
        (SlotType::Int, SlotValue::Bounded(lo, hi)) => {
            check_int(name, lo)?;
            check_int(name, hi)?;
            let (l, h) = (int_of(lo), int_of(hi));
            if l > h {
                return Err(format!("slot `{name}` bounds `[{lo}, {hi}]` are inverted"));
            }
            Ok(())
        }
        (SlotType::Int, SlotValue::Discrete(items)) => {
            items.iter().try_for_each(|i| check_int(name, i))
        }
        (SlotType::Length, SlotValue::Literal(v)) => check_length(name, v).map(|_| ()),
        (SlotType::Length, SlotValue::Bounded(lo, hi)) => {
            let lo_q = check_length(name, lo)?;
            let hi_q = check_length(name, hi)?;
            match hi_q.sub(&lo_q) {
                Ok(d) if d.magnitude() >= 0.0 => Ok(()),
                Ok(_) => Err(format!("slot `{name}` bounds `[{lo}, {hi}]` are inverted")),
                Err(e) => Err(format!("slot `{name}` bounds `[{lo}, {hi}]`: {e}")),
            }
        }
        (SlotType::Length, SlotValue::Discrete(items)) => items
            .iter()
            .try_for_each(|i| check_length(name, i).map(|_| ())),
        (SlotType::Fraction, SlotValue::Literal(v)) => check_fraction(name, v),
        (SlotType::Fraction, SlotValue::Bounded(lo, hi)) => {
            check_fraction(name, lo)?;
            check_fraction(name, hi)?;
            if fraction_of(lo) > fraction_of(hi) {
                return Err(format!("slot `{name}` bounds `[{lo}, {hi}]` are inverted"));
            }
            Ok(())
        }
        (SlotType::Fraction, SlotValue::Discrete(items)) => {
            items.iter().try_for_each(|i| check_fraction(name, i))
        }
        (SlotType::Cell, SlotValue::Literal(v)) => check_cell(name, v),
        (SlotType::Cell, SlotValue::Discrete(items)) => {
            items.iter().try_for_each(|i| check_cell(name, i))
        }
        (SlotType::Cell, SlotValue::Bounded(lo, hi)) => Err(format!(
            "slot `{name}` is a discrete cell name, not a bounded range \
             (`[{lo}, {hi}]` spelled)"
        )),
    }
}

/// A positive integer literal.
fn check_int(name: &str, text: &str) -> Result<(), String> {
    match text.parse::<u32>() {
        Ok(n) if n >= 1 => Ok(()),
        _ => Err(format!(
            "slot `{name}` must be a positive integer, got `{text}`"
        )),
    }
}

/// A length-dimensioned quantity literal (`18mm`); returns the parsed
/// quantity so bound ordering can be checked across units.
fn check_length(name: &str, text: &str) -> Result<Qty, String> {
    let bytes = text.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() && (bytes[i].is_ascii_digit() || bytes[i] == b'.') {
        i += 1;
    }
    let Ok(magnitude) = text[..i].parse::<f64>() else {
        return Err(format!(
            "slot `{name}` must be a length quantity (e.g. `18mm`), got `{text}`"
        ));
    };
    let suffix = text[i..].trim();
    let Ok(unit) = Unit::parse_expr(suffix) else {
        return Err(format!(
            "slot `{name}` must be a length quantity (e.g. `18mm`), got `{text}` \
             (unknown unit `{suffix}`)"
        ));
    };
    if unit.dimension != Dimension::base(BaseDimension::Length) {
        return Err(format!(
            "slot `{name}` must be a LENGTH, got `{text}` (dimension of `{suffix}`)"
        ));
    }
    Ok(Qty::new(magnitude, unit))
}

/// A bare fraction literal in `[0, 1]`.
fn check_fraction(name: &str, text: &str) -> Result<(), String> {
    match text.parse::<f64>() {
        Ok(v) if (0.0..=1.0).contains(&v) => Ok(()),
        Ok(v) => Err(format!(
            "slot `{name}` must be a fraction in [0, 1], got `{v}`"
        )),
        Err(_) => Err(format!(
            "slot `{name}` must be a fraction in [0, 1], got `{text}`"
        )),
    }
}

/// A cell name from the closed v1 set.
fn check_cell(name: &str, text: &str) -> Result<(), String> {
    if LATTICE_CELLS.contains(&text) {
        Ok(())
    } else {
        Err(format!(
            "slot `{name}` names unknown cell `{text}` (v1 cells: {})",
            LATTICE_CELLS.join(", ")
        ))
    }
}

/// Parsed integer for bound-order checks (validated by `check_int`).
fn int_of(text: &str) -> u32 {
    text.parse::<u32>().unwrap_or(0)
}

/// Parsed fraction for bound-order checks (validated by
/// `check_fraction`).
fn fraction_of(text: &str) -> f64 {
    text.parse::<f64>().unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ribs() -> &'static FamilySpec {
        family_for_constructor("Ribs").unwrap()
    }

    #[test]
    fn bounded_and_literal_slots_parse_and_validate() {
        let params = validate_family_params(
            ribs(),
            "Ribs(count in [4, 12], pitch=18mm, thickness in [2mm, 5mm], height=12mm)",
        )
        .unwrap();
        assert_eq!(params["count"].text, "[4, 12]");
        assert_eq!(params["count"].cause, "planner");
        assert_eq!(params["pitch"].text, "18mm");
        assert_eq!(params["pitch"].cause, "literal");
        assert_eq!(params["thickness"].cause, "planner");
        assert_eq!(params["height"].cause, "literal");
    }

    #[test]
    fn eq_in_form_is_the_same_bounded_slot() {
        let params =
            validate_family_params(ribs(), "Ribs(count = in [4, 8], pitch=18mm, thickness=3mm)")
                .unwrap();
        assert_eq!(params["count"].text, "[4, 8]");
        assert_eq!(params["count"].cause, "planner");
    }

    #[test]
    fn missing_required_slot_is_malformed() {
        let errs = validate_family_params(ribs(), "Ribs(count=4, pitch=18mm)").unwrap_err();
        assert!(
            errs.iter().any(|e| e.contains("`thickness` is missing")),
            "{errs:?}"
        );
    }

    #[test]
    fn unknown_and_duplicate_slots_are_malformed() {
        let errs = validate_family_params(
            ribs(),
            "Ribs(count=4, pitch=18mm, thickness=3mm, thickness=4mm, girth=2mm)",
        )
        .unwrap_err();
        assert!(
            errs.iter().any(|e| e.contains("unknown slot `girth`")),
            "{errs:?}"
        );
        assert!(
            errs.iter().any(|e| e.contains("more than once")),
            "{errs:?}"
        );
    }

    #[test]
    fn wrong_dimension_values_are_malformed() {
        // count given a length; thickness given a bare number.
        let errs =
            validate_family_params(ribs(), "Ribs(count=3mm, pitch=18mm, thickness=3)").unwrap_err();
        assert!(
            errs.iter()
                .any(|e| e.contains("`count` must be a positive integer")),
            "{errs:?}"
        );
        assert!(
            errs.iter()
                .any(|e| e.contains("`thickness` must be a length")),
            "{errs:?}"
        );
    }

    #[test]
    fn inverted_bounds_are_malformed() {
        let errs =
            validate_family_params(ribs(), "Ribs(count in [12, 4], pitch=18mm, thickness=3mm)")
                .unwrap_err();
        assert!(errs.iter().any(|e| e.contains("inverted")), "{errs:?}");
    }

    #[test]
    fn lattice_density_and_cell_domains_are_closed() {
        let lattice = family_for_constructor("Lattice").unwrap();
        let errs =
            validate_family_params(lattice, "Lattice(cell=voronoi, density=1.4)").unwrap_err();
        assert!(
            errs.iter().any(|e| e.contains("unknown cell `voronoi`")),
            "{errs:?}"
        );
        assert!(
            errs.iter().any(|e| e.contains("fraction in [0, 1]")),
            "{errs:?}"
        );

        let params = validate_family_params(
            lattice,
            "Lattice(cell in {gyroid, honeycomb}, density in [0.2, 0.4])",
        )
        .unwrap();
        assert_eq!(params["cell"].text, "{gyroid, honeycomb}");
        assert_eq!(params["cell"].cause, "planner");
        assert_eq!(params["density"].text, "[0.2, 0.4]");
    }

    #[test]
    fn shell_t_slot_emits_under_the_thickness_key() {
        let shell = family_for_constructor("Shell").unwrap();
        let params = validate_family_params(shell, "Shell(t=2mm)").unwrap();
        assert_eq!(params["thickness"].text, "2mm");
        assert!(validate_family_params(shell, "Shell()").is_err());
    }

    #[test]
    fn rect_pocket_family_validates_and_carries_optional_radius() {
        let rp = family_for_constructor("RectPocket").unwrap();
        let params = validate_family_params(
            rp,
            "RectPocket(width=40mm, depth_xy=20mm, height=10mm, corner_radius=2mm)",
        )
        .unwrap();
        assert_eq!(params["width"].text, "40mm");
        assert_eq!(params["depth_xy"].cause, "literal");
        assert_eq!(params["corner_radius"].text, "2mm");
        // corner_radius is optional; a bounded planner slot is accepted.
        let p2 = validate_family_params(
            rp,
            "RectPocket(width in [30mm, 50mm], depth_xy=20mm, height=10mm)",
        )
        .unwrap();
        assert_eq!(p2["width"].cause, "planner");
        assert!(!p2.contains_key("corner_radius"));
        // missing required height is malformed.
        assert!(validate_family_params(rp, "RectPocket(width=40mm, depth_xy=20mm)").is_err());
    }

    #[test]
    fn family_measures_mirror_the_param_texts() {
        let m = super::family_measures(
            ribs(),
            "Ribs(count in [4, 12], pitch=18mm, thickness in [2mm, 5mm])",
        );
        assert_eq!(m["count"], "[4, 12]");
        assert_eq!(m["pitch"], "18mm");
    }

    #[test]
    fn cross_unit_length_bounds_compare_correctly() {
        // 0.2cm..5mm is a legal (non-inverted) bound across units.
        let ok = validate_family_params(
            ribs(),
            "Ribs(count=4, pitch=18mm, thickness in [0.2cm, 5mm])",
        );
        assert!(ok.is_ok(), "{ok:?}");
    }
}
