//! The board entity-population pass (WO-87, D198): declared-topology
//! extraction for a `board` decl, committing the elec structural
//! entities (`EntityKind::Instance`/`Net`) and the derived
//! board-correctness domains (`Other("power_pins")`, ...) the
//! `std.board_correctness` packs (WO-79, charter 36) quantify over.
//!
//! DECLARED vs REALIZED (the D198 ruling): this pass reads what the
//! source SPELLS -- `then:` vendor instances, `nets:` membership
//! tuples, `straps:` bindings -- plus the registry-records payload
//! (`crate::registry`, the D198 channel) for record facts (component
//! class, capacitance, exposure class). Placement/routing-aware
//! topology (cap DISTANCE, probe clearance, clock-driver attribution,
//! reset-supervision requirements) is WO-24/WO-35 realizer territory:
//! those fields stay unprovided here and the dependent rules defer
//! honestly (D-E), never fabricate.
//!
//! ## The derivations (each cited to its consuming pack)
//!
//! - `instances`: every `then:`-scope `name = vendor(<key>)` ctor.
//! - `nets`: every `nets:` block entry, with its member pin list;
//!   measure `undecoupled_power_pin_count` = member power pins with
//!   zero shunt caps (std.elec.patterns.decoupling_shape's fact).
//! - `power_pins`: for each instance whose record states
//!   `power_pin_names` (datasheet pin table, AD-34 sourcing law), one
//!   entity per named pin; `shunt_cap_count`/`shunt_cap_value` from
//!   bypass-tier capacitor instances sharing the pin's net.
//! - `rails`: nets carrying at least one power pin; `bulk_cap_count`
//!   from bulk-tier caps on the net (the pdn pack's two-tier law).
//! - Capacitor TIERS are derived from the record's stated
//!   `capacitance_pf` (the record fact) by the class bands the pdn
//!   pack itself cites (Horowitz & Hill sec. 7 / the "100nF class"):
//!   load < 1nF <= bypass < 10uF <= bulk.
//! - `config_straps`: every `straps:` block binding;
//!   `pull_state_defined` = 1 for an explicit pull/drive/tie head, 0
//!   for a declared `floating(...)` (bringup_config.strap_not_floating).
//! - `crystals`: instances whose record `class = crystal`;
//!   `c_load_calculated` = the series combination of exactly two
//!   load-tier caps on the crystal's nets (the sizing formula the
//!   clock_discipline pack header cites; board+pin STRAY capacitance
//!   is a layout fact, omitted at the declared tier and documented as
//!   such). The record's `cl` resolves at rule-eval time through the
//!   registry handle (the WO-87 dereference seam), not by copying it
//!   into measures.
//! - `exposed_connectors`: connector-class instances whose record
//!   `exposure_class = external` (the WO-79 field);
//!   `esd_protection_count` from tvs-class instances sharing a net.
//! - `exposed_nets`: nets carrying an exposed connector's pin;
//!   `tvs_count` from tvs-class instances on the net.
//! - `critical_nets`: rails plus strap-bound nets (the dft pack's own
//!   "power rail, reset, boot strap" criteria);
//!   `test_point_count` from test_point-class instances on the net.
//! - `test_points`: test_point-class instances; `pad_diameter_mm`
//!   from the record; `probe_clearance_mm` stays realized-tier.
//! - `control_boards`: the board itself when it hosts an mcu-class
//!   instance; `debug_header_count` from debug_header-class instances
//!   (bringup_config.debug_header_presence).
//!
//! `supervised_rails` and `clock_nets` are vocabulary-only (see
//! `regolith_sem::entity::board_domain_measure_keys`): no honest
//! declared-tier source exists for their facts, so they stay empty.

use regolith_sem::{Entity, EntityId, EntityKind, Measures};
use regolith_syntax::ast::{AstNode, Decl, Field};
use regolith_syntax::syntax_kind::SyntaxKind;
use regolith_util::{IndexMap, IndexSet};

use crate::registry::RegistryRecords;

