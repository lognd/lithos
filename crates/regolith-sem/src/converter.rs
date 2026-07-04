//! The continuous/discrete converter graph and the INV-16 acyclicity
//! check (converter non-instantaneity).
//!
//! Substrate reference: `docs/substrate/13-invariants.md` INV-16 and
//! `docs/cuprite/03-behavioral-layer.md` sec. 1a (event-bounded hybrid
//! semantics, the ZOH delta rule). INV-16 states: *no algebraic loop
//! crosses the continuous/discrete boundary*. Its proof argument has two
//! independent halves, both realized here:
//!
//! 1. **The ZOH delta-by-type rule.** Every converter port (`adc`,
//!    `comparator`, `dac`, `pwm`, clocked `digital` drive) samples the
//!    pre-instant value and applies its update post-instant. That delta
//!    is a property *of the edge kind*, not of any causality analysis:
//!    a converter edge -- and, by typing, ANY domain-crossing edge --
//!    cannot participate in a zero-delay cycle. Clocked non-blocking
//!    (`<=`) register updates commit at instant end and are deltas too.
//! 2. **The within-domain acyclicity check.** A combinational
//!    (instantaneous `=`) network entirely inside one clock/continuous
//!    domain must be acyclic; a cycle with no delta to break it is a
//!    static error (E0105).
//!
//! Composed: any cross-boundary cycle contains a converter, every
//! converter contains a delta, so no zero-delay cross-boundary cycle can
//! exist; within-domain combinational cycles are rejected here. The
//! check is SOUND (under-approximate): it traverses ONLY same-domain
//! combinational edges, so it flags exactly the loops the source
//! declares within one domain and never a loop a converter/register
//! already breaks.
//!
//! Scope note: the graph is consumed from a typed input model. Promoting
//! the elec `spec:`/`ports:`/converter bodies (still `OpaqueIsland` after
//! WO-05) into that model is `regolith-syntax` work; this module is the
//! sound mechanism awaiting those typed nodes (see `regolith-lower`
//! `checks.rs` for the integration seam).

use std::collections::BTreeMap;

use regolith_diag::{codes, Diagnostic, Fix};
use serde::{Deserialize, Serialize};

/// A behavioral domain: the single continuous (DAE) frame, or one
/// synchronous-reactive clock domain named by its clock. Domain
/// membership is a partition enforced by typing (cuprite/03 sec. 1a);
/// two nodes are in the same domain iff their `Domain` values are equal.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum Domain {
    /// The continuous subset (physical quantities evolving as a DAE
    /// between event instants).
    Continuous,
    /// One clock domain's synchronous-reactive island, keyed by clock name.
    Clock(String),
}

/// The kind of a dependency edge, which fixes -- by type, not by
/// analysis -- whether it carries a ZOH delta (INV-16 mechanism 1).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EdgeKind {
    /// An instantaneous `=` dependency: the target's value depends on the
    /// source's value *within the same instant*. The only edge kind that
    /// can form an algebraic loop; must stay within one domain.
    Combinational,
    /// A converter port (`adc`/`comparator`/`dac`/`pwm`/clocked drive):
    /// samples pre-instant, updates post-instant (ZOH). A delta -- it
    /// cannot close a zero-delay cycle.
    Converter,
    /// A clocked non-blocking (`<=`) register update: commits at instant
    /// end, so the reader sees the pre-instant state. A delta.
    Register,
}

impl EdgeKind {
    /// Whether this edge carries a non-instantaneous delta (ZOH or
    /// register commit) -- i.e. it structurally breaks any cycle it lies
    /// on. Combinational edges do not; converters and registers do.
    #[must_use]
    pub fn is_delta(self) -> bool {
        matches!(self, EdgeKind::Converter | EdgeKind::Register)
    }
}

/// A graph node: a signal or block occupying exactly one domain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Node {
    /// The signal/block name, used in diagnostics.
    pub name: String,
    /// The domain this node lives in (partition membership).
    pub domain: Domain,
}

/// A dependency edge from a producer node to a consumer node.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Edge {
    /// Producer node index (the value read).
    pub from: usize,
    /// Consumer node index (the value defined).
    pub to: usize,
    /// The edge's kind, which fixes its delta property.
    pub kind: EdgeKind,
}

/// The converter graph: domain-tagged nodes and their dependency edges.
/// Built from parsed `.cupr` (once the behavioral bodies are typed) and
/// then checked for within-domain combinational cycles (INV-16).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConverterGraph {
    /// The nodes, addressed by index (stable insertion order).
    pub nodes: Vec<Node>,
    /// The dependency edges.
    pub edges: Vec<Edge>,
}

