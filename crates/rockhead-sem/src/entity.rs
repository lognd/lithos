//! The entity database: the artifact's committed state as a set of
//! entities with owners, regions, and symmetry orbits. Both languages
//! bind to it (faces/edges/nets/instances/ports/regions).
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`
//! sec. 1, 3, 5 and `docs/substrate/06`. Entity IDs are INTERNAL ONLY
//! -- never serialized into source-facing output (all source references
//! are queries, WO-08). The DB is a sequence of immutable snapshots: a
//! commit produces a NEW snapshot, never mutates one (WO-07 acceptance:
//! mutation attempts are programmer errors).

use rockhead_util::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};

use crate::symmetry::OrbitId;

/// An internal entity identifier. Deliberately opaque and NEVER emitted
/// into source-facing output (INV: no positional/id leakage). Stable
/// only within one build.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct EntityId(pub u32);

/// The broad kind of an entity (domain-tagged). Measures carry the
/// specifics; this is the coarse classification queries dispatch on.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityKind {
    /// Mech topology: a face.
    Face,
    /// Mech topology: an edge.
    Edge,
    /// Mech topology: a vertex.
    Vertex,
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

/// A named, typed measure on an entity (`area`, `direction`, `width`).
/// String-keyed so packs extend it; values are opaque strings here and
/// are typed by the predicate registry (WO-08).
pub type Measures = IndexMap<String, String>;

/// One entity in the database.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
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
    /// re-checked after realization (substrate/05 sec. 5).
    pub data_dependent: bool,
}

/// An immutable snapshot of the entity database. A commit produces a
/// new snapshot (structural sharing is an impl detail); snapshots never
/// mutate in place.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntityDb {
    entities: IndexMap<EntityId, Entity>,
}

impl EntityDb {
    /// An empty database (the pre-construction snapshot).
    #[must_use]
    pub fn empty() -> EntityDb {
        EntityDb {
            entities: IndexMap::new(),
        }
    }

    /// Look up an entity by id.
    #[must_use]
    pub fn get(&self, id: EntityId) -> Option<&Entity> {
        self.entities.get(&id)
    }

    /// Number of entities in this snapshot.
    #[must_use]
    pub fn len(&self) -> usize {
        self.entities.len()
    }

    /// True when the snapshot is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entities.is_empty()
    }

    /// Commit a predicted delta against domain-supplied new entities,
    /// producing a NEW snapshot (owner transfer, consumption, orbit
    /// intersection/splitting). Never mutates `self`.
    #[must_use]
    pub fn commit(&self, _delta: &PredictedDelta, _new_entities: &[Entity]) -> EntityDb {
        todo!("STUB WO-07: apply creates/modifies/consumes to a clone; update owners + orbits")
    }

    /// The content address of this snapshot, stable under key order
    /// (AD-6). Used for incremental caching and lockfile provenance.
    #[must_use]
    pub fn snapshot_hash(&self) -> String {
        todo!("STUB WO-07: canonical-encode entities in id order, blake3 via rockhead-util")
    }
}

#[cfg(test)]
mod tests {
    use super::{Entity, EntityDb, EntityId, EntityKind};
    use rockhead_util::{IndexMap, IndexSet};

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

    #[test]
    fn entity_round_trips_json() {
        let e = face(1);
        let json = serde_json::to_string(&e).unwrap();
        let back: Entity = serde_json::from_str(&json).unwrap();
        assert_eq!(back, e);
    }
}