/// One declared instance: `u1 = vendor(rp2040)`.
#[derive(Debug, Clone)]
struct DeclaredInstance {
    binding: String,
    record_key: String,
}

/// One declared net: name plus its `inst.pin` member spellings.
#[derive(Debug, Clone)]
struct DeclaredNet {
    name: String,
    members: Vec<String>,
}

/// One declared strap binding: `boot_sel: pull_up(u1.bootsel, 10kOhm)`.
#[derive(Debug, Clone)]
struct DeclaredStrap {
    name: String,
    head: String,
    pin: Option<String>,
}

/// The capacitor tier bands (picofarads) the pdn pack's class language
/// cites (Horowitz & Hill sec. 7 two-tier law; the "100nF class").
const BYPASS_MIN_PF: f64 = 1_000.0; // 1nF
const BULK_MIN_PF: f64 = 10_000_000.0; // 10uF

/// A capacitor's derived application tier.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CapTier {
    /// Crystal load caps and similar small-value parts (< 1nF).
    Load,
    /// Per-pin HF bypass class ([1nF, 10uF)).
    Bypass,
    /// Per-rail bulk reservoir class (>= 10uF).
    Bulk,
}

/// Populate the declared-topology entities for `decl` when it is a
/// `board` declaration; anything else yields nothing (the pass is
/// board-scoped by the WO). `next_id` advances past every allocated id
/// (the `feature_entities` convention, AD-6 determinism).
#[must_use]
pub fn board_entities(
    decl: &Decl,
    owner: &str,
    registry: &RegistryRecords,
    next_id: &mut u32,
) -> Vec<Entity> {
    if decl.kind_keyword() != Some(SyntaxKind::BoardKw) {
        return Vec::new();
    }
    let span = tracing::debug_span!("lower.entities.board", board = %owner);
    let _enter = span.enter();

    let instances = collect_instances(decl);
    let nets = collect_nets(decl);
    let straps = collect_straps(decl);
    tracing::debug!(
        instances = instances.len(),
        nets = nets.len(),
        straps = straps.len(),
        "declared board topology collected"
    );

    let class_of = |inst: &DeclaredInstance| -> Option<String> {
        registry.field(&inst.record_key, "class")
    };
    let cap_tier = |inst: &DeclaredInstance| -> Option<CapTier> {
        if class_of(inst).as_deref() != Some("capacitor") {
            return None;
        }
        let pf: f64 = registry
            .field(&inst.record_key, "capacitance_pf")?
            .parse()
            .ok()?;
        Some(if pf >= BULK_MIN_PF {
            CapTier::Bulk
        } else if pf >= BYPASS_MIN_PF {
            CapTier::Bypass
        } else {
            CapTier::Load
        })
    };

    // Membership indexes: pin spelling -> net names; instance binding
    // -> net names (an instance is "on" a net when any of its pins is).
    let mut nets_of_pin: IndexMap<&str, Vec<&str>> = IndexMap::new();
    let mut nets_of_inst: IndexMap<&str, IndexSet<&str>> = IndexMap::new();
    for net in &nets {
        for member in &net.members {
            nets_of_pin
                .entry(member.as_str())
                .or_default()
                .push(net.name.as_str());
            if let Some((inst, _pin)) = member.split_once('.') {
                nets_of_inst
                    .entry(instances_binding(&instances, inst).unwrap_or(""))
                    .or_default()
                    .insert(net.name.as_str());
            }
        }
    }
    nets_of_inst.shift_remove("");

    // Caps-by-tier per net: net name -> [(binding, capacitance_pf)].
    let mut caps_on_net: IndexMap<&str, Vec<(&str, CapTier, f64)>> = IndexMap::new();
    for inst in &instances {
        let Some(tier) = cap_tier(inst) else { continue };
        let pf: f64 = registry
            .field(&inst.record_key, "capacitance_pf")
            .and_then(|v| v.parse().ok())
            .unwrap_or(0.0);
        if let Some(net_names) = nets_of_inst.get(inst.binding.as_str()) {
            for net_name in net_names {
                caps_on_net
                    .entry(net_name)
                    .or_default()
                    .push((inst.binding.as_str(), tier, pf));
            }
        }
    }
    let tier_count_on = |net: &str, tier: CapTier| -> usize {
        caps_on_net
            .get(net)
            .map(|caps| {
                caps.iter()
                    .filter(|(_, t, _)| *t == tier)
                    .map(|(b, _, _)| *b)
                    .collect::<IndexSet<&str>>()
                    .len()
            })
            .unwrap_or(0)
    };

    let count_class_on_net = |net: &str, class: &str| -> usize {
        instances
            .iter()
            .filter(|inst| class_of(inst).as_deref() == Some(class))
            .filter(|inst| {
                nets_of_inst
                    .get(inst.binding.as_str())
                    .is_some_and(|ns| ns.contains(net))
            })
            .count()
    };

    let mut out: Vec<Entity> = Vec::new();
    let mut emit = |origin: String, kind: EntityKind, measures: Measures| {
        let id = EntityId(*next_id);
        *next_id += 1;
        tracing::debug!(owner = %owner, origin = %origin, ?kind, id = id.0, "board entity committed");
        out.push(Entity {
            id,
            origin,
            owner: owner.to_string(),
            kind,
            measures,
            tags: IndexSet::new(),
            orbit: None,
        });
    };

    // ---- Instance entities ----
    for inst in &instances {
        let mut m = Measures::new();
        m.insert("record".to_string(), inst.record_key.clone());
        emit(inst.binding.clone(), EntityKind::Instance, m);
    }

    // ---- power_pins + per-net undecoupled counts ----
    // pin spelling -> shunt_cap_count (feeds the net derivation).
    let mut power_pin_shunts: IndexMap<String, usize> = IndexMap::new();
    for inst in &instances {
        let Some(pin_names) = registry.field(&inst.record_key, "power_pin_names") else {
            continue;
        };
        for pin in pin_names.split(',').map(str::trim).filter(|p| !p.is_empty()) {
            let spelling = format!("{}.{}", inst.binding, pin);
            let pin_nets = nets_of_pin.get(spelling.as_str());
            let (shunt_count, shunt_max_pf) = pin_nets.map_or((0, None), |ns| {
                let mut count = 0usize;
                let mut max_pf: Option<f64> = None;
                let mut seen: IndexSet<&str> = IndexSet::new();
                for net in ns {
                    if let Some(caps) = caps_on_net.get(net) {
                        for (binding, tier, pf) in caps {
                            if *tier == CapTier::Bypass && seen.insert(binding) {
                                count += 1;
                                max_pf = Some(max_pf.map_or(*pf, |m: f64| m.max(*pf)));
                            }
                        }
                    }
                }
                (count, max_pf)
            });
            let mut m = Measures::new();
            m.insert("shunt_cap_count".to_string(), shunt_count.to_string());
            if let Some(pf) = shunt_max_pf {
                m.insert("shunt_cap_value".to_string(), render_pf(pf));
            }
            power_pin_shunts.insert(spelling.clone(), shunt_count);
            emit(spelling, EntityKind::Other("power_pins".to_string()), m);
        }
    }

    // ---- Net entities (with the decoupling pack's derived count) ----
    for net in &nets {
        let undecoupled = net
            .members
            .iter()
            .filter(|m| power_pin_shunts.get(*m).is_some_and(|c| *c == 0))
            .count();
        let mut m = Measures::new();
        m.insert("members".to_string(), net.members.join(","));
        m.insert("member_count".to_string(), net.members.len().to_string());
        m.insert(
            "undecoupled_power_pin_count".to_string(),
            undecoupled.to_string(),
        );
        emit(net.name.clone(), EntityKind::Net, m);
    }

    // ---- rails (nets carrying a power pin) ----
    let mut rail_names: IndexSet<&str> = IndexSet::new();
    for (pin, ns) in &nets_of_pin {
        if power_pin_shunts.contains_key(*pin) {
            rail_names.extend(ns.iter().copied());
        }
    }
    for rail in &rail_names {
        let mut m = Measures::new();
        m.insert(
            "bulk_cap_count".to_string(),
            tier_count_on(rail, CapTier::Bulk).to_string(),
        );
        emit((*rail).to_string(), EntityKind::Other("rails".to_string()), m);
    }

    // ---- config_straps ----
    for strap in &straps {
        let mut m = Measures::new();
        let defined = match strap.head.as_str() {
            "pull_up" | "pull_down" | "drive_high" | "drive_low" | "tied" => Some("1"),
            "floating" => Some("0"),
            other => {
                tracing::debug!(
                    strap = %strap.name,
                    head = %other,
                    "unrecognized strap binding head; pull state stays unprovided (defers)"
                );
                None
            }
        };
        if let Some(v) = defined {
            m.insert("pull_state_defined".to_string(), v.to_string());
        }
        if let Some(pin) = &strap.pin {
            m.insert("pin".to_string(), pin.clone());
        }
        emit(
            strap.name.clone(),
            EntityKind::Other("config_straps".to_string()),
            m,
        );
    }

    // ---- crystals ----
    for inst in &instances {
        if class_of(inst).as_deref() != Some("crystal") {
            continue;
        }
        let mut m = Measures::new();
        m.insert("record".to_string(), inst.record_key.clone());
        // Series combination of exactly two load-tier caps on the
        // crystal's nets; any other count is honestly unprovided.
        let mut load_caps: IndexMap<&str, f64> = IndexMap::new();
        if let Some(ns) = nets_of_inst.get(inst.binding.as_str()) {
            for net in ns {
                if let Some(caps) = caps_on_net.get(net) {
                    for (binding, tier, pf) in caps {
                        if *tier == CapTier::Load {
                            load_caps.insert(binding, *pf);
                        }
                    }
                }
            }
        }
        if load_caps.len() == 2 {
            let vals: Vec<f64> = load_caps.values().copied().collect();
            let series = (vals[0] * vals[1]) / (vals[0] + vals[1]);
            m.insert("c_load_calculated".to_string(), render_pf(series));
        } else {
            tracing::debug!(
                crystal = %inst.binding,
                load_caps = load_caps.len(),
                "crystal without exactly two load caps on its nets; \
                 c_load_calculated stays unprovided (defers)"
            );
        }
        emit(
            inst.binding.clone(),
            EntityKind::Other("crystals".to_string()),
            m,
        );
    }

    // ---- exposed_connectors + exposed_nets ----
    let mut exposed_pin_nets: IndexSet<&str> = IndexSet::new();
    for inst in &instances {
        if class_of(inst).as_deref() != Some("connector")
            || registry.field(&inst.record_key, "exposure_class").as_deref() != Some("external")
        {
            continue;
        }
        let inst_nets = nets_of_inst.get(inst.binding.as_str());
        let esd = inst_nets.map_or(0usize, |ns| {
            let mut seen: IndexSet<String> = IndexSet::new();
            for net in ns {
                exposed_pin_nets.insert(net);
                for other in &instances {
                    if class_of(other).as_deref() == Some("tvs")
                        && nets_of_inst
                            .get(other.binding.as_str())
                            .is_some_and(|ons| ons.contains(net))
                    {
                        seen.insert(other.binding.clone());
                    }
                }
            }
            seen.len()
        });
        let mut m = Measures::new();
        m.insert("record".to_string(), inst.record_key.clone());
        m.insert("esd_protection_count".to_string(), esd.to_string());
        if let Some(class) = registry.field(&inst.record_key, "connector_class") {
            m.insert("class".to_string(), class);
        }
        emit(
            inst.binding.clone(),
            EntityKind::Other("exposed_connectors".to_string()),
            m,
        );
    }
    for net in &exposed_pin_nets {
        let mut m = Measures::new();
        m.insert(
            "tvs_count".to_string(),
            count_class_on_net(net, "tvs").to_string(),
        );
        emit(
            (*net).to_string(),
            EntityKind::Other("exposed_nets".to_string()),
            m,
        );
    }

    // ---- critical_nets (rails + strap-bound nets, the dft criteria) ----
    let mut critical: IndexSet<&str> = rail_names.clone();
    for strap in &straps {
        if let Some(pin) = &strap.pin {
            if let Some(ns) = nets_of_pin.get(pin.as_str()) {
                critical.extend(ns.iter().copied());
            }
        }
    }
    for net in &critical {
        let mut m = Measures::new();
        m.insert(
            "test_point_count".to_string(),
            count_class_on_net(net, "test_point").to_string(),
        );
        emit(
            (*net).to_string(),
            EntityKind::Other("critical_nets".to_string()),
            m,
        );
    }

    // ---- test_points ----
    for inst in &instances {
        if class_of(inst).as_deref() != Some("test_point") {
            continue;
        }
        let mut m = Measures::new();
        m.insert("record".to_string(), inst.record_key.clone());
        if let Some(pad) = registry.field(&inst.record_key, "pad_diameter_mm") {
            m.insert("pad_diameter_mm".to_string(), pad);
        }
        emit(
            inst.binding.clone(),
            EntityKind::Other("test_points".to_string()),
            m,
        );
    }

    // ---- control_boards ----
    if instances
        .iter()
        .any(|inst| class_of(inst).as_deref() == Some("mcu"))
    {
        let debug_headers = instances
            .iter()
            .filter(|inst| class_of(inst).as_deref() == Some("debug_header"))
            .count();
        let mut m = Measures::new();
        m.insert("debug_header_count".to_string(), debug_headers.to_string());
        emit(
            owner.to_string(),
            EntityKind::Other("control_boards".to_string()),
            m,
        );
    }

    tracing::debug!(entities = out.len(), "board entity population complete");
    out
}