impl ConverterGraph {
    /// An empty graph.
    #[must_use]
    pub fn new() -> ConverterGraph {
        ConverterGraph::default()
    }

    /// Add a node and return its index.
    pub fn add_node(&mut self, name: impl Into<String>, domain: Domain) -> usize {
        let id = self.nodes.len();
        self.nodes.push(Node {
            name: name.into(),
            domain,
        });
        id
    }

    /// Add a dependency edge between two existing node indices.
    pub fn add_edge(&mut self, from: usize, to: usize, kind: EdgeKind) {
        self.edges.push(Edge { from, to, kind });
    }

    /// Whether an edge crosses the domain boundary (its endpoints are in
    /// different domains). By typing, such an edge is always a converter,
    /// so it is treated as a delta regardless of its recorded kind --
    /// this is what makes the check sound: a domain-crossing edge ALWAYS
    /// breaks a would-be cycle (INV-16 mechanism 1).
    #[must_use]
    fn crosses_domain(&self, edge: &Edge) -> bool {
        self.nodes[edge.from].domain != self.nodes[edge.to].domain
    }

    /// Whether an edge breaks any cycle it lies on: it carries a ZOH /
    /// register delta by kind, OR it crosses the continuous/discrete
    /// boundary (a converter by typing). Only edges that do NEITHER --
    /// same-domain combinational edges -- can close an algebraic loop.
    #[must_use]
    fn breaks_cycle(&self, edge: &Edge) -> bool {
        edge.kind.is_delta() || self.crosses_domain(edge)
    }

    /// Find combinational cycles: every simple cycle in the subgraph of
    /// same-domain combinational edges (deltas and domain crossings
    /// excluded). Each returned cycle is the node-index path back to its
    /// entry node. Deterministic (nodes visited in index order).
    #[must_use]
    pub fn combinational_cycles(&self) -> Vec<Vec<usize>> {
        // Adjacency built from cycle-forming edges only.
        let mut adj: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for edge in &self.edges {
            if self.breaks_cycle(edge) {
                continue;
            }
            adj.entry(edge.from).or_default().push(edge.to);
        }

        let mut cycles = Vec::new();
        let mut color = vec![Color::White; self.nodes.len()];
        let mut stack: Vec<usize> = Vec::new();
        for start in 0..self.nodes.len() {
            if color[start] == Color::White {
                dfs_cycles(start, &adj, &mut color, &mut stack, &mut cycles);
            }
        }
        cycles
    }

    /// The INV-16 within-domain acyclicity check: one E0105 diagnostic
    /// per combinational cycle, naming the looping signals and the fix
    /// (insert a converter/register delta to break it). An empty result
    /// means every declared cycle is broken by a converter or register
    /// (loop-free in the combinational sense) -- the legal case.
    #[must_use]
    pub fn check_acyclic(&self) -> Vec<Diagnostic> {
        let cycles = self.combinational_cycles();
        if cycles.is_empty() {
            tracing::debug!(
                nodes = self.nodes.len(),
                edges = self.edges.len(),
                "INV-16: converter graph combinationally acyclic"
            );
            return Vec::new();
        }
        cycles
            .iter()
            .map(|cycle| {
                let path = cycle
                    .iter()
                    .map(|&id| self.nodes[id].name.as_str())
                    .collect::<Vec<_>>()
                    .join(" -> ");
                tracing::info!(cycle = %path, "INV-16: combinational cycle within one domain -> E0105");
                Diagnostic::error(
                    codes::COMBINATIONAL_CYCLE,
                    format!("combinational cycle within one domain: {path}"),
                )
                .with_fix(Fix {
                    message:
                        "break the loop with a converter port (adc/comparator/dac/pwm) or a clocked \
                         `<=` register so a ZOH delta interrupts it"
                            .to_string(),
                    replacement: None,
                })
            })
            .collect()
    }
}

/// DFS colouring for simple-cycle detection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Color {
    /// Unvisited.
    White,
    /// On the current DFS stack (a back-edge to it closes a cycle).
    Gray,
    /// Fully explored.
    Black,
}

