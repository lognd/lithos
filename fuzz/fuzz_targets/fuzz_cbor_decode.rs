//! Fuzz the CBOR decode path (AD-3 / AD-18): decoding arbitrary bytes
//! with `ciborium` -- the same decoder `regolith_util::canon` uses to
//! re-parse its own canonical output -- must never panic. Malformed
//! input is a clean `Err`, never a crash (the decoder sits behind the
//! FFI boundary where panics become CoreBug).
#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Decode into the dynamic Value model; any structurally valid CBOR
    // is accepted, anything else is a clean Err. Neither may panic.
    let decoded: Result<ciborium::value::Value, _> = ciborium::from_reader(data);

    if let Ok(value) = decoded {
        // Re-encoding a decoded value must also stay panic-free (the
        // canonicalizer walks decoded Values on the hash-input path).
        let mut buf = Vec::new();
        let _ = ciborium::into_writer(&value, &mut buf);
    }
});
