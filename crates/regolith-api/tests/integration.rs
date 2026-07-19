//! Integration test (TEST003): drives `regolith-api::Session` end to
//! end from outside the crate, against the published surface only --
//! open a session over an explicit in-memory-written file, run
//! `check`, and read back the rendered diagnostics and JSON payload
//! the PyO3 layer crosses (AD-4).

// frob:tests crates/regolith-api/src kind="integration"
#[test]
fn session_check_runs_end_to_end_from_outside_the_crate() {
    use camino::Utf8PathBuf;
    use regolith_api::Session;

    let dir = std::env::temp_dir().join(format!("regolith-api-integration-{}", std::process::id()));
    let dir = Utf8PathBuf::from_path_buf(dir).unwrap();
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("m.hema"), "part Widget:\n  mass: 5 g\n").unwrap();

    let session = Session::open_root(&dir);
    let empty = regolith_lower::RealizedInputs::new();
    let out = session
        .check(&empty)
        .expect("a directory of well-formed sources checks successfully");

    // AD-7: a successful call, regardless of verdict; read both crossings
    // the PyO3 layer relies on -- the rendered text and the JSON payload.
    let _ = out.ok();
    let rendered = out.rendered(false);
    assert!(rendered.is_empty(), "no diagnostics expected: {rendered}");
    let payload: serde_json::Value = serde_json::from_slice(&out.payload_json()).unwrap();
    assert!(!payload["snapshots"].as_array().unwrap().is_empty());

    std::fs::remove_dir_all(&dir).ok();
}
