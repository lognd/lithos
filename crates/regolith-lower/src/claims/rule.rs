use super::{
    AstNode, Claim, ClaimForm, Decl, EntitySnapshots, Field, Given, Obligation, SweepDomain,
};

/// WO-28: one obligation per attached rule per consuming declaration
/// whose evaluation was not a clean pass. Violated matches make the
/// obligation's given name each failing entity with its evaluated
/// detail; deferred matches name the blocking fact (D-E: "givens name
/// the required facts"). The claim name is the rule's waive-target
/// spelling (`dfm(pack.rule)`), so `waive dfm(pack.rule)` matches it
/// through the EXISTING ladder (D-D: zero new override surface).
/// `advise:` rules never lower (droppable guidance is never
/// load-bearing, INV-3).
pub(crate) fn push_rule_obligations(
    obligations: &mut Vec<Obligation>,
    outcomes: &[crate::rule_engine::RuleEvaluation],
    snapshots: &EntitySnapshots,
) {
    for eval in outcomes {
        let rule = &eval.rule;
        if rule.demand.is_none() {
            continue;
        }
        if eval.is_clean_pass() {
            continue;
        }
        let subject_ref = snapshots
            .scopes
            .get(&eval.decl_name)
            .map(regolith_sem::EntityDb::snapshot_hash)
            .unwrap_or_default();

        let demand_text = rule.demand.clone().unwrap_or_default();
        let form = match crate::rule_engine::split_comparison(&demand_text) {
            Some((lhs, op, rhs)) => ClaimForm::Comparison {
                lhs: lhs.trim().to_string(),
                op: op.to_string(),
                rhs: rhs.trim().to_string(),
            },
            None => ClaimForm::Comparison {
                lhs: demand_text.clone(),
                op: "holds".to_string(),
                rhs: String::new(),
            },
        };

        let mut refs: Vec<(String, String)> = Vec::new();
        for (origin, detail, _margin) in &eval.violations {
            refs.push((origin.clone(), format!("violated: {detail}")));
        }
        for (origin, fact) in &eval.deferrals {
            refs.push((origin.clone(), format!("requires fact: {fact}")));
        }

        let mut hints = Vec::new();
        if let Some(why) = &rule.why {
            hints.push(format!("why: {why}"));
        }
        if let Some(per) = &rule.per {
            hints.push(format!("per: {per}"));
        }

        let forall = match (&rule.forall_var, rule.query_text.is_empty()) {
            (Some(var), false) => vec![format!("{var} in {}", rule.query_text)],
            _ => Vec::new(),
        };
        let sweep = rule.forall_var.as_ref().map(|var| SweepDomain {
            axis: var.clone(),
            domain: rule.query_text.clone(),
        });

        tracing::info!(
            rule = %rule.qualified(),
            subject = %eval.decl_name,
            violations = eval.violations.len(),
            deferrals = eval.deferrals.len(),
            "lowering rule outcome to an obligation"
        );
        obligations.push(Obligation {
            claim: Claim {
                name: Some(rule.claim_name()),
                form,
                forall,
                sf: None,
                scatter_factor: None,
                trust_floor: None,
                hints: hints.clone(),
                model_pin: None,
            },
            subject_ref,
            given: Given {
                materials: Vec::new(),
                loads: Vec::new(),
                backing: Vec::new(),
                refs,
            },
            hints,
            sweep,
            payloads: Vec::new(),
        });
    }
}

/// Collect a declaration's structured materials and loads into a
/// [`Given`] (BE-2). `material`/`materials` fields become
/// `given.materials`; the child lines of a `loads:` block become
/// `given.loads` (as `name: value` text). Reading the typed `Field`
/// tree (not a raw text scan) keeps the obligation key sensitive to the
/// exact declared values while staying deterministic (source order).
pub(crate) fn given_for_decl(decl: &Decl) -> Given {
    let mut materials = Vec::new();
    let mut loads = Vec::new();

    for node in decl.syntax().descendants() {
        let Some(field) = Field::cast(node.clone()) else {
            continue;
        };
        let name = field.name();
        let leaf = name.rsplit('.').next().unwrap_or(&name);
        if matches!(leaf, "material" | "materials") {
            if let Some(value) = field.value() {
                materials.push((name.clone(), value.text().to_string().trim().to_string()));
            }
        }
        if leaf == "loads" {
            for inner in node.descendants() {
                if inner == node {
                    continue;
                }
                let Some(load) = Field::cast(inner) else {
                    continue;
                };
                if let Some(value) = load.value() {
                    loads.push(format!(
                        "{}: {}",
                        load.name(),
                        value.text().to_string().trim()
                    ));
                }
            }
        }
    }

    Given {
        materials,
        loads,
        backing: Vec::new(),
        refs: Vec::new(),
    }
}
