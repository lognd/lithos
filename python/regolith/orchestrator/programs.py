"""Pipeline-produced realizer programs (WO-51 deliverable 4).

Promote the ``feature_programs`` the Rust ``lower.programs`` pass emits
into ``BuildPayload`` (scalar ops + D150 promoted sketches + D151/D152
cavity-derived ``flow_paths``) into the realizer's input contract
(:class:`regolith.realizer.mech.schema.FeatureProgram`), keyed by the
``from=<ref>`` subject each flow path's selector names -- so
:func:`regolith.orchestrator.orchestrate.staged_build` no longer needs
caller-supplied programs (the caller channel stays as an override for
tests, AD-22).

HONESTY CONTRACT (AD-25, D151/D152 verbatim): a program converts ONLY
when every field the realizer contract requires is DECLARED in the
emitted IR -- a fully pinned promoted sketch (the outline is a
cumulative cardinal walk over exact declared lengths -- arithmetic on
declared facts, never computed geometry), a blank/pocket op with a
declared depth (the solid), and per-segment declared
diameter/depth/elevation/roughness facts. Anything indeterminate makes
the program non-convertible: it is SKIPPED with a named reason at INFO
(the subject stays pending and its obligations stay honestly
indeterminate) -- never guessed.
"""

from __future__ import annotations

import json
import logging
import math

from regolith.realizer.mech.schema import (
    BlankOp,
    FeatureProgram,
    FlowPath,
    FlowSegment,
    Point2,
    ResolvedParam,
    Sketch,
    Stage,
)

_log = logging.getLogger(__name__)

#: Unit scale factors to meters for the declared-quantity texts the
#: emitted IR carries (`80mm`); anything else is a named skip.
_LENGTH_SCALE: dict[str, float] = {"mm": 1.0e-3, "cm": 1.0e-2, "m": 1.0}

#: Cardinal walk headings (degrees) to exact unit direction vectors --
#: the same exact-cosine contract as the Rust promotion (INV-10).
_DIRECTIONS: dict[float, tuple[float, float]] = {
    0.0: (1.0, 0.0),
    90.0: (0.0, 1.0),
    180.0: (-1.0, 0.0),
    270.0: (0.0, -1.0),
}


def _quantity_m(text: str) -> float | None:
    """Parse a declared length text (`8mm`) to meters; ``None`` (a named
    skip upstream) for expressions or unknown suffixes."""
    split = len(text)
    for i, ch in enumerate(text):
        if not (ch.isdigit() or ch in ".-"):
            split = i
            break
    try:
        value = float(text[:split])
    except ValueError:
        return None
    suffix = text[split:].strip()
    scale = _LENGTH_SCALE.get(suffix)
    if scale is None:
        return None
    return value * scale


def _declared(fact: object) -> str | None:
    """The value of a `DerivedFact::Declared`; ``None`` when the fact is
    honestly indeterminate (which makes the program non-convertible)."""
    if not isinstance(fact, dict):
        return None
    declared = fact.get("declared")
    if isinstance(declared, dict):
        value = declared.get("value")
        if isinstance(value, str):
            return value
    return None


def _outline(sketch: object) -> tuple[Point2, ...] | None:
    """The outline polygon of a PROMOTED, fully pinned cardinal sketch:
    the cumulative walk over exact declared lengths (the close edge is
    the implicit return to the start -- not a vertex). ``None`` when
    any segment is free/unsupported (the honest skip)."""
    if not isinstance(sketch, dict):
        return None
    promoted = sketch.get("promoted")
    if not isinstance(promoted, dict):
        return None
    unit = promoted.get("unit")
    symbol = unit.get("symbol") if isinstance(unit, dict) else None
    scale = _LENGTH_SCALE.get(symbol or "")
    if scale is None:
        return None
    segments = promoted.get("segments")
    if not isinstance(segments, list) or not segments:
        return None
    points = [Point2(x=0.0, y=0.0)]
    x, y = 0.0, 0.0
    for seg in segments:
        if not isinstance(seg, dict):
            return None
        length = seg.get("length")
        pinned = length.get("pinned") if isinstance(length, dict) else None
        if not isinstance(pinned, (int, float)):
            return None  # a free length: the outline is not declared
        angle = seg.get("angle_deg")
        if not isinstance(angle, (int, float)):
            return None
        direction = _DIRECTIONS.get(float(angle))
        if direction is None:
            return None
        magnitude = float(pinned) * scale
        x += direction[0] * magnitude
        y += direction[1] * magnitude
        points.append(Point2(x=x, y=y))
    # The last cumulative point is where the close edge departs; the
    # polygon's vertices are every walk corner (start included once).
    return tuple(points)


