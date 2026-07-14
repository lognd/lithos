//! `make codes` driver: prints the WO-131/D247 diagnostic code +
//! explain-content registry as JSON to stdout.
//!
//! Thin wrapper over `regolith_diag::{code, explain}` -- the ONE
//! registry (`crates/regolith-diag/src/code.rs` + `explain.rs`).
//! Mirrors `export_schema.rs`'s `make schema` precedent exactly: Rust
//! is the source of truth, this binary is the only place that reads
//! it for codegen, and the Python side consumes the GENERATED output,
//! never a second registry.

use serde::Serialize;

/// One code's exported row: the numeric code plus every explain field,
/// flattened for easy pydantic/dict consumption on the Python side.
#[derive(Serialize)]
struct CodeRow {
    code: String,
    symbol: String,
    family: String,
    meaning: String,
    why: String,
    fix: String,
    example: Option<String>,
    authored: bool,
}

fn main() {
    let rows: Vec<CodeRow> = regolith_diag::explain::ALL
        .iter()
        .map(|e| CodeRow {
            code: e.code.to_string(),
            symbol: e.symbol.to_string(),
            family: format!("{:?}", e.code.family),
            meaning: e.meaning.to_string(),
            why: e.why.to_string(),
            fix: e.fix.to_string(),
            example: e.example.map(str::to_string),
            authored: e.authored,
        })
        .collect();
    let json = serde_json::to_string_pretty(&rows).expect("code registry always serializes");
    println!("{json}");
}
