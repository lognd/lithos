//! The execution model: stage pipelines, concurrent scopes with
//! snapshot reads, commit/merge, setups, and pieces.
//!
//! Substrate reference: `docs/substrate/06` (all) and `docs/mech/02`
//! sec. 2-4, 7a (pieces). Scopes read committed SNAPSHOTS: referencing a
//! sibling scope's exports is a compile error naming the later-scope
//! fix. Impl binding resolves at stage exit (SEAM-1 rule 1). Per-stage
//! process binding looks up a capability table whose DATA arrives with
//! WO-16; this WO stubs the lookup slot.

use regolith_diag::{codes, Diagnostic};
use regolith_util::IndexMap;
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

    /// Topological order of the stages (parents before children), via
    /// Kahn's algorithm over the `from=`/`joins=` parent edges. Import
    /// entry stages have no parent edges.
    ///
    /// # Errors
    /// Returns diagnostics if the graph has a cycle or a dangling parent
    /// (a `from=`/`joins=` naming a stage id this graph does not have).
    ///
    /// # Panics
    /// Never in practice: every in-degree entry is inserted before any
    /// edge can reference it.
    pub fn topo_order(&self) -> Result<Vec<StageId>, Vec<Diagnostic>> {
        let mut parents: IndexMap<StageId, Vec<StageId>> = IndexMap::new();
        let mut dangling = Vec::new();
        for (id, stage) in &self.stages {
            let ps: Vec<StageId> = match &stage.entry {
                StageEntry::From(p) => vec![*p],
                StageEntry::Joins(ps) => ps.clone(),
                StageEntry::Import { .. } => Vec::new(),
            };
            for p in &ps {
                if !self.stages.contains_key(p) {
                    dangling.push(Diagnostic::error(
                        codes::AMBIGUOUS_SELECTION,
                        format!(
                            "stage `{}` names a parent stage that does not exist",
                            stage.label
                        ),
                    ));
                }
            }
            parents.insert(*id, ps);
        }
        if !dangling.is_empty() {
            return Err(dangling);
        }

        let mut indegree: IndexMap<StageId, usize> = IndexMap::new();
        let mut children: IndexMap<StageId, Vec<StageId>> = IndexMap::new();
        for (id, ps) in &parents {
            indegree.insert(*id, ps.len());
            for p in ps {
                children.entry(*p).or_default().push(*id);
            }
        }

        let mut queue: Vec<StageId> = indegree
            .iter()
            .filter(|(_, &degree)| degree == 0)
            .map(|(id, _)| *id)
            .collect();
        queue.sort_unstable();

        let mut order = Vec::new();
        let mut idx = 0;
        while idx < queue.len() {
            let id = queue[idx];
            idx += 1;
            order.push(id);
            if let Some(kids) = children.get(&id) {
                let mut kids = kids.clone();
                kids.sort_unstable();
                for kid in kids {
                    let degree = indegree.get_mut(&kid).expect("kid was inserted above");
                    *degree -= 1;
                    if *degree == 0 {
                        queue.push(kid);
                    }
                }
            }
        }

        if order.len() != self.stages.len() {
            return Err(vec![Diagnostic::error(
                codes::AMBIGUOUS_SELECTION,
                "the stage graph has a cycle in its from/joins edges".to_string(),
            )]);
        }
        Ok(order)
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
///
/// This module tracks the scope DAG structurally (parent -> children
/// edges) but not per-statement name references (those live in the
/// AST/IR layers above); the structural proxy for "reads a sibling's
/// export" is a scope index reachable as a child of more than one
/// parent -- it is being treated as a descendant of two unrelated
/// lineages, which is exactly the diamond a legitimate DAG join
/// (`joins=`, `align:`) declares explicitly elsewhere, never as a bare
/// scope child edge. Every such scope is flagged, naming the siblings
/// it is reachable from.
#[must_use]
pub fn check_sibling_reads(scopes: &[Scope]) -> Vec<Diagnostic> {
    let mut parent_of: IndexMap<usize, Vec<usize>> = IndexMap::new();
    for (idx, scope) in scopes.iter().enumerate() {
        for &child in &scope.children {
            parent_of.entry(child).or_default().push(idx);
        }
    }

    let scope_name = |i: usize| -> String {
        scopes
            .get(i)
            .and_then(|s| s.label.clone())
            .unwrap_or_else(|| format!("scope#{i}"))
    };

    let mut diags = Vec::new();
    for (child, parents) in &parent_of {
        if parents.len() > 1 {
            let names: Vec<String> = parents.iter().map(|&p| scope_name(p)).collect();
            diags.push(
                Diagnostic::error(
                    codes::AMBIGUOUS_SELECTION,
                    format!(
                        "`{}` is reachable from sibling scopes {}; it cannot read their \
                         uncommitted exports",
                        scope_name(*child),
                        names.join(", ")
                    ),
                )
                .with_fix(regolith_diag::Fix {
                    message: "move the reference into a later `then` scope, after both \
                              siblings have committed"
                        .to_string(),
                    replacement: None,
                }),
            );
        }
    }
    diags
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