def _blank_op(
    program: dict[str, object], sketches: dict[str, object]
) -> tuple[str, str, BlankOp] | None:
    """The solid-producing op: the first blank/pocket feature whose
    referenced profile promotes to a fully pinned outline and whose
    thickness is declared. Returns ``(stage, process, op)``; ``None`` (a
    named skip upstream) when no such op exists.

    Thickness source (WO-62 D171/AD-32): a `blank` op's own `thickness`
    param wins when present (the sheet-gauge value, asserted or sourced
    from `process=laser_cut(sheet=<t>)`, INV-21 `cause:
    process(<proc>.sheet)`); a `pocket`/legacy `blank` op with no
    `thickness` param falls back to `depth` (the WO-51 coolant_gallery
    exemplar's non-sheet-metal convention -- an extrude depth doubling
    as its solid's thickness), preserving that pre-existing corpus
    conversion unchanged.
    """
    features = program.get("features")
    if not isinstance(features, list):
        return None
    for op in features:
        if not isinstance(op, dict) or op.get("kind") not in ("blank", "pocket"):
            continue
        params = op.get("params")
        if not isinstance(params, dict):
            continue
        profile = params.get("profile", {})
        profile_name = profile.get("text") if isinstance(profile, dict) else None
        if not isinstance(profile_name, str):
            continue
        thickness_param = params.get("thickness") or params.get("depth", {})
        thickness_text = (
            thickness_param.get("text") if isinstance(thickness_param, dict) else None
        )
        if not isinstance(thickness_text, str):
            continue
        outline = _outline(sketches.get(profile_name))
        thickness = _quantity_m(thickness_text)
        if outline is None or thickness is None:
            continue
        return (
            str(op.get("stage") or "main"),
            str(op.get("process") or "unspecified"),
            BlankOp(
                name=str(op.get("name") or "body"),
                sketch=Sketch(name=profile_name, outline=outline),
                thickness=ResolvedParam(value=thickness),
            ),
        )
    return None


def _segment(seg: dict[str, object]) -> FlowSegment | None:
    """One emitted `FlowSegmentIr` as a realizer `FlowSegment`: every
    required field must be declared. The flow area derives from the
    declared diameter (`pi * (d/2)^2` -- the op's section is circular
    by its kind, a declared fact); ``bore=None`` skips the D130
    cross-check (the IR keeps the binding for a future full
    conversion, matching the WO-42 fixture precedent)."""
    dia_text = _declared(seg.get("flow_area"))
    len_text = _declared(seg.get("length"))
    elev_text = _declared(seg.get("elevation_change"))
    rough = _declared(seg.get("roughness_class"))
    if dia_text is None or len_text is None or elev_text is None or rough is None:
        return None
    diameter = _quantity_m(dia_text)
    length = _quantity_m(len_text)
    if diameter is None or length is None:
        return None
    elevation = 0.0 if elev_text == "0" else _quantity_m(elev_text)
    if elevation is None:
        return None
    return FlowSegment(
        role=str(seg.get("role") or "run"),
        flow_area=ResolvedParam(value=math.pi * (diameter / 2.0) ** 2),
        length=ResolvedParam(value=length),
        elevation_change=ResolvedParam(value=elevation),
        roughness_class=rough,
    )


def emitted_realizer_programs(payload_json: bytes) -> dict[str, FeatureProgram]:
    """Every pipeline-emitted program that converts COMPLETELY into the
    realizer contract.

    Keyed by its flow paths' selector subjects (`milled.wetted` -- the
    exact `from=<ref>` string a fluorite edge spells, D130's pinned
    convention) when it has any; a part with a convertible solid but NO
    cavity queries (WO-62 D171/AD-32: a plain sheet-metal blank has
    nothing for a fluorite edge to consume) is ALSO promoted, keyed
    `<part_name>.<op_name>` (the same `<selector>.<binding>`-shaped
    convention, deterministic and collision-free against the D130 flow
    selectors since no `then:` op binding can spell a `.wetted` suffix).
    Non-convertible programs are skipped with the missing piece named
    at INFO; they stay pending."""
    if not payload_json:
        return {}
    payload = json.loads(payload_json)
    out: dict[str, FeatureProgram] = {}
    for program in payload.get("feature_programs") or []:
        if not isinstance(program, dict):
            continue
        part = str(program.get("part_name") or "?")
        flow_paths = program.get("flow_paths") or []
        sketches = program.get("sketches")
        blank = _blank_op(program, sketches if isinstance(sketches, dict) else {})
        if blank is None:
            _log.info(
                "emitted program for part=%s is not convertible: no blank/pocket op "
                "with a fully pinned promoted profile and a declared thickness "
                "(stays pending; obligations honestly indeterminate)",
                part,
            )
            continue
        stage_name, process, op = blank
        paths: list[FlowPath] = []
        convertible = True
        for path in flow_paths:
            segments = [_segment(s) for s in path.get("segments") or []]
            if not segments or any(s is None for s in segments):
                _log.info(
                    "emitted program for part=%s path=%s has an indeterminate "
                    "segment field (stays pending; never guessed)",
                    part,
                    path.get("selector"),
                )
                convertible = False
                break
            paths.append(
                FlowPath(
                    selector=str(path.get("selector") or ""),
                    segments=tuple(s for s in segments if s is not None),
                )
            )
        if not convertible:
            continue
        realizer_program = FeatureProgram(
            part_name=part,
            material=None,
            stages=(Stage(name=stage_name, process=process, features=(op,)),),
            flow_paths=tuple(paths),
        )
        subjects = [path.selector for path in paths] or [f"{part}.{op.name}"]
        for subject in subjects:
            if subject in out:
                _log.warning(
                    "subject %s emitted by more than one part; keeping the first "
                    "(deterministic file/decl order, AD-6)",
                    subject,
                )
                continue
            out[subject] = realizer_program
            _log.info(
                "pipeline-produced realizer program: part=%s subject=%s "
                "(WO-51 d4/WO-62 d2: no hand-authored program)",
                part,
                subject,
            )
    return out
