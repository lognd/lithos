//! Budget arithmetic (L2): interval sums checked against a limit at the
//! worst-case corner, naming the worst contributors when a budget
//! cannot close (E0432).
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. Sums run in
//! source order with outward-rounded interval arithmetic (AD-6);
//! `locked:` entries are fixed contributions, reserves are held back for
//! targets.

use regolith_diag::{codes, Diagnostic};
use regolith_qty::{Comparator, Interval, Literal, Qty, ValueSource};

use crate::nodes::Budget;

/// Pull a concrete limit-like magnitude out of a value source, when one
/// is already resolved to a literal. `derived`/`allocated`/`free`/bare
/// `in [...]` sources have not resolved to a number yet at L2 -- the
/// budget check has nothing to compare against until they do, and
/// nothing upstream promises they are resolved this early (AD-6/INV-20:
/// cheaper checks run first, but resolution itself is a later pass).
fn literal_limit(vs: &ValueSource) -> Option<Qty> {
    match vs {
        ValueSource::Literal(Literal::Value(q) | Literal::Comparator(Comparator::AtMost(q))) => {
            Some(q.clone())
        }
        _ => None,
    }
}

/// One named contribution to a budget (an interval-valued draw).
#[derive(Debug, Clone)]
pub struct Contribution {
    /// Contributor name (for the E0432 diagnostic).
    pub name: String,
    /// The interval-valued amount it draws.
    pub amount: Interval,
    /// Whether this is a `locked:` (fixed) entry.
    pub locked: bool,
}

