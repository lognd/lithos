//! AD-23: one net core, per-discipline plugins.
//!
//! The net ledger machinery (terminal collection, per-net imposer
//! counting, deterministic traversal) lives ONCE here, parameterized by
//! a [`NetDiscipline`]. A discipline contributes a check predicate over
//! a net's imposer terminals plus its diagnostic message -- it never
//! reimplements the traversal.
//!
//! `elec` (cuprite/03 sec. 2, "at most one voltage-imposing terminal")
//! and `fluid` (fluorite/02 sec. 4, "at least one pressure imposer per
//! subnet") are the two instances this WO ships. Both ride the same
//! [`first_violation`] walk; only the predicate differs.
//!
//! History: before this module, the elec single-driver check lived in
//! Python (`regolith.realizer.elec.netlist.check_single_driver`). AD-23
//! (D100) named two parallel ledgers the failure mode this refit closes
//! -- see `docs/spec/toolchain/00-architecture.md` sec. 23 and its
//! AD-23 CLARIFICATION.

use serde::{Deserialize, Serialize};

/// One terminal on a net: its owning component/pin names, and whether it
/// imposes a state on the net (a driver pin for `elec`, a pressure
/// imposer for `fluid`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct Terminal {
    /// The owning component's ref.
    pub component: String,
    /// The terminal/pin name on that component.
    pub terminal: String,
    /// Whether this terminal imposes a state on the net (elec: a driver
    /// pin; fluid: a pressure imposer).
    pub imposes: bool,
}

/// One net: a name and its terminals, in the order the caller supplies
/// them (AD-6: callers are responsible for deterministic input order;
/// this module never reorders).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct NetEntry {
    /// The net's name.
    pub name: String,
    /// Every terminal joined to this net, in ledger order.
    pub terminals: Vec<Terminal>,
}

/// A discipline violation found on one net: the net name, the imposer
/// terminals that triggered it (`"component.terminal"` form), and the
/// discipline's rendered message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct Violation {
    /// The offending net's name.
    pub net: String,
    /// The imposer terminals found on that net, `"component.terminal"`.
    pub imposers: Vec<String>,
    /// The discipline's rendered message (goldens depend on this text).
    pub message: String,
}

/// A net discipline: a check predicate over one net's imposer terminals.
/// Disciplines are DATA (a predicate + message), not subclass logic --
/// the shared traversal in [`first_violation`] is the only "core".
// frob:doc docs/modules/regolith-sem.md#net-core
pub trait NetDiscipline {
    /// Check one net's imposer terminals (already `"component.terminal"`
    /// formatted, in ledger order). Returns the violation message when
    /// the net breaks this discipline's imposer-count rule.
    fn check_imposers(&self, net_name: &str, imposers: &[String]) -> Option<String>;
}

/// The elec discipline (cuprite/03 sec. 2, "at most one voltage-imposing
/// terminal per net"): more than one driver/imposer pin is an error.
/// Refit verbatim from the former Python
/// `regolith.realizer.elec.netlist.check_single_driver` -- the message
/// text is byte-identical on purpose (goldens depend on it).
#[derive(Debug, Clone, Copy, Default)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct ElecDiscipline;

impl NetDiscipline for ElecDiscipline {
    fn check_imposers(&self, net_name: &str, imposers: &[String]) -> Option<String> {
        if imposers.len() > 1 {
            Some(format!(
                "net '{net_name}' has {} driver pins (single-driver check, cuprite/06)",
                imposers.len()
            ))
        } else {
            None
        }
    }
}

/// The fluid discipline (fluorite/02 sec. 4): at least one pressure
/// imposer (reference, regulator, pump curve, `Imposer`) per subnet --
/// an imposer-free subnet is a compile error, never a solve-time
/// surprise. WO-31 deliverable 3 wires this discipline through
/// `regolith_lower::fluid` to the E0201 (`IMPOSER_FREE_SUBNET`)
/// diagnostic (see the fluorite negative corpus `41_fluo_no_imposer`).
#[derive(Debug, Clone, Copy, Default)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct FluidDiscipline;