/// Resolve a member's instance prefix to its declared binding (exact
/// match today; a helper so orbit/alias handling has one home later).
fn instances_binding<'a>(instances: &'a [DeclaredInstance], name: &str) -> Option<&'a str> {
    instances
        .iter()
        .find(|i| i.binding == name)
        .map(|i| i.binding.as_str())
}

/// Every `then:`-scope `name = vendor(<key>)` instance of `decl`.
fn collect_instances(decl: &Decl) -> Vec<DeclaredInstance> {
    let mut out = Vec::new();
    for call in crate::claim_scope::feature_calls_in_decl(decl) {
        if call.head != "vendor" {
            continue;
        }
        // `args_text` is the raw RHS (`vendor(rp2040)`); the record key
        // is the bare identifier inside the call's parentheses.
        let inner = call
            .args_text
            .split_once('(')
            .map_or(call.args_text.as_str(), |(_, rest)| rest);
        let key: String = inner
            .trim_start()
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '.')
            .collect();
        if key.is_empty() {
            tracing::debug!(binding = %call.binding, "vendor() with no record key; skipped");
            continue;
        }
        out.push(DeclaredInstance {
            binding: call.binding.clone(),
            record_key: key,
        });
    }
    out
}

/// Every declared net of `decl`: `nets:` block entries (explicit
/// member tuples) plus `connect:` mating lines (D198 names both
/// sources -- a `connect` line's dotted port references are its
/// connection's declared members).
fn collect_nets(decl: &Decl) -> Vec<DeclaredNet> {
    let mut out = Vec::new();
    for field in named_block_fields(decl, "nets") {
        let name = field.name();
        let members = member_spellings(&field);
        out.push(DeclaredNet { name, members });
    }
    for call in crate::claim_scope::connect_calls_in_decl(decl) {
        let members = dotted_paths(&call.args_text);
        out.push(DeclaredNet {
            name: call.binding,
            members,
        });
    }
    out
}

