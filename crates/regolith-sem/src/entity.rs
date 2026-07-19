//! The entity database: the artifact's committed state as a set of
//! entities with owners, regions, and symmetry orbits. Both languages
//! bind to it (faces/edges/nets/instances/ports/regions).
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! sec. 1, 3, 5 and `docs/spec/regolith/06`. Entity IDs are INTERNAL ONLY
//! -- never serialized into source-facing output (all source references
//! are queries, WO-08). The DB is a sequence of immutable snapshots: a
//! commit produces a NEW snapshot, never mutates one (WO-07 acceptance:
//! mutation attempts are programmer errors).

use regolith_util::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};

use crate::symmetry::OrbitId;

/// An internal entity identifier. Deliberately opaque and NEVER emitted
/// into source-facing output (INV: no positional/id leakage). Stable
/// only within one build.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub struct EntityId(pub u32);

/// The broad kind of an entity (domain-tagged). Measures carry the
/// specifics; this is the coarse classification queries dispatch on.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub enum EntityKind {
    /// Mech topology: a face.
    Face,
    /// Mech topology: an edge.
    Edge,
    /// Mech topology: a vertex.
    Vertex,
    /// Mech domain: a hole (rule-pack `forall` domain, WO-28). Typed
    /// fields ride `Entity::measures` under the well-known keys
    /// `position`, `diameter`, `edge_distance` (WO-29 Q1) rather than
    /// dedicated struct fields, so new geometric attributes do not force
    /// a schema-version bump; the WO-08 predicate registry still owns
    /// their typing.
    Hole,
    /// Mech domain: a bend (rule-pack `forall` domain, WO-28). Typed
    /// fields ride `Entity::measures` under the well-known keys
    /// `radius`, `angle`, `line` (WO-29 Q1) plus `relief_cuts` and
    /// `at_free_edge` (WO-28: the sheet-metal reference pack's
    /// bend-relief vocabulary -- declared bend facts the extraction
    /// layer provides post-realization when not spelled in source).
    Bend,
    /// Mech domain: a declared rib PATTERN over a target region
    /// (charter 34 phase 1, D200/WO-77 -- one entity per `Ribs(...)`
    /// op, not one per rib: the count is a parameter, possibly a
    /// bounded optimizer slot). Well-known measure keys: `count`,
    /// `pitch`, `thickness`, `height`.
    Rib,
    /// Mech domain: a declared pocket-grid removal pattern (D200/
    /// WO-77). Well-known measure keys: `nx`, `ny`, `wall`, `floor`,
    /// `depth`.
    PocketGrid,
    /// Mech domain: a declared shell/hollow-out op (D200/WO-77).
    /// Well-known measure key: `thickness` (spelled `t` in source).
    Shell,
    /// Mech domain: a declared lattice-infill removal (D200/WO-77).
    /// Well-known measure keys: `cell` (a name from the v1 discrete
    /// set), `density` (a fraction in `[0, 1]`).
    Lattice,
    /// Elec: a net.
    Net,
    /// Elec: a component instance.
    Instance,
    /// Elec: a port of an instance.
    Port,
    /// An owned spatial/resource region (courtyard, keepout, zone).
    Region,
    /// An escape hatch for domain kinds added by packs (named).
    Other(String),
}