/// Iterative-safe recursive DFS recording each back-edge as a cycle
/// (the stack slice from the target node to the current node).
fn dfs_cycles(
    node: usize,
    adj: &BTreeMap<usize, Vec<usize>>,
    color: &mut [Color],
    stack: &mut Vec<usize>,
    cycles: &mut Vec<Vec<usize>>,
) {
    color[node] = Color::Gray;
    stack.push(node);
    if let Some(succs) = adj.get(&node) {
        for &next in succs {
            match color[next] {
                Color::White => dfs_cycles(next, adj, color, stack, cycles),
                Color::Gray => {
                    // Back-edge: the cycle is stack[pos..] where
                    // stack[pos] == next.
                    if let Some(pos) = stack.iter().position(|&n| n == next) {
                        cycles.push(stack[pos..].to_vec());
                    }
                }
                Color::Black => {}
            }
        }
    }
    stack.pop();
    color[node] = Color::Black;
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A genuine combinational cycle within one clock domain (`a = f(b)`,
    /// `b = g(a)`, both instantaneous) is a static error (E0105).
    #[test]
    fn within_domain_combinational_cycle_is_flagged() {
        let mut g = ConverterGraph::new();
        let clk = Domain::Clock("sys".to_string());
        let a = g.add_node("a", clk.clone());
        let b = g.add_node("b", clk);
        g.add_edge(a, b, EdgeKind::Combinational);
        g.add_edge(b, a, EdgeKind::Combinational);

        let diags = g.check_acyclic();
        assert_eq!(diags.len(), 1, "one cycle expected");
        assert_eq!(diags[0].code, codes::COMBINATIONAL_CYCLE);
    }

    /// The comparator-feeds-its-own-threshold loop (INV-16's legal
    /// fixture): the feedback path passes through converters (comparator
    /// sampling the continuous plant, a dac/pwm driving it), so the loop
    /// is broken by a ZOH delta -- loop-free in the combinational sense.
    #[test]
    fn comparator_feeds_own_threshold_is_legal() {
        let mut g = ConverterGraph::new();
        let disc = Domain::Clock("ctrl".to_string());
        let cont = Domain::Continuous;
        // Continuous plant output, the discrete comparator result, and
        // the discrete threshold the comparator feeds back into.
        let plant = g.add_node("v_out", cont);
        let cmp = g.add_node("cmp_out", disc.clone());
        let thresh = g.add_node("threshold", disc);
        // comparator samples the continuous plant (converter, cont->disc)
        g.add_edge(plant, cmp, EdgeKind::Converter);
        // comparator result sets the threshold, same domain, instantaneous
        g.add_edge(cmp, thresh, EdgeKind::Combinational);
        // the threshold drives the plant back via a converter (disc->cont)
        g.add_edge(thresh, plant, EdgeKind::Converter);

        // A graph cycle exists (cmp->thresh->plant->cmp) but two edges are
        // converters, so the combinational subgraph is acyclic.
        assert!(g.combinational_cycles().is_empty());
        assert!(g.check_acyclic().is_empty());
    }

    /// A loop broken by a clocked `<=` register (not a converter) is also
    /// legal: the register commit is a delta.
    #[test]
    fn register_broken_loop_is_legal() {
        let mut g = ConverterGraph::new();
        let clk = Domain::Clock("sys".to_string());
        let a = g.add_node("a", clk.clone());
        let b = g.add_node("b", clk);
        g.add_edge(a, b, EdgeKind::Combinational);
        g.add_edge(b, a, EdgeKind::Register);
        assert!(g.check_acyclic().is_empty());
    }

    /// Soundness: a same-domain combinational cycle is flagged, but if the
    /// very same topology crosses domains (so an edge is a converter by
    /// typing), it is not -- a domain-crossing edge always breaks it.
    #[test]
    fn domain_crossing_edge_always_breaks_the_cycle() {
        // Same two-edge loop, but the nodes are in different domains, so
        // one edge is a domain crossing (a converter by typing) even
        // though it is recorded Combinational: no cycle.
        let mut g = ConverterGraph::new();
        let a = g.add_node("a", Domain::Continuous);
        let b = g.add_node("b", Domain::Clock("sys".to_string()));
        g.add_edge(a, b, EdgeKind::Combinational);
        g.add_edge(b, a, EdgeKind::Combinational);
        assert!(
            g.check_acyclic().is_empty(),
            "a cross-domain edge must break the cycle (INV-16 soundness)"
        );
    }

    /// A self-loop that is combinational within one domain is a cycle;
    /// the same self-dependency through a register is legal.
    #[test]
    fn self_loop_cases() {
        let mut g = ConverterGraph::new();
        let clk = Domain::Clock("sys".to_string());
        let a = g.add_node("a", clk);
        g.add_edge(a, a, EdgeKind::Combinational);
        assert_eq!(g.check_acyclic().len(), 1);

        let mut h = ConverterGraph::new();
        let clk = Domain::Clock("sys".to_string());
        let a = h.add_node("a", clk);
        h.add_edge(a, a, EdgeKind::Register);
        assert!(h.check_acyclic().is_empty());
    }

    /// An empty graph is trivially acyclic (the state the lowering seam
    /// runs over until the elec behavioral bodies are typed).
    #[test]
    fn empty_graph_is_acyclic() {
        assert!(ConverterGraph::new().check_acyclic().is_empty());
    }
}
