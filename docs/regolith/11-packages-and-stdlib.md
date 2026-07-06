# Packages, Registries, and the Standard Library

> Regolith spec. One package system for both languages: how library data
> (materials, contact pairs, processes, components, logic families,
> protocols, interface packs, mating packs, harness models, intent verbs)
> is published, versioned, resolved, pinned, and trusted. The tool is
> named **quarry** (`quarry.toml`, `quarry add`) and the public
> registry instance is named **lodestone** (owner-decided, cycle 9,
> D78/D80). The hosting model is settled (section 10; cycle 8, D77).

## 1. Design constraints

1. **Data is load-bearing.** A yield strength or an absolute-max rating
   participates in evidence; a silent data change is a silent change to
   what was proven. Therefore: records are immutable, updates are
   explicit, and every build pins exact record revisions.
2. **Contracts are the unit of compatibility.** Version numbers are
   *computed* from contract diffs, not chosen by authors.
3. **Two-halved packs are normal.** Matings, verbs, and model packs ship
   a modeling-side half and a harness-side half that must co-version.
4. **Provenance or it does not exist.** Every record carries an evidence
   clause; trust is a property of evidence, surfaced at build time.

## 2. Package kinds

| kind | contents | examples |
|---|---|---|
| `quantities` | quantity namespaces, claim vocab extensions | `std.quantities`, `mfg` (time/cost) |
| `materials` | material classes, records, `contact` pairs | `std.materials`, `mmpds` |
| `process` | capability tables + rule packs (DFM/DRC/ERC/derating), per process or fab | `std.sheet_metal`, `jlc.pcb_2l`, `haas.vf2` |
| `components` | elec catalog records: limits as intervals, derating `f(T)/f(V)`, packages, port options, behavioral model refs | `ti.logic`, `st.mcu`, `passives.e96` |
| `interfaces` | interface packs (contract libraries) | `std.mech.mounts` (NEMA, ISO flanges), `std.elec.families`, `std.elec.protocols` |
| `matings` | connection declarations + their harness model nodes (two halves) | `std.mech.bolted`, `std.elec.buses` |
| `models` | harness model packs implementing signatures | `fea.shell`, `spice.ngspice`, `sta.basic`, `cam.mill3ax` |
| `verbs` | intent-verb schemas + lowering skeletons (elec intent layer; mech may grow them) | `std.intents`, `std.debug` |
| `formats` | readers for external-linkage formats (`by extern`, import stages, supplied plans), hash-pinned; each declares transparent (elaborates to design IR) or opaque (measured/evidenced entry) | `fmt.verilog`, `fmt.step`, `fmt.dxf`, `fmt.gcode_fanuc`, `fmt.elf` |
| `parts` | reusable designed artifacts (parts/blocks/boards) with their contracts | a published gearbox; an open-hardware PSU block |

One package may provide several kinds; the manifest declares what it
contributes to which registries.

## 3. The manifest

```
# quarry.toml
[package]
name = "jlc.pcb"
version = "2.3.0"            # checked against computed minimum bump
kinds = ["process"]
license = "CC-BY-4.0"

[provides]
processes = ["pcb_fab.jlc_2l_standard", "pcb_fab.jlc_4l_ctrl_imp"]

[depends]
"std.quantities" = "^1"
"std.elec" = "^0.4"

[halves]                      # co-versioning declaration, if two-halved
modeling = "src/regolith/"
harness  = "src/models/"

[evidence]
# hash-pinned source documents records may cite
"jlc-capability-2026-03.pdf" = "sha256:9c1f..."
```

## 4. Records: immutable, revisioned, provenanced

- A registry record is addressed by `(package, key, revision)`; revisions
  are append-only. Publishing a correction publishes a new revision; it
  never mutates history.
- Every record cites evidence: `by catalog(ref)` (hash-pinned document),
  `by test(ref)` (report), `by analysis` (derivation shipped with the
  pack). Interval-valued where reality scatters.
- The lockfile pins `(package version, record revision hash)` for every
  record a build consumed. `quarry update` moves pins explicitly and the
  diff shows exactly which facts changed; evidence caching keys on record
  hashes, so an updated yield strength invalidates exactly the
  obligations that consumed it.

## 5. Versioning: computed semver

The publish step diffs the new contracts against the previous version:

- widening promises, loosening demands, adding records/roles/models:
  **minor**;
- narrowing promises, tightening demands, changing a record's values,
  removing anything: **major**;