impl EntityKind {
    /// Map a source-level kind word (singular or plural: `holes`,
    /// `net`, ...) to its entity kind. This is the ONE home for the
    /// word-to-kind mapping: the query engine's base selector and the
    /// lowering that commits entities must both go through it, or a
    /// committed entity and the query that names it silently disagree
    /// (the exact desync WO-29's `Hole` promotion exposed). Unknown
    /// words map to [`EntityKind::Other`] so pack-defined kinds still
    /// validate.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn from_kind_word(word: &str) -> Self {
        match word {
            "faces" | "face" => EntityKind::Face,
            "edges" | "edge" => EntityKind::Edge,
            "vertices" | "vertex" => EntityKind::Vertex,
            "holes" | "hole" => EntityKind::Hole,
            "bends" | "bend" => EntityKind::Bend,
            "ribs" | "rib" => EntityKind::Rib,
            "pocket_grids" | "pocket_grid" => EntityKind::PocketGrid,
            "shells" | "shell" => EntityKind::Shell,
            "lattices" | "lattice" => EntityKind::Lattice,
            "nets" | "net" => EntityKind::Net,
            "instances" | "instance" => EntityKind::Instance,
            "ports" | "port" => EntityKind::Port,
            "regions" | "region" => EntityKind::Region,
            other => EntityKind::Other(other.to_string()),
        }
    }

    /// The well-known `Entity::measures` keys this kind's doc comment
    /// promises (WO-29 Q1), or `None` when this kind has no documented
    /// measure vocabulary yet. This is the ONE home for that table (the
    /// `Hole`/`Bend` doc comments above are the prose form of the same
    /// fact): a rule-pack `forall`'s field references (WO-28 E0603, `crate
    /// ::rules`'s consumer) and any future reader of the measure
    /// vocabulary must both cite this function rather than re-deriving
    /// the key list, or the two lists drift (NO DUPLICATION). Kinds
    /// without an entry here are not (yet) checked for unprovided
    /// fields -- absence is "not modeled", not "no fields".
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn known_measure_keys(&self) -> Option<&'static [&'static str]> {
        match self {
            EntityKind::Hole => Some(&["position", "diameter", "edge_distance"]),
            EntityKind::Bend => Some(&["radius", "angle", "line", "relief_cuts", "at_free_edge"]),
            // WO-77 (D200): the removal-family measure vocabularies.
            EntityKind::Rib => Some(&["count", "pitch", "thickness", "height"]),
            EntityKind::PocketGrid => Some(&["nx", "ny", "wall", "floor", "depth"]),
            EntityKind::Shell => Some(&["thickness"]),
            EntityKind::Lattice => Some(&["cell", "density"]),
            // WO-87 (D198): declared-topology net vocabulary. The
            // static counts the board entity-population pass derives
            // (`undecoupled_power_pin_count`, ...) plus every field the
            // landed stdlib net-domain packs (std.elec.patterns, the
            // espresso jlc DRC pack) reference, so E0603 stays a real
            // unknown-field check while realized-tier fields keep
            // deferring honestly per D-E.
            EntityKind::Net => Some(&[
                "members",
                "member_count",
                "driver_count",
                "series_term_count",
                "tvs_count",
                "test_point_count",
                "undecoupled_power_pin_count",
                "bare_switch_input_count",
                "discrete_level_shift_count",
                "exposed_port_no_clamp_count",
                "unprotected_supply_input_count",
                "unregulated_divider_rail_count",
                "drive_current",
                "load_current",
                "driver",
                "loads",
                "kind",
            ]),
            // WO-87 (D198): the board-correctness domain vocabulary
            // (charter 36 families), committed as `Other(<word>)` by
            // the board entity-population pass (`regolith-lower::
            // board_entities`). The words match `from_kind_word`'s
            // fallback, so a `forall p in power_pins` enumerates
            // exactly what the pass commits.
            EntityKind::Other(word) => board_domain_measure_keys(word),
            _ => None,
        }
    }

    /// Map a `then:` claim-scope feature CONSTRUCTOR head (`Bore`,
    /// `Bend`, `PatternOf`'s inner head, ...) to the domain entity kind
    /// it materializes, or `None` when the constructor is not one of the
    /// hole/bend feature verbs this WO structures (WO-29 deliverable 2,
    /// Q4(a) corrected). This is the ONE home for the constructor-to-kind
    /// mapping, the mate of [`EntityKind::from_kind_word`]: the lowering
    /// that materializes feature entities and any future consumer that
    /// names a constructor must both go through it, or an emitted entity
    /// and the rule that quantifies over it silently disagree. Unknown
    /// constructors return `None` (they stay opaque / non-domain) rather
    /// than mapping to `Other`, because a `forall h in holes` domain must
    /// enumerate ONLY the kinds it names -- an unrecognized constructor
    /// is not a hole with an unknown name, it is simply not a hole.
    ///
    /// The hole family is the material-removal round-feature verbs the
    /// mech corpus uses (`docs/hematite`, `std.mech.*` vocab); the bend
    /// family is sheet forming. New feature verbs join the appropriate
    /// arm here (no schema change: `EntityKind` is unchanged, only the
    /// word-to-kind lookup grows).
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn from_constructor_word(head: &str) -> Option<Self> {
        match head {
            // Round material-removal features -> Hole.
            "Bore" | "CBore" | "Drill" | "Ream" | "Pierce" | "CSink" | "Countersink"
            | "ThreadedHole" | "TappedHole" | "Tap" | "PilotHole" => Some(EntityKind::Hole),
            // Sheet forming -> Bend.
            "Bend" => Some(EntityKind::Bend),
            // Declared material-removal families (charter 34 phase 1,
            // D200/WO-77): one entity per op (the pattern, not its
            // instances -- `count`/`nx` are parameters, possibly
            // bounded optimizer slots, never an entity multiplier).
            "Ribs" => Some(EntityKind::Rib),
            "PocketGrid" => Some(EntityKind::PocketGrid),
            "Shell" => Some(EntityKind::Shell),
            "Lattice" => Some(EntityKind::Lattice),
            _ => None,
        }
    }
}

