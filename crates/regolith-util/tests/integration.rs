//! Integration test (TEST003): exercises `regolith-util`'s public API
//! the same way a downstream crate does -- from outside the crate,
//! against the published surface only.

// frob:tests crates/regolith-util/src kind="integration"
#[test]
fn content_address_round_trips_through_the_public_api() {
    #[derive(serde::Serialize)]
    struct Payload {
        a: u32,
        b: String,
    }

    let value = Payload {
        a: 7,
        b: "regolith".to_string(),
    };

    let addr = regolith_util::canon::content_address("regolith.util.integration", &value)
        .expect("finite, serializable value must encode");
    assert_eq!(addr.len(), 64, "content address is a blake3 hex digest");

    let digest = regolith_util::hash_hex(b"regolith-util integration test");
    assert_eq!(digest.len(), 64);
}