impl NetDiscipline for FluidDiscipline {
    fn check_imposers(&self, net_name: &str, imposers: &[String]) -> Option<String> {
        if imposers.is_empty() {
            Some(format!(
                "subnet '{net_name}' has no pressure imposer (imposer-free \
                 subnet, fluorite/02 sec. 4)"
            ))
        } else {
            None
        }
    }
}

/// The load-path discipline (calcite/03 sec. 3, WO-47 deliverable 4):
/// at least one `support:` node per structure subnet -- a subnet with
/// no support is the load-path analog of `FluidDiscipline`'s
/// imposer-free subnet (E0208). Wired through `regolith_lower::calcite`
/// to a real diagnostic (the calcite negative corpus).
///
/// SCOPE CUT (WO-47 close-out): calcite/03 sec. 3 also names support
/// REACHABILITY (E0207, "a member cannot reach a support through
/// transfer edges") and circulation reference reachability (E0205) --
/// both need a graph traversal from every node to a reference/support
/// set, which this module does not yet provide (today's `NetDiscipline`
/// trait only counts imposer terminals per net, it does not walk
/// edges). Adding that traversal is real new machinery, not a
/// discipline-as-data plugin, so it is escalated rather than invented
/// here; see the WO-47 report for the follow-up.
#[derive(Debug, Clone, Copy, Default)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct LoadPathDiscipline;

impl NetDiscipline for LoadPathDiscipline {
    fn check_imposers(&self, net_name: &str, imposers: &[String]) -> Option<String> {
        if imposers.is_empty() {
            Some(format!(
                "structure subnet '{net_name}' has no support node (calcite/03 sec. 3, \
                 the load-path discipline)"
            ))
        } else {
            None
        }
    }
}

/// The circulation discipline (calcite/03 sec. 3, WO-47 deliverable 4):
/// every occupiable space joins the circulation net or is explicitly
/// `unoccupied` -- this module's `check_imposers` predicate reads as
/// "every net must have at least one joined terminal" applied per
/// space, the same terminal-ledger shape `UNJOINED_TERMINAL` (E0202)
/// checks for fluorite, here surfaced as the circulation family's
/// E0204. See [`LoadPathDiscipline`]'s doc comment for the reachability
/// checks (E0205/E0206) this module does NOT cover.
#[derive(Debug, Clone, Copy, Default)]
// frob:doc docs/modules/regolith-sem.md#net-core
pub struct CirculationDiscipline;

impl NetDiscipline for CirculationDiscipline {
    fn check_imposers(&self, net_name: &str, imposers: &[String]) -> Option<String> {
        if imposers.is_empty() {
            Some(format!(
                "space '{net_name}' joins no circulation edge and is not `unoccupied` \
                 (calcite/03 sec. 3, the circulation discipline)"
            ))
        } else {
            None
        }
    }
}