/// The measure vocabulary of one board-correctness `Other(<word>)`
/// domain (WO-87/D198, charter 36 families), or `None` for a
/// pack-defined word this table does not model. Split out of
/// [`EntityKind::known_measure_keys`] only for readability -- that
/// method is still the ONE reader-facing home.
///
/// Realized-tier fields (`shunt_cap_distance_mm`,
/// `probe_clearance_mm`) are listed as vocabulary even though the
/// declared-topology pass never provides them: E0603 is an
/// unknown-FIELD check, and an unprovided-but-modeled field defers
/// honestly at eval time (the `Hole::edge_distance` precedent).
/// `supervised_rails` and `clock_nets` are vocabulary-only today: the
/// declared-topology tier has no honest source for reset-supervision
/// requirements or clock-driver attribution (both need record/pin-
/// direction facts that are WO-24/WO-35 realizer territory), so those
/// domains stay empty (vacuous pass), never fabricated.
#[must_use]
fn board_domain_measure_keys(word: &str) -> Option<&'static [&'static str]> {
    match word {
        "power_pins" => Some(&[
            "shunt_cap_count",
            "shunt_cap_value",
            "shunt_cap_distance_mm",
        ]),
        "rails" => Some(&["bulk_cap_count"]),
        "config_straps" => Some(&["pull_state_defined", "pin"]),
        "control_boards" => Some(&["debug_header_count"]),
        "supervised_rails" => Some(&["reset_supervisor_present", "reset_supervisor_required"]),
        "crystals" => Some(&["record", "cl", "c_load_calculated"]),
        "clock_nets" => Some(&["driver_count", "series_term_count"]),
        "exposed_connectors" => Some(&[
            "record",
            "class",
            "esd_protection_count",
            "inrush_protection_count",
        ]),
        "exposed_nets" => Some(&["tvs_count"]),
        "critical_nets" => Some(&["test_point_count"]),
        "test_points" => Some(&["record", "pad_diameter_mm", "probe_clearance_mm"]),
        // WO-112 Class 5: the REALIZED-tier routed-copper domain --
        // populated from a `layout.realized` input's `RoutedSegment`s
        // (`regolith-lower::board_entities::realized_trace_entities`),
        // never from declared topology. An un-realized build defers the
        // whole domain by name (see `rule_engine`'s realized-tier
        // gate), so a `forall t in traces` DRC rule is honest at every
        // tier: deferred before layout, evaluated after.
        "traces" => Some(&["net", "layer", "width", "length"]),
        _ => None,
    }
}

/// A named, typed measure on an entity (`area`, `direction`, `width`).
/// String-keyed so packs extend it; values are opaque strings here and
/// are typed by the predicate registry (WO-08).
// frob:doc docs/modules/regolith-sem.md#entity-db
pub type Measures = IndexMap<String, String>;

/// One entity in the database.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub struct Entity {
    /// Internal id (never source-facing).
    pub id: EntityId,
    /// The construct that created this entity (for diagnostics).
    pub origin: String,
    /// The construct that most recently modified it (its owner).
    pub owner: String,
    /// Coarse kind.
    pub kind: EntityKind,
    /// Typed measures (kind-specific).
    pub measures: Measures,
    /// User tags.
    pub tags: IndexSet<String>,
    /// Symmetry orbit this entity belongs to, if any.
    pub orbit: Option<OrbitId>,
}

