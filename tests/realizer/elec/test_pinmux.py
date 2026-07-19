"""Pin-mux matcher: flow demands -> pins (WO-35 deliverable 2/3).

Spec: cuprite/04 sec. 1 step 2. The fixture is STM32G0-shaped
(`examples/registry/stm32g0.cupr` lqfp48 table, deliverable 1's typed
shape) since that record's functions are atomic (no `function_modes:`
join needed), matching the WO's "Kestrel-shaped fixture" acceptance
wording.
"""

from __future__ import annotations

from regolith.realizer.elec.pinmux import (
    AlternateFunctionTable,
    FlowDemand,
    FunctionInstance,
    PinOption,
    assign_pinmux,
)


def _stm32g0_lqfp48() -> AlternateFunctionTable:
    """A slice of `examples/registry/stm32g0.cupr`'s lqfp48 pin table."""
    return AlternateFunctionTable(
        package="lqfp48",
        pins=(
            PinOption(pin="pa2", functions=("uart2.tx", "tim15.ch1", "adc.in2")),
            PinOption(pin="pa3", functions=("uart2.rx", "tim15.ch2", "adc.in3")),
            PinOption(pin="pb6", functions=("twi1.scl", "uart1.tx", "tim16.ch1")),
            PinOption(pin="pb7", functions=("twi1.sda", "uart1.rx")),
        ),
        instances=(
            FunctionInstance(id="uart2.tx", kind="uart.tx"),
            FunctionInstance(id="uart2.rx", kind="uart.rx"),
            FunctionInstance(id="tim15.ch1", kind="pwm"),
            FunctionInstance(id="tim15.ch2", kind="pwm"),
            FunctionInstance(id="uart1.tx", kind="uart.tx"),
            FunctionInstance(id="uart1.rx", kind="uart.rx"),
            FunctionInstance(id="twi1.scl", kind="i2c.scl"),
            FunctionInstance(id="twi1.sda", kind="i2c.sda"),
            FunctionInstance(id="adc.in2", kind="adc"),
            FunctionInstance(id="adc.in3", kind="adc"),
            FunctionInstance(id="tim16.ch1", kind="pwm"),
        ),
    )


def _spi_contention_table() -> AlternateFunctionTable:
    """Two SPI instances; only one is DMA-capable (the contention fixture)."""
    return AlternateFunctionTable(
        package="lqfp48",
        pins=(
            PinOption(pin="pa5", functions=("spi1.sck",)),
            PinOption(pin="pb3", functions=("spi2.sck",)),
        ),
        instances=(
            FunctionInstance(
                id="spi1.sck", kind="spi.sck", capabilities=frozenset({"dma_capable"})
            ),
            FunctionInstance(id="spi2.sck", kind="spi.sck"),
        ),
    )


# frob:tests python/regolith/realizer/elec/pinmux.py::assign_pinmux kind="unit"
def test_happy_assignment_is_deterministic() -> None:
    """Every demand lands on a legal pin; rerunning is byte-identical."""
    table = _stm32g0_lqfp48()
    demands = [
        FlowDemand(flow="u_mcu.uart2.tx", kind="uart.tx"),
        FlowDemand(flow="u_mcu.uart2.rx", kind="uart.rx"),
    ]
    first = assign_pinmux(demands, table)
    second = assign_pinmux(demands, table)
    assert first.is_ok, first.danger_err
    assert first.danger_ok == second.danger_ok
    pinout = first.danger_ok.pinout()
    assert pinout["pa2"] == "uart2.tx"
    assert pinout["pa3"] == "uart2.rx"
    for assignment in first.danger_ok.assignments:
        assert assignment.cause == f"planner(pinmux {assignment.instance})"


def test_two_uart_tx_demands_backjump_to_second_instance() -> None:
    """Two `uart.tx` demands must land on the two distinct tx instances."""
    table = _stm32g0_lqfp48()
    demands = [
        FlowDemand(flow="u_mcu.uart2.tx", kind="uart.tx"),
        FlowDemand(flow="u_mcu.uart1.tx", kind="uart.tx"),
    ]
    result = assign_pinmux(demands, table)
    assert result.is_ok, result.danger_err
    pinout = result.danger_ok.pinout()
    assert set(pinout.values()) == {"uart2.tx", "uart1.tx"}
    assert set(pinout.keys()) == {"pa2", "pb6"}


def test_locked_pin_is_honored() -> None:
    """`locked: pinmux(u_mcu.uart2.tx): pa2` fixes the assignment."""
    table = _stm32g0_lqfp48()
    demands = [FlowDemand(flow="u_mcu.uart2.tx", kind="uart.tx", locked_pin="pa2")]
    result = assign_pinmux(demands, table)
    assert result.is_ok, result.danger_err
    assignment = result.danger_ok.assignments[0]
    assert assignment.pin == "pa2"
    assert assignment.instance == "uart2.tx"


def test_infeasible_lock_names_pin_and_demand() -> None:
    """A lock to a pin with no legal instance is a constructive error."""
    table = _stm32g0_lqfp48()
    demands = [FlowDemand(flow="u_mcu.uart2.tx", kind="uart.tx", locked_pin="pb7")]
    result = assign_pinmux(demands, table)
    assert result.is_err
    err = result.danger_err
    assert err.pin == "pb7"
    assert err.flow == "u_mcu.uart2.tx"


def test_dma_capable_spi_contention_names_both_flows() -> None:
    """Two flows demanding the single DMA-capable SPI fail with both named."""
    table = _spi_contention_table()
    demands = [
        FlowDemand(
            flow="u_mcu.spi_a",
            kind="spi.sck",
            required_capabilities=frozenset({"dma_capable"}),
        ),
        FlowDemand(
            flow="u_mcu.spi_b",
            kind="spi.sck",
            required_capabilities=frozenset({"dma_capable"}),
        ),
    ]
    result = assign_pinmux(demands, table)
    assert result.is_err
    err = result.danger_err
    assert set(err.flows) == {"u_mcu.spi_a", "u_mcu.spi_b"}
    assert "u_mcu.spi_a" in err.message
    assert "u_mcu.spi_b" in err.message


def test_no_assignment_appears_uncaused() -> None:
    """Every emitted assignment carries the planner(pinmux ...) cause (INV-21)."""
    table = _stm32g0_lqfp48()
    demands = [FlowDemand(flow="u_mcu.uart2.tx", kind="uart.tx")]
    result = assign_pinmux(demands, table)
    assert result.is_ok
    for assignment in result.danger_ok.assignments:
        assert assignment.cause.startswith("planner(pinmux ")