/// Walk `nets` in the given order and return the FIRST discipline
/// violation (fail-fast). This matches the historical elec behavior
/// exactly: the first offending net short-circuits the whole check, it
/// does not accumulate every violation.
#[must_use]
// frob:doc docs/modules/regolith-sem.md#net-core
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn first_violation<D: NetDiscipline>(discipline: &D, nets: &[NetEntry]) -> Option<Violation> {
    for net in nets {
        let imposers: Vec<String> = net
            .terminals
            .iter()
            .filter(|t| t.imposes)
            .map(|t| format!("{}.{}", t.component, t.terminal))
            .collect();
        if let Some(message) = discipline.check_imposers(&net.name, &imposers) {
            return Some(Violation {
                net: net.name.clone(),
                imposers,
                message,
            });
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::{
        first_violation, CirculationDiscipline, ElecDiscipline, FluidDiscipline,
        LoadPathDiscipline, NetEntry, Terminal,
    };

    fn terminal(component: &str, terminal: &str, imposes: bool) -> Terminal {
        Terminal {
            component: component.to_string(),
            terminal: terminal.to_string(),
            imposes,
        }
    }

    // frob:tests crates/regolith-sem/src/net_core.rs::first_violation kind="unit"
    #[test]
    fn elec_single_driver_passes_clean_nets() {
        let nets = vec![NetEntry {
            name: "VCC".to_string(),
            terminals: vec![terminal("u1", "vdd", true), terminal("u2", "vdd", false)],
        }];
        assert_eq!(first_violation(&ElecDiscipline, &nets), None);
    }

    #[test]
    fn elec_single_driver_flags_two_drivers() {
        let nets = vec![NetEntry {
            name: "VCC".to_string(),
            terminals: vec![terminal("u1", "vdd", true), terminal("u2", "vdd", true)],
        }];
        let violation = first_violation(&ElecDiscipline, &nets).expect("violation");
        assert_eq!(violation.net, "VCC");
        assert_eq!(violation.imposers, vec!["u1.vdd", "u2.vdd"]);
        assert_eq!(
            violation.message,
            "net 'VCC' has 2 driver pins (single-driver check, cuprite/06)"
        );
    }

    #[test]
    fn elec_single_driver_stops_at_first_offending_net() {
        let nets = vec![
            NetEntry {
                name: "OK".to_string(),
                terminals: vec![terminal("u1", "a", true)],
            },
            NetEntry {
                name: "BAD1".to_string(),
                terminals: vec![terminal("u1", "b", true), terminal("u2", "b", true)],
            },
            NetEntry {
                name: "BAD2".to_string(),
                terminals: vec![terminal("u1", "c", true), terminal("u2", "c", true)],
            },
        ];
        let violation = first_violation(&ElecDiscipline, &nets).expect("violation");
        assert_eq!(violation.net, "BAD1");
    }

    #[test]
    fn fluid_discipline_flags_imposer_free_subnet() {
        let nets = vec![NetEntry {
            name: "loop_a".to_string(),
            terminals: vec![terminal("pipe1", "a", false), terminal("pipe2", "b", false)],
        }];
        let violation = first_violation(&FluidDiscipline, &nets).expect("violation");
        assert_eq!(violation.net, "loop_a");
        assert!(violation.message.contains("imposer-free"));
    }

    #[test]
    fn fluid_discipline_passes_with_one_imposer() {
        let nets = vec![NetEntry {
            name: "loop_a".to_string(),
            terminals: vec![terminal("reg1", "out", true), terminal("pipe2", "b", false)],
        }];
        assert_eq!(first_violation(&FluidDiscipline, &nets), None);
    }

    #[test]
    fn load_path_discipline_flags_subnet_with_no_support() {
        let nets = vec![NetEntry {
            name: "MainFrame".to_string(),
            terminals: vec![terminal("G1", "end", false), terminal("C1", "end", false)],
        }];
        let violation = first_violation(&LoadPathDiscipline, &nets).expect("violation");
        assert_eq!(violation.net, "MainFrame");
        assert!(violation.message.contains("no support node"));
    }

    #[test]
    fn load_path_discipline_passes_with_one_support() {
        let nets = vec![NetEntry {
            name: "MainFrame".to_string(),
            terminals: vec![
                terminal("F1", "footing", true),
                terminal("C1", "end", false),
            ],
        }];
        assert_eq!(first_violation(&LoadPathDiscipline, &nets), None);
    }

    #[test]
    fn circulation_discipline_flags_unjoined_space() {
        let nets = vec![NetEntry {
            name: "Suite103".to_string(),
            terminals: vec![],
        }];
        let violation = first_violation(&CirculationDiscipline, &nets).expect("violation");
        assert_eq!(violation.net, "Suite103");
        assert!(violation.message.contains("circulation"));
    }

    #[test]
    fn circulation_discipline_passes_with_one_edge() {
        let nets = vec![NetEntry {
            name: "Lobby".to_string(),
            terminals: vec![terminal("lobby_door", "edge", true)],
        }];
        assert_eq!(first_violation(&CirculationDiscipline, &nets), None);
    }
}
