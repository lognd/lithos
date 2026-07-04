//! `make schema` driver: prints the AD-5 JSON Schema export to stdout.
//!
//! Thin wrapper over `rockhead_oblig::export_schemas` -- the schema
//! codegen pipeline (schemars -> datamodel-code-generator -> pydantic)
//! pipes this into the Python model generator (AD-5).

fn main() {
    print!("{}", rockhead_oblig::export_schemas());
}
