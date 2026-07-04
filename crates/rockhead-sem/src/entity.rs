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
    ///
    /// `new_entities` carries the post-delta state of every entity the
    /// delta creates or modifies (owner/orbit already updated by the
    /// caller); `consumes` names entities removed from the snapshot.
    /// Consumption is applied after the upserts so a construct may
    /// consume an entity in the same commit it (re-)creates under a
    /// different id.
    #[must_use]
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
    /// of commit history, then hashed with the one blessed primitive
    /// (`rockhead_util::hash_hex`, blake3).
    ///
    /// # Panics
    /// Never in practice: the lookup key always comes from this map's
    /// own key set, and `Entity` has no non-finite float fields to
    /// reject at serialization.
    #[must_use]
    pub fn snapshot_hash(&self) -> String {
        // TODO(AD-6): migrate off serde_json to the canonical-CBOR encoder
        // (domain_tag || schema_version || canonical_cbor) once WO-13 lands
        // it; a shared encoder belongs in rockhead-util so sem and oblig
        // reuse one home. Today only "stable under key order" (WO-07) is
        // required and met via id sorting; determinism holds (sorted ids,
        // stable field order, ryu floats).
        let mut ids: Vec<&EntityId> = self.entities.keys().collect();
        ids.sort();

        let mut buf = Vec::new();
        for id in ids {
            let entity = self
                .entities
                .get(id)
                .expect("id came from this map's own keys");
            let encoded =
                serde_json::to_vec(entity).expect("Entity serialization is total (no NaN/cycles)");
            buf.extend_from_slice(&(encoded.len() as u64).to_le_bytes());
            buf.extend_from_slice(&encoded);
        }
        rockhead_util::hash_hex(&buf)
    }

    /// Iterate entities in canonical (ascending id) order. Used by the
    /// query engine (WO-08) to enumerate a base selection; never expose
    /// `IndexMap`'s own iteration order here (AD-6).
    pub fn iter(&self) -> impl Iterator<Item = &Entity> {
        let mut entities: Vec<&Entity> = self.entities.values().collect();
        entities.sort_by_key(|e| e.id);
        entities.into_iter()
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
