//! The execution model: stage pipelines, concurrent scopes with
//! snapshot reads, commit/merge, setups, and pieces.
//!
//! Substrate reference: `docs/substrate/06` (all) and `docs/mech/02`
//! sec. 2-4, 7a (pieces). Scopes read committed SNAPSHOTS: referencing a
//! sibling scope's exports is a compile error naming the later-scope
//! fix. Impl binding resolves at stage exit (SEAM-1 rule 1). Per-stage
//! process binding looks up a capability table whose DATA arrives with
//! WO-16; this WO stubs the lookup slot.

use rockhead_diag::Diagnostic;
use rockhead_util::IndexMap;
use serde::{Deserialize, Serialize};

use crate::entity::EntityId;

/// A stage identifier within a pipeline.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct StageId(pub u32);

/// How a stage enters: from one parent, joining several piece-parents,
/// or an import entry stage.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StageEntry {
    /// `from=<parent>`: a single-parent continuation.
    From(StageId),
    /// `joins=[...]`: multiple piece-parents merge here.
    Joins(Vec<StageId>),
    /// `import(path) [sealed]`: an entry stage from another artifact.
    Import {
        /// The imported artifact path.
        path: String,
        /// Whether the import is sealed (opaque, no further modification).
        sealed: bool,
    },
}

/// One stage in the pipeline.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Stage {
    /// Stage id.
    pub id: StageId,
    /// User label.
    pub label: String,
    /// How the stage enters.
    pub entry: StageEntry,
    /// Bound process/capability name; resolved against the capability
    /// table (WO-16 data). `None` = planner-allocated.
    pub process: Option<String>,
}

/// The stage graph of an artifact.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct StageGraph {
    stages: IndexMap<StageId, Stage>,
}

impl StageGraph {
    /// An empty graph.
    #[must_use]
    pub fn new() -> StageGraph {
        StageGraph {
            stages: IndexMap::new(),
        }
    }

    /// Add a stage.
    pub fn add(&mut self, stage: Stage) {
        self.stages.insert(stage.id, stage);
    }

    /// Topological order of the stages (parents before children).
    ///
    /// # Errors
    /// Returns diagnostics if the graph has a cycle or a dangling parent.
    pub fn topo_order(&self) -> Result<Vec<StageId>, Vec<Diagnostic>> {
        todo!("STUB WO-10: Kahn topo-sort over from/joins edges; cycle/dangling -> diagnostics")
    }
}

/// A scope within a stage/setup: `then [label] [on <region>]:`. Scopes
/// form a DAG and read committed snapshots only.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Scope {
    /// Optional scope label.
    pub label: Option<String>,
    /// Optional owned region the scope is guarded on (`on <region>`).
    pub on_region: Option<EntityId>,
    /// Child scope ids (the DAG edges).
    pub children: Vec<usize>,
}

/// A machining/assembly setup: ordered, with held entities and optional
/// refixturing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Setup {
    /// Position in the setup order.
    pub order: u32,
    /// Entities held (consumed) by this setup (`hold:`).
    pub hold: Vec<EntityId>,
    /// Whether this setup flips the workpiece (`flip about`), injecting a
    /// refixture-tolerance scatter entry at stage level.
    pub flip_about: Option<String>,
}

/// A piece in a multi-piece (weldment/panel) unified DB, with per-piece
/// provenance.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Piece {
    /// Piece name.
    pub name: String,
    /// Provenance tag (which source piece produced these entities).
    pub provenance: String,
}

/// Check the snapshot-read rule: a reference to a sibling scope's
/// exports (rather than a committed snapshot) is a compile error naming
/// the later-scope fix.
#[must_use]
pub fn check_sibling_reads(_scopes: &[Scope]) -> Vec<Diagnostic> {
    todo!("STUB WO-10: flag references to sibling-scope exports; suggest a later scope")
}

#[cfg(test)]
mod tests {
    use super::{Stage, StageEntry, StageGraph, StageId};

    #[test]
    fn stage_graph_round_trips_json() {
        let mut g = StageGraph::new();
        g.add(Stage {
            id: StageId(0),
            label: "src".to_string(),
            entry: StageEntry::Import {
                path: "stock.hem".to_string(),
                sealed: true,
            },
            process: None,
        });
        let json = serde_json::to_string(&g).unwrap();
        let back: StageGraph = serde_json::from_str(&json).unwrap();
        assert_eq!(back, g);
    }
}
