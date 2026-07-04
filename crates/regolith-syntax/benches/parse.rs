//! Criterion benchmarks for the front-end over the Kestrel corpus
//! (AD-11: Kestrel = the standard workload; `examples/cubesat/`). Each
//! source file is timed through lex, parse, and format so regressions in
//! any front-end pass show up on `make bench`.
//!
//! The criterion harness macros generate undocumented public items; the
//! workspace `missing_docs` lint does not apply to a bench harness.
#![allow(missing_docs)]

use std::path::PathBuf;

use camino::Utf8PathBuf;
use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

/// The Kestrel corpus: every source file under `examples/cubesat/`.
fn kestrel_sources() -> Vec<(String, String)> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("crates/regolith-syntax is two levels under the workspace root")
        .join("examples/cubesat");

    let mut out = Vec::new();
    let mut entries: Vec<_> = std::fs::read_dir(&root)
        .expect("examples/cubesat must exist")
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| {
            p.extension()
                .and_then(|e| e.to_str())
                .is_some_and(|e| e == "hem" || e == "cupr")
        })
        .collect();
    entries.sort();

    for path in entries {
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .expect("ascii file name")
            .to_string();
        let text = std::fs::read_to_string(&path).expect("readable corpus file");
        out.push((name, text));
    }
    out
}

fn bench_frontend(c: &mut Criterion) {
    let sources = kestrel_sources();
    let mut group = c.benchmark_group("kestrel");

    for (name, source) in &sources {
        let file = Utf8PathBuf::from(name.clone());
        group.throughput(Throughput::Bytes(source.len() as u64));

        group.bench_with_input(BenchmarkId::new("lex", name), source, |b, src| {
            b.iter(|| regolith_syntax::token::lex(std::hint::black_box(src)));
        });
        group.bench_with_input(BenchmarkId::new("parse", name), source, |b, src| {
            b.iter(|| regolith_syntax::parser::parse(std::hint::black_box(src), &file));
        });
        group.bench_with_input(BenchmarkId::new("format", name), source, |b, src| {
            b.iter(|| regolith_syntax::formatter::format(std::hint::black_box(src), &file));
        });
    }
    group.finish();
}

criterion_group!(benches, bench_frontend);
criterion_main!(benches);
