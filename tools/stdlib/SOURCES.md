# tools/stdlib/ -- source ledger (WO-66, D174 sourcing law)

Every generated or hand-cited stdlib family added by WO-66 is listed
here: source document + revision/edition + license posture + fetch
date + which script (if any) produced it. Per-record citations live
in-file (each record's `evidence.reference`); this ledger is the
package-level index the sourcing law's rule 1 asks for.

No live network fetcher was written this dispatch: the cited
standards bodies (ISO, AISC) do not publish these tables as an open
API or a scrapeable page under a permissive TOS -- only as paid PDFs
or JS-rendered product pages (the WO-60 close-out already hit this
wall for CISC/CSA metric sections and recorded the same finding).
Per the sourcing law ("a family whose only source is closed stays
SMALL and hand-cited rather than large and stolen"), every table
below is a manual, cited transcription of widely-republished open
engineering-reference figures for the named standard, not a live
fetch -- fetch dates below mark when this transcription was written,
not an HTTP request timestamp. A polite official fetcher can be added
later if/when a source publishes a genuinely open, scrapeable table;
until then, generation runs over the COMMITTED input table only
(deterministic, no network at generation time either).

| family | source document | revision/edition | license posture | script | committed table | date |
|---|---|---|---|---|---|---|
| std.fasteners (SHCS, hex bolt, hex nut, washer) | ISO 4762 / ISO 4014 / ISO 4032 / ISO 7089 dimension tables; ISO 898-1 property classes | ISO 4762:2004, ISO 4014:2011, ISO 4032:2012, ISO 7089:2000, ISO 898-1:2013 | standard dimension figures, widely republished under open engineering-reference use; no vendor-proprietary data | `tools/stdlib/gen_fasteners.py` | `tools/stdlib/data/iso_fasteners.toml` | 2026-07-09 |
| std.civil channels/angles | AISC Steel Construction Manual 16th ed. / Shapes Database v16.0 | v16.0 (same edition WO-60 cited) | AISC public shapes database, open use for engineering reference | `tools/stdlib/gen_civil_sections.py` | `tools/stdlib/data/aisc_channels_angles.toml` | 2026-07-09 |
| std.elec E-series (resistor/capacitor parametric families) | IEC 60063 preferred number series | IEC 60063:2015 | standard's own published per-decade value list, open engineering-reference use | `tools/stdlib/gen_eseries.py` | `tools/stdlib/data/e_series.toml` | 2026-07-09 |
| std.elec connectors (JST-XH/PH, Molex KK, screw-terminal) | JST XH/PH series official connector drawings; Molex KK 254 series drawing; generic pluggable screw-terminal manufacturer catalogs | current catalog pages as of this dispatch | manufacturer datasheet/drawing figures, open engineering-reference use | none (hand-cited, not a standards-table generation candidate) | n/a | 2026-07-09 |
| std.bearings (deep-groove ball) | ISO 15 boundary dimensions; generic deep-groove ball bearing manufacturer general catalog load ratings | ISO 15:2011 | boundary dims per open standard; load ratings widely republished across manufacturer general catalogs | none (hand-cited seed) | n/a | 2026-07-09 |
| std.bearings (linear bushing, LM_UU class) | generic LM_UU form factor, widely republished across manufacturer general catalogs | n/a (no single governing standard for this class) | open engineering-reference use | none (hand-cited seed) | n/a | 2026-07-09 |
| std.bearings (angular-contact ball, 70xx C miniature) | ISO 15 boundary dimensions; conservative low end of the manufacturer general-catalog dynamic-rating range for the 15deg miniature series (low end is conservative for L10 lower bounds) | ISO 15:2011 | boundary dims per open standard; ratings widely republished across manufacturer general catalogs | none (hand-cited seed, WO-113) | n/a | 2026-07-13 |
| std.bearings (tapered roller, 320xx metric) | ISO 355 boundary dimensions; conservative low end of the manufacturer general-catalog dynamic-rating range for the series | ISO 355 | boundary dims per open standard; ratings widely republished across manufacturer general catalogs | none (hand-cited seed, WO-113) | n/a | 2026-07-13 |
| std.motion (steppers) | NEMA MG1 frame-size convention; typical rated points across commodity stepper manufacturer general catalogs | n/a | open engineering-reference use | none (hand-cited seed) | n/a | 2026-07-09 |
| std.motion (leadscrew/belt/rail) | DIN 103 (Tr thread form); GT2 timing-belt profile; common open-source motion-platform form factors | DIN 103 | open engineering-reference use | none (hand-cited seed) | n/a | 2026-07-09 |
| std.machines (mill/printer/laser classes) | representative envelope/kinematics classes across manufacturer general catalogs for each machine category | n/a (class records, not one vendor SKU) | open engineering-reference use | none (hand-cited seed) | n/a | 2026-07-09 |
| std.tooling (end mills, drills) | ISO 235 / DIN 338 jobber-drill series; common carbide end-mill dimension classes across cutting-tool manufacturer general catalogs | ISO 235, DIN 338 | open engineering-reference use | none (hand-cited seed) | n/a | 2026-07-09 |
| std.civil timber_sawn widening (2x6..2x12, 4x4/4x6, 6x8/6x10/6x12) | ALSC/PS 20-based NDS Supplement Table 1B nominal-to-dressed size table (same table the two pre-existing rows cite) | NDS Supplement Table 1B | standard dimension figures, widely republished under open engineering-reference use | none (hand-cited, computed section properties from dressed dims, same method as pre-existing rows) | n/a | 2026-07-10 |
| std.elec cells (Samsung INR18650-25R, EEMB LP503759, series_pack) | Samsung SDI INR18650-25R cell spec (Ver. 1.0), cross-checked via distributor-republished copies (nkon.nl, 18650batterystore.com, dnkpower.com); EEMB LP503759 product page (eemb.com/product-198) | Samsung INR18650-25R Spec. No. INR18650-25R Ver. 1.0; EEMB product page as fetched | manufacturer datasheet/product-page figures, open engineering-reference use | none (hand-cited; series_pack row is DERIVED arithmetic, not a transcribed vendor pack SKU) | n/a | 2026-07-10 |
| std.elec servos (Hitec HS-311, Hitec HS-55) | Hitec HS-311 General Specification sheet (horizonhobby.com PDF); Hitec HS-55 spec sheet (hiteccs.com), cross-checked against servodatabase.com's transcriptions | current manufacturer spec sheets as of this dispatch | manufacturer datasheet figures, open engineering-reference use | none (hand-cited) | n/a | 2026-07-10 |
| ti.mcu MSP430FR5 (MSP430FR5994/FR59941/FR5992/FR5964/FR5962, PM 64-pin package only) | TI MSP430FR5994/FR59941/FR5992/FR5964/FR5962 datasheet, fetched live from https://www.ti.com/lit/gpn/msp430fr5994 | SLASE54D Rev. D, MARCH 2016 - REVISED JANUARY 2021 | manufacturer datasheet figures, open-CDN fetch (TI); DigiKey is NOT a source anywhere in this row (D257) | `tools/stdlib/gen_processors.py` | `tools/stdlib/data/ti_mcu_msp430fr5.toml` | 2026-07-16 |

## Omission discipline (D174 sourcing law rule 1)

Fields not verifiable from an open source this session are OMITTED
with an in-record note, never guessed:

- std.fasteners: the standard's real per-diameter min/max LENGTH
  range is replaced by a representative common-stock length subset
  (8-50mm); nut proof-load-per-class table (ISO 898-2) is omitted.
- std.bearings linear bushings: dynamic/static load ratings omitted
  (no single boundary-dimension standard fixes them for this class
  the way ISO 15 fixes ball-bearing rings).
- std.motion linear rails (MGN12/15): dynamic/static load ratings
  omitted.
- std.elec cells: `eemb_lp503759` omits max charge voltage and max
  continuous discharge current -- not stated on the fetched EEMB
  product page, and the linked full datasheet PDF was not machine-
  readable this session (the alternate LiPol-overview PDF mirror
  returned HTTP 403). Not backfilled from generic Li-Po chemistry
  convention (4.20V is near-universal for this chemistry but was not
  independently confirmed for THIS part this session).

## Generation determinism

`make stdlib-gen` (`tools/stdlib/generate_all.py`) reads ONLY the
committed tables under `tools/stdlib/data/` and renders through the
shared `tools/stdlib/render.py` formatter (sorted keys, fixed float
repr) -- no wall-clock, no randomness, no network. Rerunning with an
unchanged input table produces byte-identical output
(`tests/tools/test_stdlib_gen_drift.py` enforces this both ways: zero
diff against committed files, and two in-process runs equal).