/// Every `inst.pin`-shaped dotted path in `text` (a connect line's
/// argument list), in source order.
fn dotted_paths(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut chars = text.char_indices().peekable();
    while let Some((start, c)) = chars.next() {
        if !(c.is_ascii_alphabetic() || c == '_') {
            continue;
        }
        // Skip if preceded by an ident char (mid-token).
        if start > 0
            && text[..start]
                .chars()
                .next_back()
                .is_some_and(|p| p.is_ascii_alphanumeric() || p == '_' || p == '.')
        {
            continue;
        }
        let mut end = start + c.len_utf8();
        while let Some(&(i, n)) = chars.peek() {
            if n.is_ascii_alphanumeric() || n == '_' || n == '.' {
                end = i + n.len_utf8();
                chars.next();
            } else {
                break;
            }
        }
        let token = text[start..end].trim_end_matches('.');
        if token.contains('.') {
            out.push(token.to_string());
        }
    }
    out
}

/// Every `straps:` block binding of `decl`.
fn collect_straps(decl: &Decl) -> Vec<DeclaredStrap> {
    let mut out = Vec::new();
    for field in named_block_fields(decl, "straps") {
        let name = field.name();
        let text = colon_rhs_text(&field);
        let head: String = text
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
            .collect();
        let pin = text
            .split_once('(')
            .map(|(_, rest)| rest)
            .and_then(|rest| {
                let arg: String = rest
                    .chars()
                    .take_while(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '.')
                    .collect();
                (!arg.is_empty()).then_some(arg)
            });
        out.push(DeclaredStrap { name, head, pin });
    }
    out
}

