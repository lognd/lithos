---
id: T-0002
title: Annotate crates/regolith-oblig doc edges for COV001
state: queued
kind: docs
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- crates/regolith-oblig/src/**
evidence: []
attachments: []
---
frob check --type python --only gates reports 146 COV001 warnings under crates/regolith-oblig (e.g. flownet.rs::RecordRef, flownet.rs::ScalarInterval) -- public symbols with no frob:doc edge. This is the obligation-graph core crate (AD-1/AD-2 territory), the highest-value place to start closing COV001 given regolith-lower/regolith-syntax/regolith-oblig account for most of the 6900+ COV001 hits repo-wide.

Add frob:doc / frob:describes anchors (or doc comments the doclink/coverage gate already recognizes) for the public API surface of crates/regolith-oblig/src/, prioritizing flownet.rs and any other file with more than 10 undocumented public symbols. Re-run frob check --only gates and confirm the COV001 count for this crate drops to 0.

Origin: frob enforcement adoption sweep (frob check --only gates dry run).