/// The exclusion/arbitration policy of a [`EntityKind::Region`] entity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub enum RegionPolicy {
    /// Sole occupancy: any placement/route into it is a conflict unless
    /// an explicit join is declared.
    Exclusion,
    /// Shared under a declared arbitration construct.
    Arbitration,
}

/// The predicted effect of one construct/statement, declared BEFORE any
/// realizer runs (the ownership check works on these, WO-09). A
/// construct with data-dependent effects flags it for post-realization
/// verification.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub struct PredictedDelta {
    /// Entities this construct creates.
    pub creates: Vec<EntityId>,
    /// Entities it modifies (transfers ownership).
    pub modifies: Vec<EntityId>,
    /// Entities it consumes (removes).
    pub consumes: Vec<EntityId>,
    /// Regions it touches (placement/route extent).
    pub regions_touched: Vec<EntityId>,
    /// The symmetry contribution this construct declares (Cn, orbit,
    /// or break); `None` means symmetry-neutral.
    pub symmetry: Option<OrbitId>,
    /// True when the true effect depends on realized data and must be
    /// re-checked after realization (regolith/05 sec. 5).
    pub data_dependent: bool,
}

/// An immutable snapshot of the entity database. A commit produces a
/// new snapshot (structural sharing is an impl detail); snapshots never
/// mutate in place.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#entity-db
pub struct EntityDb {
    entities: IndexMap<EntityId, Entity>,
}

impl EntityDb {
    /// An empty database (the pre-construction snapshot).
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn empty() -> EntityDb {
        EntityDb {
            entities: IndexMap::new(),
        }
    }

    /// Look up an entity by id.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn get(&self, id: EntityId) -> Option<&Entity> {
        self.entities.get(&id)
    }

    /// Number of entities in this snapshot.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn len(&self) -> usize {
        self.entities.len()
    }

    /// True when the snapshot is empty.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn is_empty(&self) -> bool {
        self.entities.is_empty()
    }

    /// Commit a predicted delta against domain-supplied new entities,
    /// producing a NEW snapshot (owner transfer, consumption, orbit
    /// intersection/splitting). Never mutates `self`.
    ///
    /// `new_entities` carries the post-delta state of every entity the
    /// delta creates or modifies (owner/orbit already updated by the
    /// caller); `consumes` names entities removed from the snapshot.
    /// Consumption is applied after the upserts so a construct may
    /// consume an entity in the same commit it (re-)creates under a
    /// different id.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn commit(&self, delta: &PredictedDelta, new_entities: &[Entity]) -> EntityDb {
        let mut entities = self.entities.clone();
        for entity in new_entities {
            entities.insert(entity.id, entity.clone());
        }
        for id in &delta.consumes {
            entities.shift_remove(id);
        }
        EntityDb { entities }
    }

    /// The content address of this snapshot, stable under key order
    /// (AD-6). Used for incremental caching and lockfile provenance.
    ///
    /// Entities are canonically encoded in ascending id order (never in
    /// `IndexMap` iteration/insertion order) so the hash is independent
    /// of commit history, then hashed via the one shared canonical-CBOR
    /// encoder at the bottom of the layering (`regolith_util::canon`,
    /// AD-18) -- nothing hashes JSON anywhere.
    ///
    /// # Panics
    /// Never in practice: the lookup key always comes from this map's
    /// own key set, and `Entity` has no non-finite float fields to
    /// reject at serialization (a non-finite field would be an
    /// upstream compiler bug).
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn snapshot_hash(&self) -> String {
        let mut ids: Vec<&EntityId> = self.entities.keys().collect();
        ids.sort();

        let ordered: Vec<&Entity> = ids
            .into_iter()
            .map(|id| {
                self.entities
                    .get(id)
                    .expect("id came from this map's own keys")
            })
            .collect();

        regolith_util::canon::content_address("regolith.sem.snapshot", &ordered)
            .expect("Entity has no non-finite float fields; a NaN reaching here is an upstream compiler bug")
    }

    /// Iterate entities in canonical (ascending id) order. Used by the
    /// query engine (WO-08) to enumerate a base selection; never expose
    /// `IndexMap`'s own iteration order here (AD-6).
    // frob:doc docs/modules/regolith-sem.md#entity-db
    pub fn iter(&self) -> impl Iterator<Item = &Entity> {
        let mut entities: Vec<&Entity> = self.entities.values().collect();
        entities.sort_by_key(|e| e.id);
        entities.into_iter()
    }
}