/// Check that a budget closes: the outward-rounded interval sum of the
/// contributions, plus any reserve, stays within the limit at the
/// worst-case corner.
///
/// # Errors
/// Returns an E0432 diagnostic naming the worst contributors when the
/// budget cannot close.
pub fn close_budget(
    budget: &Budget,
    contributions: &[Contribution],
) -> Result<(), Vec<Diagnostic>> {
    let Some(limit) = literal_limit(&budget.limit) else {
        // Limit has not resolved to a concrete literal yet; nothing to
        // check until it does (see `literal_limit`).
        return Ok(());
    };

    let mut diags = Vec::new();

    // Sum in fixed source order (AD-6); a contribution whose dimension
    // does not match the budget's own is a construction error, named
    // here rather than silently dropped or silently summed.
    let mut total: Option<Interval> = None;
    for c in contributions {
        total = Some(match total {
            None => c.amount.clone(),
            Some(t) => {
                if let Ok(sum) = t.add(&c.amount) {
                    sum
                } else {
                    diags.push(Diagnostic::error(
                        codes::BUDGET_CANNOT_CLOSE,
                        format!(
                            "budget `{}`: contributor `{}` has an incompatible dimension and \
                             cannot be summed into this budget",
                            budget.name, c.name
                        ),
                    ));
                    t
                }
            }
        });
    }

    let Some(mut total) = total else {
        // No contributions: the budget trivially closes.
        return if diags.is_empty() { Ok(()) } else { Err(diags) };
    };

    // Fold in the reserve (held back for targets), when it is itself a
    // resolved literal.
    if let Some(reserve_vs) = &budget.reserve {
        if let Some(reserve) = literal_limit(reserve_vs) {
            if let Ok(reserve_interval) = Interval::new(&reserve, &reserve) {
                match total.add(&reserve_interval) {
                    Ok(sum) => total = sum,
                    Err(_) => diags.push(Diagnostic::error(
                        codes::BUDGET_CANNOT_CLOSE,
                        format!(
                            "budget `{}`: its reserve has an incompatible dimension and cannot \
                             be folded into the budget total",
                            budget.name
                        ),
                    )),
                }
            }
        }
    }

    if total.unit().dimension != limit.dimension() {
        diags.push(Diagnostic::error(
            codes::BUDGET_CANNOT_CLOSE,
            format!(
                "budget `{}`: its running total's dimension does not match its limit's dimension",
                budget.name
            ),
        ));
        return Err(diags);
    }

    // Worst-case corner: the outward-rounded upper bound of the total
    // against the limit (closed interval -- exact equality closes).
    let worst_total = total.hi().magnitude();
    let limit_mag = if total.unit().symbol == limit.unit().symbol {
        limit.magnitude()
    } else {
        // Units differ but dimension matches (e.g. `mm` vs `m`); no
        // cross-unit conversion is exposed on this crate's `Qty`/`Unit`
        // API, so a mismatched-unit limit is reported rather than
        // silently mis-compared.
        diags.push(Diagnostic::error(
            codes::BUDGET_CANNOT_CLOSE,
            format!(
                "budget `{}`: total is expressed in `{}` but the limit is in `{}`; cannot \
                 compare without a shared unit",
                budget.name,
                total.unit().symbol,
                limit.unit().symbol
            ),
        ));
        return Err(diags);
    };

    if worst_total <= limit_mag {
        return if diags.is_empty() { Ok(()) } else { Err(diags) };
    }

    // Over budget: name the worst (largest) non-locked contributors
    // first; `locked:` entries are fixed truth, not adjustable draws, so
    // they are counted in the sum but not blamed. Ties keep source
    // order (stable sort, AD-6).
    let mut blamed: Vec<&Contribution> = contributions.iter().filter(|c| !c.locked).collect();
    if blamed.is_empty() {
        blamed = contributions.iter().collect();
    }
    blamed.sort_by(|a, b| {
        b.amount
            .hi()
            .magnitude()
            .partial_cmp(&a.amount.hi().magnitude())
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let worst_names: Vec<String> = blamed.iter().map(|c| c.name.clone()).collect();

    diags.push(Diagnostic::error(
        codes::BUDGET_CANNOT_CLOSE,
        format!(
            "budget `{}` cannot close: worst-case total {worst_total} exceeds limit {limit_mag} \
             (worst contributors: {})",
            budget.name,
            worst_names.join(", ")
        ),
    ));
    Err(diags)
}

#[cfg(test)]
mod tests {
    use super::{close_budget, Contribution};
    use crate::nodes::Budget;
    use num_rational::Ratio;
    use regolith_diag::codes;
    use regolith_qty::{BaseDimension, Dimension, Interval, Literal, Qty, Unit, ValueSource};

    fn grams() -> Unit {
        Unit {
            symbol: "g".to_string(),
            dimension: Dimension::base(BaseDimension::Mass),
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        }
    }

    fn mass_interval(lo: f64, hi: f64) -> Interval {
        Interval::new(&Qty::new(lo, grams()), &Qty::new(hi, grams())).unwrap()
    }

    fn mass_limit(x: f64) -> ValueSource {
        ValueSource::Literal(Literal::Value(Qty::new(x, grams())))
    }

    fn budget(limit: f64) -> Budget {
        Budget {
            name: "mass".to_string(),
            limit: mass_limit(limit),
            reserve: None,
        }
    }

    // Well-formed close and over-budget E0432 (naming worst contributors)
    // land with the arithmetic; the interval outward-rounding lives in
    // regolith-qty (WO-03).
    #[test]
    fn budget_closes_and_overflows() {
        let b = budget(100.0);

        // Empty ledger: trivially closes.
        assert!(close_budget(&b, &[]).is_ok());

        // Well within budget.
        let ok_contribs = vec![
            Contribution {
                name: "board".to_string(),
                amount: mass_interval(10.0, 20.0),
                locked: false,
            },
            Contribution {
                name: "case".to_string(),
                amount: mass_interval(30.0, 40.0),
                locked: false,
            },
        ];
        assert!(close_budget(&b, &ok_contribs).is_ok());

        // Exact-equality boundary: closed interval closes exactly at the
        // limit (not over).
        let boundary = vec![Contribution {
            name: "exact".to_string(),
            amount: mass_interval(0.0, 100.0),
            locked: false,
        }];
        assert!(close_budget(&b, &boundary).is_ok());

        // Over budget: E0432, naming the worst (largest) contributor
        // first; the locked entry is counted in the sum but never
        // blamed.
        let over_contribs = vec![
            Contribution {
                name: "locked-fixed".to_string(),
                amount: mass_interval(50.0, 50.0),
                locked: true,
            },
            Contribution {
                name: "small".to_string(),
                amount: mass_interval(1.0, 2.0),
                locked: false,
            },
            Contribution {
                name: "big".to_string(),
                amount: mass_interval(60.0, 70.0),
                locked: false,
            },
        ];
        let err = close_budget(&b, &over_contribs).unwrap_err();
        assert_eq!(err.len(), 1);
        assert_eq!(err[0].code, codes::BUDGET_CANNOT_CLOSE);
        assert!(err[0].message.contains("big"));
        // The worst (largest) non-locked contributor is named first.
        let big_pos = err[0].message.find("big").unwrap();
        let small_pos = err[0].message.find("small").unwrap();
        assert!(big_pos < small_pos);
        assert!(!err[0].message.contains("locked-fixed"));
    }

    #[test]
    fn mixed_dimension_contribution_is_rejected_not_silently_dropped() {
        let b = budget(100.0);
        let volts = Unit {
            symbol: "V".to_string(),
            dimension: Dimension::base(BaseDimension::Current),
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        };
        let bad = vec![
            Contribution {
                name: "mass-item".to_string(),
                amount: mass_interval(1.0, 2.0),
                locked: false,
            },
            Contribution {
                name: "wrong-dimension".to_string(),
                amount: Interval::new(&Qty::new(1.0, volts.clone()), &Qty::new(2.0, volts))
                    .unwrap(),
                locked: false,
            },
        ];
        let err = close_budget(&b, &bad).unwrap_err();
        assert!(
            err.iter()
                .any(|d| d.code == codes::BUDGET_CANNOT_CLOSE
                    && d.message.contains("wrong-dimension"))
        );
    }
}
