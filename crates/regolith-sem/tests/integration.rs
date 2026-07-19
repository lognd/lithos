//! Integration test (TEST003): drives the semantic layer end to end
//! from outside the crate -- parse a small `.hema` profile source with
//! `regolith-syntax`, extract its typed walk, and run the sketch DOF
//! ledger (`profile::compute_ledger`/`check_ledger_closes`) exactly the
//! way a real caller (the checker pipeline above this crate) would,
//! rather than poking at one internal function in isolation.

// frob:tests crates/regolith-sem/src kind="integration"
#[test]
fn profile_walk_ledger_closes_end_to_end_from_outside_the_crate() {
    use camino::Utf8PathBuf;
    use regolith_sem::profile::{check_ledger_closes, compute_ledger, count_declared_free};
    use regolith_syntax::syntax_kind::SyntaxKind;
    use regolith_syntax::walk::parse_walk;

    let src = "profile p:\n\
               \x20\x20\x20\x20walk:\n\
               \x20\x20\x20\x20\x20\x20\x20\x20from origin\n\
               \x20\x20\x20\x20\x20\x20\x20\x20line right\n\
               \x20\x20\x20\x20\x20\x20\x20\x20line up\n\
               \x20\x20\x20\x20\x20\x20\x20\x20close\n\
               \x20\x20\x20\x20constraints:\n\
               \x20\x20\x20\x20\x20\x20\x20\x20a.length = 8mm\n\
               \x20\x20\x20\x20\x20\x20\x20\x20b.length = 5mm\n";
    let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
    let decl = parse
        .syntax()
        .descendants()
        .find(|n| n.kind() == SyntaxKind::Decl)
        .expect("a Decl in the parsed source");
    let walk = parse_walk(&decl).expect("a walk from the typed CST");

    let free = count_declared_free(&walk);
    let ledger = compute_ledger(&walk, free);
    assert!(
        ledger.is_closed(),
        "two lines pinned by two constraints plus close should close"
    );
    assert!(check_ledger_closes(&ledger).is_empty());
}