#[cfg(test)]
mod tests {
    use super::{Entity, EntityDb, EntityId, EntityKind};
    use regolith_util::{IndexMap, IndexSet};

    fn face(id: u32) -> Entity {
        Entity {
            id: EntityId(id),
            origin: "shell".to_string(),
            owner: "shell".to_string(),
            kind: EntityKind::Face,
            measures: IndexMap::new(),
            tags: IndexSet::new(),
            orbit: None,
        }
    }

    #[test]
    fn empty_db_is_empty() {
        assert!(EntityDb::empty().is_empty());
    }

    // frob:tests crates/regolith-sem/src/entity.rs::EntityDb.snapshot_hash kind="unit"
    #[test]
    fn snapshot_hash_is_stable_across_builds_and_changes_with_entities() {
        let db1 = EntityDb::empty().commit(
            &super::PredictedDelta {
                creates: vec![EntityId(1)],
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            },
            &[face(1)],
        );
        let db2 = EntityDb::empty().commit(
            &super::PredictedDelta {
                creates: vec![EntityId(1)],
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            },
            &[face(1)],
        );
        assert_eq!(
            db1.snapshot_hash(),
            db2.snapshot_hash(),
            "same entities -> same hash across independent builds"
        );

        let db3 = db1.commit(
            &super::PredictedDelta {
                creates: vec![EntityId(2)],
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            },
            &[face(2)],
        );
        assert_ne!(
            db1.snapshot_hash(),
            db3.snapshot_hash(),
            "adding an entity must change the snapshot hash"
        );
    }

    #[test]
    fn entity_round_trips_json() {
        let e = face(1);
        let json = serde_json::to_string(&e).unwrap();
        let back: Entity = serde_json::from_str(&json).unwrap();
        assert_eq!(back, e);
    }

    // frob:tests crates/regolith-sem/src/entity.rs::EntityDb.len kind="unit"
    // frob:tests crates/regolith-sem/src/entity.rs::EntityDb.iter kind="unit"
    #[test]
    fn len_and_iter_reflect_committed_entities_in_ascending_id_order() {
        let db = EntityDb::empty();
        assert_eq!(db.len(), 0);

        let db = db.commit(
            &super::PredictedDelta {
                creates: vec![EntityId(2), EntityId(1)],
                modifies: vec![],
                consumes: vec![],
                regions_touched: vec![],
                symmetry: None,
                data_dependent: false,
            },
            &[face(2), face(1)],
        );
        assert_eq!(db.len(), 2);
        let ids: Vec<u32> = db.iter().map(|e| e.id.0).collect();
        assert_eq!(ids, vec![1, 2], "iter is canonical ascending-id order");
    }

    // frob:tests crates/regolith-sem/src/entity.rs::EntityKind.from_kind_word kind="unit"
    #[test]
    fn from_kind_word_maps_singular_and_plural_and_falls_back_to_other() {
        assert_eq!(EntityKind::from_kind_word("hole"), EntityKind::Hole);
        assert_eq!(EntityKind::from_kind_word("holes"), EntityKind::Hole);
        assert_eq!(EntityKind::from_kind_word("nets"), EntityKind::Net);
        assert_eq!(
            EntityKind::from_kind_word("power_pins"),
            EntityKind::Other("power_pins".to_string())
        );
    }

    // frob:tests crates/regolith-sem/src/entity.rs::EntityKind.known_measure_keys kind="unit"
    #[test]
    fn known_measure_keys_covers_documented_kinds_and_none_for_undocumented() {
        assert_eq!(
            EntityKind::Hole.known_measure_keys(),
            Some(&["position", "diameter", "edge_distance"][..])
        );
        assert_eq!(EntityKind::Face.known_measure_keys(), None);
    }

    // frob:tests crates/regolith-sem/src/entity.rs::EntityKind.from_constructor_word kind="unit"
    #[test]
    fn from_constructor_word_maps_feature_verbs_and_rejects_unknown() {
        assert_eq!(
            EntityKind::from_constructor_word("Bore"),
            Some(EntityKind::Hole)
        );
        assert_eq!(
            EntityKind::from_constructor_word("Bend"),
            Some(EntityKind::Bend)
        );
        assert_eq!(EntityKind::from_constructor_word("Extrude"), None);
    }
}