- doc/metadata only: **patch**.

Authors may bump higher than computed, never lower. For two-halved packs,
the halves version together; a harness-half model change that alters an
error model is major for the pack (evidence depends on it). Only
literal-valued promise slots participate in widen/narrow comparison;
slots valued `derived`/`allocated` compare structurally
(presence/type) -- their values are context-dependent and not the
contract's to diff.

## 6. Namespacing, resolution, coherence

- Records are referenced bare (`AISI_4140`) when unambiguous;
  package-qualified (`mmpds.AISI_4140`) otherwise. Ambiguity follows the
  trait-coherence rulebook (`09-build-and-lockfile.md` section 5):
  unique-most-specific-or-error, `use` pins, `override ... by <evidence>`.
- A project's root manifest declares its dependency set; there is no
  ambient global registry state. Two versions of one package in one
  build graph is an error (no shadow worlds of material data).

## 7. Trust tiers

Evidence classes rank: `certified` (authority/vendor-signed:
MMPDS, vendor datasheets with signature) > `tested` (attached test
reports) > `community` (unsigned). Builds declare a floor per claim
group:

```
require Structural:
    trust: >= certified          # data below this tier -> indeterminate, not pass
```

`--release` defaults the floor to `tested` for load-bearing claims;
waivers are per-item, ledgered. This keeps community data usable for
exploration without letting it silently underwrite a release.

## 8. The standard library

`std` is just packages with a reserved prefix:

- `std.quantities` -- namespaces (`mech`, `elec`, `thermo`, `geom`,
  `info`, `mfg`), claim forms, time structure, masks.
- `std.materials`, `std.contact` -- starter metals/polymers, dry/greased
  pairs (conservative, `community`-tier; real work imports certified
  packs).
- `std.mech` -- generic features, primitive profiles, mount/flange
  interface packs, bolted/press/bearing matings + model nodes.
- `std.elec` -- port kinds, logic `family` records, protocol packs
  (I2C/SPI/UART/USB...), bus matings + model nodes, derating rules.
- `std.intents`, `std.debug` -- intent verbs; debug/probe/indicate verbs
  and target overlays.
- `std.models` -- the baseline harness: beam/joint/Lame; STA/worst-case
  DC/IPC-2221; utilization/RTA.

Stdlib evolution follows the same computed-semver discipline as any
package; nothing in the compiler special-cases `std`.

## 9. Projects, files, and teams

How several people (or agents) work one design across many files.
Almost everything here is a consequence of decisions made elsewhere --
import-based reference (regolith `10` sec. 3), declaring-system
obligation ownership (`10` sec. 3), content-addressed evidence
(INV-1), deterministic resolution (INV-10) -- stated in one place
because collaboration is where they compose.

1. **A project is a manifest + a source tree + one lockfile.** The
   root manifest (`quarry.toml`; `[package]` metadata optional until
   published) declares the dependency set; there is no ambient
   registry state (sec. 6). Resolution, evidence caching, and lockfile
   authorship are per project root.
2. **Files are containers, not scopes.** A source file holds top-level
   declarations; file boundaries carry no semantics beyond import
   visibility. Splitting a file in two (and adding the import) changes
   no resolution, no verdict, and no lockfile row -- INV-27,
   file-layout invariance. Organize files by ownership and review
   boundaries, not by language rules.
3. **Two import forms, one mechanism.**
   - `import <pkg> (<names>)` and `import "<path>" (<names>)` bind the
     named top-level declarations into the file's namespace.
   - Bare `import <pkg>` (no name list) loads the package's *registry
     contributions* -- records, feature classes, verbs, matings --
     which resolve through the coherence rulebook (sec. 6), not the
     file namespace. Path imports always name what they take: a bare
     path import would splice a teammate's entire namespace into your
     file, unreviewed.
   - The import graph must be acyclic; a cycle is an E03xx error
     naming it. Contracts break real dependency cycles: both sides
     import the shared interface pack instead of each other.
   - Relative path imports resolve **against the importing file's
     directory** and must stay inside the project root [SETTLED,
     cycle 6, D51 -- forced the first time a project imported across
     directories, `examples/cubesat/eps.cupr` reusing
     `../elec/buck_converter.cupr`]. The lockfile pins the resolved
     content by hash either way (INV-22).