/// The nested `Field` children of the direct-child block field of
/// `decl` named `block_name` (`nets:` / `straps:` -- the shared
/// structured field-block grammar, the same shape `connect:` parses).
fn named_block_fields(decl: &Decl, block_name: &str) -> Vec<Field> {
    let mut out = Vec::new();
    for node in decl.syntax().children() {
        let Some(field) = Field::cast(node.clone()) else {
            continue;
        };
        if field.name() != block_name {
            continue;
        }
        for child in node.children() {
            if let Some(inner) = Field::cast(child) {
                out.push(inner);
            }
        }
    }
    out
}

/// The raw text after the field's first-line `:` with any trailing
/// comment stripped (the tuple grammar only partially structures net
/// member lists -- `(a.b` parses, `, c.d)` sweeps to an opaque island
/// -- so the member scan reads the spelled text, the same stance as
/// `rule_engine::field_value_text_or_rhs`).
fn colon_rhs_text(field: &Field) -> String {
    let full = field.syntax().text().to_string();
    let first_line = full.lines().next().unwrap_or("");
    let first_line = first_line.split('#').next().unwrap_or("");
    first_line
        .split_once(':')
        .map(|(_, rhs)| rhs.trim().to_string())
        .unwrap_or_default()
}

/// The `inst.pin` member spellings of a net entry's tuple text.
fn member_spellings(field: &Field) -> Vec<String> {
    let rhs = colon_rhs_text(field);
    let inner = rhs
        .trim()
        .trim_start_matches('(')
        .trim_end_matches(')')
        .to_string();
    inner
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
        .collect()
}

