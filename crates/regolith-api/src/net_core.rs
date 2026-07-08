//! JSON marshalling over `regolith_sem::net_core` for the elec
//! discipline (AD-23 D4). This is the ONE crossing point the PyO3 layer
//! calls through -- no net-ledger logic lives here, only wire<->core
//! translation, matching the `format`/`debug_dump` shape already in
//! this crate.
//!
//! The wire shape mirrors the Python `NetlistModel`/`Net`/`Pin` fields
//! (`is_driver`) exactly, so `regolith.compiler` can serialize a
//! `NetlistModel` with a plain `model_dump_json()` and hand it straight
//! across.

use serde::{Deserialize, Serialize};

use regolith_sem::net_core::{first_violation, ElecDiscipline, NetEntry, Terminal};

/// One wire-format pin: matches `regolith.realizer.elec.netlist.Pin`.
#[derive(Debug, Deserialize)]
struct WirePin {
    component: String,
    pin: String,
    #[serde(default)]
    is_driver: bool,
}

/// One wire-format net: matches `regolith.realizer.elec.netlist.Net`.
#[derive(Debug, Deserialize)]
struct WireNet {
    name: String,
    pins: Vec<WirePin>,
}

/// The elec single-driver check's result: `None` when every net is
/// clean, `Some` naming the first offending net (fail-fast, matching
/// the historical Python behavior byte-for-byte).
#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct ElecViolation {
    /// The offending net's name.
    pub net: String,
    /// The driver terminals found on that net, `"component.pin"`.
    pub drivers: Vec<String>,
    /// The rendered message (byte-identical to the retired Python text).
    pub message: String,
}

/// Parse `nets_json` (a JSON array of wire-format nets) and run the elec
/// discipline's single-driver check (cuprite/06), returning the first
/// violation found, in net order.
///
/// # Errors
/// Returns a `serde_json` error message when `nets_json` does not parse
/// as the expected wire shape -- an infrastructure/programmer-facing
/// failure, not a design error (those are `Ok(Some(..))`).
pub fn check_elec_single_driver(nets_json: &str) -> Result<Option<ElecViolation>, String> {
    let wire_nets: Vec<WireNet> =
        serde_json::from_str(nets_json).map_err(|e| format!("invalid net JSON: {e}"))?;
    let entries: Vec<NetEntry> = wire_nets
        .into_iter()
        .map(|n| NetEntry {
            name: n.name,
            terminals: n
                .pins
                .into_iter()
                .map(|p| Terminal {
                    component: p.component,
                    terminal: p.pin,
                    imposes: p.is_driver,
                })
                .collect(),
        })
        .collect();
    Ok(first_violation(&ElecDiscipline, &entries).map(|v| ElecViolation {
        net: v.net,
        drivers: v.imposers,
        message: v.message,
    }))
}

#[cfg(test)]
mod tests {
    use super::check_elec_single_driver;

    #[test]
    fn clean_nets_pass() {
        let json = r#"[{"name":"VCC","pins":[{"component":"u1","pin":"vdd","is_driver":true}]}]"#;
        assert_eq!(check_elec_single_driver(json).unwrap(), None);
    }

    #[test]
    fn two_drivers_flagged() {
        let json = r#"[{"name":"VCC","pins":[
            {"component":"u1","pin":"vdd","is_driver":true},
            {"component":"u2","pin":"vdd","is_driver":true}
        ]}]"#;
        let violation = check_elec_single_driver(json).unwrap().expect("violation");
        assert_eq!(violation.net, "VCC");
        assert_eq!(violation.drivers, vec!["u1.vdd", "u2.vdd"]);
        assert_eq!(
            violation.message,
            "net 'VCC' has 2 driver pins (single-driver check, cuprite/06)"
        );
    }

    #[test]
    fn bad_json_reports_error() {
        assert!(check_elec_single_driver("not json").is_err());
    }
}