4. **The unit of parallel work is the contract.** Contract-first
   decomposition (regolith `04` sec. 5, `08` sec. 3): the system
   owner writes interfaces + connections + boundary truth and verifies
   at L2 with zero artifacts; each artifact then implements its
   load-annotated contract in its own file(s), checkable locally
   against fixed contracts. Impls are top-level declarations, so an
   alternative impl of a shared block may live in its author's file;
   selection at a use site is the ordinary `use` pin. An artifact edit
   that keeps its promises re-verifies only that artifact (INV-19);
   one that changes promises re-keys exactly the consumers' joint
   obligations (INV-1) -- the blast radius of a teammate's change is
   computed, not feared.
5. **Obligation ownership follows declaration.** The system that
   declares a connection owns its joint obligations; artifacts own
   their own. Content addressing makes the split shareable: a
   team-shared (or CI-hosted) evidence cache is sound by construction
   -- keys decide reuse, not trust in whoever populated the cache --
   and obligations are self-contained and serializable, so discharge
   can run remotely (`07` sec. 2).
6. **Merges reconcile in source; the lockfile is derived state.**
   After a source merge, `build` regenerates the lockfile
   deterministically (INV-10): lockfile merge conflicts are resolved
   by rebuild, and the post-merge lockfile diff is the review artifact
   for what the merge actually changed. Two humans locking one
   decision differently is an ordinary coherence error naming both
   locks (`09` sec. 5), not a merge surprise.
7. **Graduating a subtree to a package.** When a subteam's artifact
   stabilizes, publish it as a `parts`-kind package: consumers change
   one import line (path form -> package form) and gain computed
   semver and trust tiers. Path imports are the intra-repo form;
   packages are the cross-repo and cross-team boundary.

## 10. Registry hosting

[SETTLED, cycle 8, D77 -- the technical half of SOPEN-3; naming is the
owner's.] The hosting model follows from one observation: **because
every consumed record is content-addressed and lockfile-pinned
(INV-22), hosting can affect availability, never meaning.** A registry
is a distribution channel for immutable facts, and a channel cannot
lie about a fact whose hash the consumer already demands. Everything
below is a consequence.

1. **A registry is an index plus an archive store.** The index maps
   `(package, version)` to a manifest digest and an archive hash; it
   is append-only and fetched sparsely (per-package paths, HTTP range
   requests -- the cargo sparse-index shape, which is the proven prior
   art). The archive store is dumb content-addressed storage; anything
   that can serve bytes by hash can host it.
2. **Sources are declared in the manifest; there is no ambient
   default inside the languages.** The root manifest's `[sources]`
   table names each registry (the public one, a vendor's, a company's
   private mirror) and maps dependency namespaces onto them. The
   toolchain ships configured with the public registry so the common
   case is zero ceremony -- but the resolution input is always the
   manifest, per section 6's no-ambient-state rule.
3. **Mirrors are trivially safe.** A mirror serves the same
   content-addressed bytes; the lockfile pin decides acceptance. A
   poisoned mirror can only cause a loud hash mismatch (INV-22's
   drift error), never a silent substitution. Corporate
   air-gapped mirrors and `quarry vendor` (copy every pinned archive
   into the repo for offline builds) need no trust machinery of
   their own.
4. **Signing carries trust tiers; hosting does not.** A record's
   trust tier (section 7) is established by *signatures on the
   record* (authority/vendor keys for `certified`, attached reports
   for `tested`, none for `community`), verified locally against the
   consumer's key set. Where a package is fetched from is
   deliberately absent from the tier computation -- a certified MMPDS
   record is certified from any mirror, and no registry operator can
   mint certification by hosting.
5. **Yank hides, never deletes.** A yanked version disappears from
   *new* resolution but remains fetchable by exact pin forever --
   record immutability (section 4) extends to distribution, so a
   lockfile written yesterday builds today. Security-critical
   retractions are handled the same way as everywhere else in the
   system: loudly (an advisory flag on the index entry surfaces as a
   build warning naming the advisory), never silently.
6. **Publishing is where computed semver runs** (section 5): the
   registry re-runs the contract diff on submission and refuses an
   understated bump -- the one check that must live server-side,
   because it protects consumers from authors.

What deliberately does not exist: registry-side build execution
(obligations are discharged by consumers or their CI; the registry
stores facts, not verdicts), per-registry namespace magic (names
resolve by the coherence rulebook regardless of source), and any
form of mutable "latest" channel (resolution always lands on a
pinned version; `quarry update` is the only mover).