/// Render a picofarad magnitude as the `<n>pF` literal the quantity
/// grammar re-parses (trailing-zero trimming per `render_qty`'s rule).
fn render_pf(pf: f64) -> String {
    let mut s = format!("{pf:.6}");
    if s.contains('.') {
        while s.ends_with('0') {
            s.pop();
        }
        if s.ends_with('.') {
            s.pop();
        }
    }
    format!("{s}pF")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::output::ParsedFile;
    use camino::Utf8PathBuf;

    const BOARD: &str = "board B1:\n    then:\n        u1 = vendor(rp2040_board_min)\n        x1 = vendor(abracon_abm8_16mhz_18pf)\n        j1 = vendor(jst_xh_2p)\n        c1 = vendor(cap_100nf_x7r_0402)\n        cb1 = vendor(cap_22uf_x5r_0805)\n        cl1 = vendor(cap_36pf_c0g_0402)\n        cl2 = vendor(cap_36pf_c0g_0402)\n        d1 = vendor(tvs_pesd5v0s1ba)\n        tp1 = vendor(tp_smd_keystone_5015)\n        sw1 = vendor(swd_header_ftsh_105)\n    nets:\n        v3v3: (u1.iovdd, c1.p1, cb1.p1, tp1.p1)\n        gnd: (u1.gnd, c1.p2, cb1.p2)\n        xin: (x1.p1, u1.xin, cl1.p1)\n        xout: (x1.p2, u1.xout, cl2.p1)\n        vext: (j1.pin1, d1.p1)\n    straps:\n        boot_sel: pull_up(u1.bootsel, 10kOhm)\n        qspi_ss: floating(u1.qspi_ss)\n";

    fn registry() -> RegistryRecords {
        RegistryRecords::from_pairs(&[
            (
                "rp2040_board_min",
                &[("class", "mcu"), ("power_pin_names", "iovdd, dvdd")],
            ),
            (
                "abracon_abm8_16mhz_18pf",
                &[("class", "crystal"), ("cl_pf", "18")],
            ),
            (
                "jst_xh_2p",
                &[
                    ("class", "connector"),
                    ("exposure_class", "external"),
                    ("connector_class", "power"),
                ],
            ),
            (
                "cap_100nf_x7r_0402",
                &[("class", "capacitor"), ("capacitance_pf", "100000")],
            ),
            (
                "cap_22uf_x5r_0805",
                &[("class", "capacitor"), ("capacitance_pf", "22000000")],
            ),
            (
                "cap_36pf_c0g_0402",
                &[("class", "capacitor"), ("capacitance_pf", "36")],
            ),
            ("tvs_pesd5v0s1ba", &[("class", "tvs")]),
            (
                "tp_smd_keystone_5015",
                &[("class", "test_point"), ("pad_diameter_mm", "2.03")],
            ),
            ("swd_header_ftsh_105", &[("class", "debug_header")]),
        ])
    }

    fn populate(src: &str) -> Vec<Entity> {
        let path = Utf8PathBuf::from("t.cupr");
        let pf = ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        };
        let file = regolith_syntax::ast::File::cast(pf.parse.syntax()).unwrap();
        let decl = file.decls().into_iter().next().unwrap();
        let mut next_id = 1u32;
        board_entities(&decl, "B1", &registry(), &mut next_id)
    }

    fn find<'a>(entities: &'a [Entity], kind: &EntityKind, origin: &str) -> &'a Entity {
        entities
            .iter()
            .find(|e| &e.kind == kind && e.origin == origin)
            .unwrap_or_else(|| panic!("no {kind:?} entity with origin {origin}"))
    }

    #[test]
    fn power_pins_derive_shunt_counts_from_net_membership() {
        let entities = populate(BOARD);
        let kind = EntityKind::Other("power_pins".to_string());
        let iovdd = find(&entities, &kind, "u1.iovdd");
        assert_eq!(iovdd.measures.get("shunt_cap_count").unwrap(), "1");
        assert_eq!(iovdd.measures.get("shunt_cap_value").unwrap(), "100000pF");
        // dvdd is declared a power pin by the record but wired to no
        // net: zero shunt coverage, honestly.
        let dvdd = find(&entities, &kind, "u1.dvdd");
        assert_eq!(dvdd.measures.get("shunt_cap_count").unwrap(), "0");
    }

    #[test]
    fn rails_and_critical_nets_carry_bulk_and_test_point_counts() {
        let entities = populate(BOARD);
        let rail = find(&entities, &EntityKind::Other("rails".to_string()), "v3v3");
        assert_eq!(rail.measures.get("bulk_cap_count").unwrap(), "1");
        let crit = find(
            &entities,
            &EntityKind::Other("critical_nets".to_string()),
            "v3v3",
        );
        assert_eq!(crit.measures.get("test_point_count").unwrap(), "1");
    }

    #[test]
    fn straps_carry_pull_state_defined_both_ways() {
        let entities = populate(BOARD);
        let kind = EntityKind::Other("config_straps".to_string());
        let pulled = find(&entities, &kind, "boot_sel");
        assert_eq!(pulled.measures.get("pull_state_defined").unwrap(), "1");
        let floating = find(&entities, &kind, "qspi_ss");
        assert_eq!(floating.measures.get("pull_state_defined").unwrap(), "0");
    }

    #[test]
    fn crystal_series_load_caps_compute_c_load() {
        let entities = populate(BOARD);
        let xtal = find(&entities, &EntityKind::Other("crystals".to_string()), "x1");
        // Two 36pF caps in series = 18pF.
        assert_eq!(xtal.measures.get("c_load_calculated").unwrap(), "18pF");
        assert_eq!(xtal.measures.get("record").unwrap(), "abracon_abm8_16mhz_18pf");
    }

    #[test]
    fn exposed_connector_and_net_count_tvs_protection() {
        let entities = populate(BOARD);
        let conn = find(
            &entities,
            &EntityKind::Other("exposed_connectors".to_string()),
            "j1",
        );
        assert_eq!(conn.measures.get("esd_protection_count").unwrap(), "1");
        assert_eq!(conn.measures.get("class").unwrap(), "power");
        let net = find(&entities, &EntityKind::Other("exposed_nets".to_string()), "vext");
        assert_eq!(net.measures.get("tvs_count").unwrap(), "1");
    }

    #[test]
    fn control_board_counts_debug_headers_and_nets_count_undecoupled() {
        let entities = populate(BOARD);
        let cb = find(
            &entities,
            &EntityKind::Other("control_boards".to_string()),
            "B1",
        );
        assert_eq!(cb.measures.get("debug_header_count").unwrap(), "1");
        let v3v3 = find(&entities, &EntityKind::Net, "v3v3");
        assert_eq!(
            v3v3.measures.get("undecoupled_power_pin_count").unwrap(),
            "0"
        );
    }

    #[test]
    fn non_board_decls_and_empty_registry_populate_nothing_extra() {
        let path = Utf8PathBuf::from("t.cupr");
        let pf = ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse("part p:\n    stage s1: process=laser_cut\n", &path),
        };
        let file = regolith_syntax::ast::File::cast(pf.parse.syntax()).unwrap();
        let decl = file.decls().into_iter().next().unwrap();
        let mut next_id = 1u32;
        assert!(board_entities(&decl, "p", &registry(), &mut next_id).is_empty());

        // A board with no registry still commits instances/nets/straps
        // (declared structure) -- record-classified domains stay empty.
        let pf2 = ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(BOARD, &path),
        };
        let file2 = regolith_syntax::ast::File::cast(pf2.parse.syntax()).unwrap();
        let decl2 = file2.decls().into_iter().next().unwrap();
        let mut id2 = 1u32;
        let entities = board_entities(&decl2, "B1", &RegistryRecords::empty(), &mut id2);
        assert!(entities.iter().any(|e| e.kind == EntityKind::Instance));
        assert!(entities.iter().any(|e| e.kind == EntityKind::Net));
        assert!(!entities
            .iter()
            .any(|e| e.kind == EntityKind::Other("crystals".to_string())));
    }

    #[test]
    fn connect_lines_declare_nets_too() {
        // D198: "nets (from connect statements / net decls)" -- a
        // connect: mating line's dotted port refs are declared members.
        let src = "board B2:\n    then:\n        u1 = vendor(rp2040_board_min)\n    connect:\n        grab: BusAttach<fmc>(a=u1.fmc, b=u1.fmc_slave)\n";
        let path = Utf8PathBuf::from("t.cupr");
        let pf = ParsedFile {
            path: path.clone(),
            parse: regolith_syntax::parse(src, &path),
        };
        let file = regolith_syntax::ast::File::cast(pf.parse.syntax()).unwrap();
        let decl = file.decls().into_iter().next().unwrap();
        let mut next_id = 1u32;
        let entities = board_entities(&decl, "B2", &registry(), &mut next_id);
        let net = entities
            .iter()
            .find(|e| e.kind == EntityKind::Net && e.origin == "grab")
            .expect("connect line committed as a net");
        assert!(net.measures.get("members").unwrap().contains("u1.fmc"));
    }
}
