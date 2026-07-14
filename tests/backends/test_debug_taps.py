"""Tests for the WO-125 debug-tap model + deriver (D237.2)."""

from __future__ import annotations

from regolith.backends.debug_taps import ExplicitTap, TapCandidate, derive_taps


def _cands():
    return (
        TapCandidate(target_path="net.vcc_3v3", kind="rail", why="claim(power.vcc)"),
        TapCandidate(target_path="net.vcc_5v", kind="rail", why="claim(power.5v)"),
        TapCandidate(target_path="net.mclk", kind="clock", why="claim(clock.mclk)"),
        TapCandidate(target_path="net.spi_sck", kind="bus", why="claim(bus.spi)"),
        TapCandidate(target_path="net.gpio3", kind="signal", why="claim(io.gpio3)"),
        TapCandidate(target_path="net.gpio1", kind="signal", why="claim(io.gpio1)"),
    )


def test_derive_taps_ranks_by_family_then_path():
    result = derive_taps(_cands(), (), capacity=6)
    assert result.is_ok
    tap_set = result.danger_ok
    kinds = [t.kind for t in tap_set.taps]
    assert kinds == ["rail", "rail", "clock", "bus", "signal", "signal"]
    # within family, deterministic by target_path
    rails = [t.target_path for t in tap_set.taps if t.kind == "rail"]
    assert rails == sorted(rails)
    signals = [t.target_path for t in tap_set.taps if t.kind == "signal"]
    assert signals == ["net.gpio1", "net.gpio3"]
    assert tap_set.unallocated == ()


def test_derive_taps_channels_are_contiguous_from_zero():
    result = derive_taps(_cands(), (), capacity=6)
    tap_set = result.danger_ok
    assert [t.channel for t in tap_set.taps] == list(range(6))


def test_derive_taps_capacity_limit_names_unallocated():
    result = derive_taps(_cands(), (), capacity=3)
    assert result.is_ok
    tap_set = result.danger_ok
    assert len(tap_set.taps) == 3
    assert {t.kind for t in tap_set.taps} == {"rail", "clock"}
    unallocated_paths = {u.target_path for u in tap_set.unallocated}
    assert unallocated_paths == {"net.spi_sck", "net.gpio1", "net.gpio3"}
    for u in tap_set.unallocated:
        assert u.reason == "header capacity exceeded"


def test_explicit_tap_wins_channel_before_derived():
    explicit = (ExplicitTap(target_path="net.gpio3", why="debug spec block"),)
    result = derive_taps(_cands(), explicit, capacity=1)
    assert result.is_ok
    tap_set = result.danger_ok
    assert len(tap_set.taps) == 1
    assert tap_set.taps[0].target_path == "net.gpio3"
    assert tap_set.taps[0].source == "explicit"
    assert tap_set.taps[0].channel == 0
    # every rail/clock/bus candidate lost the single channel to the
    # explicit pick and is named, not dropped.
    assert len(tap_set.unallocated) == 5


def test_explicit_tap_unknown_net_path_is_a_diagnostic():
    explicit = (ExplicitTap(target_path="net.does_not_exist"),)
    result = derive_taps(_cands(), explicit, capacity=6)
    assert result.is_err
    assert result.danger_err.kind == "unknown_explicit_tap"
    assert "net.does_not_exist" in result.danger_err.message


def test_derive_taps_is_deterministic_across_calls():
    a = derive_taps(_cands(), (), capacity=4).danger_ok
    b = derive_taps(_cands(), (), capacity=4).danger_ok
    assert a == b


def test_derive_taps_negative_capacity_is_a_diagnostic():
    result = derive_taps(_cands(), (), capacity=-1)
    assert result.is_err
    assert result.danger_err.kind == "invalid_tap_capacity"


def test_derive_taps_zero_capacity_allocates_nothing():
    result = derive_taps(_cands(), (), capacity=0)
    assert result.is_ok
    tap_set = result.danger_ok
    assert tap_set.taps == ()
    assert len(tap_set.unallocated) == len(_cands())


def test_duplicate_explicit_tap_paths_deduplicate():
    explicit = (
        ExplicitTap(target_path="net.gpio1"),
        ExplicitTap(target_path="net.gpio1"),
    )
    result = derive_taps(_cands(), explicit, capacity=6)
    assert result.is_ok
    tap_set = result.danger_ok
    gpio1_taps = [t for t in tap_set.taps if t.target_path == "net.gpio1"]
    assert len(gpio1_taps) == 1
