# Copyright 2026 Qilimanjaro Quantum Tech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the ``qdac-default-v1`` capability profile.

This is the package's integration story: every qdac operation validates against a
:class:`~qprogram.PlatformCapabilities` built from the profile, single-channel waveforms are
accepted and IQ ones are not, each predicate fires on the case it is written for, and the
classifier lands qdac operations and their enclosing sweeps in the host domain. The last two
sections exercise the surfaces that consume the plan: :func:`~qprogram.explain` and the reference
executor behind :func:`~qprogram.simulate`.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import numpy as np
import pytest
from _header import HEADER, REQUIRE
from qprogram import Variable, explain, loads, simulate
from qprogram.protocol import (
    BusCapabilities,
    CompilerCapabilities,
    Diagnostic,
    PlatformCapabilities,
    resolve_profile,
)
from qprogram.sweeps import Range, Values
from qprogram.validation import validate
from qprogram.waveforms import IQDrag, Ramp, Square

from qprogram_qdac import QProgram
from qprogram_qdac.profiles import QDAC_DEFAULT_V1

if TYPE_CHECKING:
    from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_caps(*, rt: bool = False, extra_bus_tokens: Iterable[str] = ()) -> PlatformCapabilities:
    """Build a platform with ``qdac-default-v1`` on the bus slot and ``qprogram-base-v1`` above it.

    QDAC has no FPGA, so a correctly wired platform fills only the ``host`` half of a qdac bus slot.
    ``rt=True`` fills both halves, which is the mis-wiring the ``DomainConstraint`` predicate guards
    against. ``extra_bus_tokens`` widens the bus slot so a non-qdac operation can route to it.
    """
    bus_cc = CompilerCapabilities.from_profile("qdac-default-v1")
    if extra_bus_tokens:
        bus_cc = dataclasses.replace(bus_cc, capabilities=bus_cc.capabilities | frozenset(extra_bus_tokens))
    platform_cc = CompilerCapabilities.from_profile("qprogram-base-v1")
    return PlatformCapabilities(
        bus={},
        platform=BusCapabilities(rt=platform_cc, host=platform_cc),
        default_bus_profile=BusCapabilities(rt=bus_cc if rt else None, host=bus_cc),
    )


def _diagnostics(p: QProgram, caps: PlatformCapabilities) -> list[Diagnostic]:
    """Return only the diagnostics of a validation run, dropping the plan."""
    diagnostics, _ = validate(p, caps)
    return diagnostics


def _node(p: QProgram, class_name: str) -> object:
    """Return the first node of the named class in the program body."""
    return next(n for n in p.body.walk() if type(n).__name__ == class_name)


# ---------------------------------------------------------------------------
# Profile registration
# ---------------------------------------------------------------------------


def test_qdac_default_profile_is_registered():
    assert resolve_profile("qdac-default-v1") is QDAC_DEFAULT_V1


def test_qdac_default_profile_carries_every_qdac_token():
    caps = CompilerCapabilities.from_profile("qdac-default-v1")
    assert caps.profile == "qdac-default-v1"
    assert caps.version == (0, 2, 0)
    for token in (
        "vendor.qdac.wait_trigger",
        "vendor.qdac.set_trigger",
        "vendor.qdac.set_offset",
        "vendor.qdac.play",
        "waveform.ramp",
        "waveform.square",
        "waveform.single",
    ):
        assert token in caps.capabilities, token


def test_qdac_default_profile_holds_no_platform_tokens():
    """Block, expression and sweep tokens belong to the platform slot, so the bus profile omits them."""
    caps = CompilerCapabilities.from_profile("qdac-default-v1")
    for token in ("block.sweep", "expr.constant", "sweep.linear"):
        assert token not in caps.capabilities, token


def test_qdac_default_profile_holds_no_iq_waveform_tokens():
    """QDAC is single-channel, so the profile advertises no IQ waveform."""
    caps = CompilerCapabilities.from_profile("qdac-default-v1")
    assert not any(token.startswith("waveform.iq") for token in caps.capabilities)


def test_qdac_default_profile_publishes_no_limits():
    """The dwell floor is enforced by a predicate and not published as a limit.

    A predicate cannot read the slot's limits, so a published floor could be overridden without the
    check following it. Publishing nothing keeps what the profile says and what it enforces the same.
    """
    assert QDAC_DEFAULT_V1.limits == {}


def test_qdac_default_vendor_versions_record_qdac():
    caps = CompilerCapabilities.from_profile("qdac-default-v1")
    assert "qdac" in caps.vendor_versions


# ---------------------------------------------------------------------------
# Happy path: every supported construct validates clean
# ---------------------------------------------------------------------------


def test_program_with_every_supported_construct_validates_clean():
    caps = _make_caps()
    p = QProgram()
    p.qdac.set_offset("flux_q0", 0.42)
    p.qdac.set_trigger("flux_q0", 10e-6, position="start", outputs={1, 2, 3})
    p.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=10)
    p.qdac.wait_trigger("flux_q0", port=2)
    assert _diagnostics(p, caps) == []


def test_play_uses_bus_waveforms():
    """Play is bus-touching, so its waveform token is checked against the routed bus slot."""
    caps = _make_caps()
    p = QProgram()
    p.qdac.play("flux_q0", Square(0.5, 100))
    assert _diagnostics(p, caps) == []


def test_expression_tokens_are_checked_against_the_platform_slot():
    """``expr.*`` tokens route to the platform slot even when the operation carrying them is bus-touching.

    The qdac bus profile advertises no ``expr.*`` token, so an arithmetic offset validating clean is
    what proves the routing.
    """
    caps = _make_caps()
    p = QProgram()
    v = p.variable("scale")
    p.qdac.set_offset("flux_q0", v * 2 + 0.1)
    assert _diagnostics(p, caps) == []


# ---------------------------------------------------------------------------
# Unsupported waveforms
# ---------------------------------------------------------------------------


def test_iq_waveform_is_rejected_on_a_qdac_bus():
    """An IQ envelope has no token on the single-channel qdac profile, so it fails validation."""
    caps = _make_caps()
    p = QProgram()
    p.qdac.play("flux_q0", IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1))
    diagnostics = _diagnostics(p, caps)
    assert [d.code for d in diagnostics] == ["missing-capability"]
    assert "waveform.iq_drag" in diagnostics[0].message


# ---------------------------------------------------------------------------
# Predicate: empty trigger outputs
# ---------------------------------------------------------------------------


def test_empty_trigger_outputs_is_rejected():
    caps = _make_caps()
    p = QProgram()
    p.qdac.set_trigger("flux_q0", 10e-6, outputs=())
    codes = {d.code for d in _diagnostics(p, caps)}
    assert "qdac.empty-trigger-outputs" in codes


def test_non_empty_trigger_outputs_validates_clean():
    caps = _make_caps()
    p = QProgram()
    p.qdac.set_trigger("flux_q0", 10e-6, outputs={1})
    assert _diagnostics(p, caps) == []


# ---------------------------------------------------------------------------
# Predicate: dwell floor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dwell", [1, 0, np.int64(1)], ids=["int", "zero", "numpy-int"])
def test_dwell_below_the_floor_is_rejected(dwell):
    """A numpy integer is checked like a Python one, so a dwell taken from an array cannot slip past."""
    caps = _make_caps()
    p = QProgram()
    p.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=dwell)
    diagnostics = _diagnostics(p, caps)
    assert [(d.severity, d.code) for d in diagnostics] == [("error", "qdac.dwell-below-minimum")]
    assert diagnostics[0].node is _node(p, "Play")
    assert diagnostics[0].limit is None
    assert diagnostics[0].message == (
        f"qdac.play dwell={dwell} is below the QDAC-II minimum of 2; dwell is in microseconds"
    )


@pytest.mark.parametrize("kwargs", [{}, {"dwell": 2}, {"dwell": 1000}], ids=["default", "at-floor", "above"])
def test_dwell_at_or_above_the_floor_validates_clean(kwargs):
    """The default dwell is the floor itself, so a ``play`` that leaves it out is valid."""
    caps = _make_caps()
    p = QProgram()
    p.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), **kwargs)
    assert _diagnostics(p, caps) == []


def test_dwell_that_is_not_a_number_is_left_to_the_platform():
    """``dwell`` is typed ``int``, but a hand-written ``.qp`` file can still bind it to a loop variable.

    The check compares numbers only, so it leaves that dwell alone rather than failing on an
    expression it cannot evaluate. The sweep is still lifted host-side, which is the other
    predicate's job.
    """
    text = (
        f"{HEADER}\n"
        "\n"
        f"{REQUIRE}\n"
        "\n"
        "body:\n"
        "  var d\n"
        "\n"
        "  for d in Range(start=2, stop=10, step=2):\n"
        '    qdac.play "flux_q0" "flux_ramp" dwell=d\n'
    )
    p = loads(text)
    assert isinstance(_node(p, "Play").dwell, Variable)
    assert [d.code for d in _diagnostics(p, _make_caps(rt=True))] == ["forced-host"]


# ---------------------------------------------------------------------------
# Operation classification: qdac operations are host-side by design
# ---------------------------------------------------------------------------


def test_qdac_set_offset_is_host_only():
    """qdac fills the host half of the bus slot only, so its operations classify as ``{host}``."""
    caps = _make_caps()
    p = QProgram()
    p.qdac.set_offset("flux_q0", 0.42)
    _, plan = validate(p, caps)
    assert plan[_node(p, "SetOffset")] == frozenset({"host"})


def test_qdac_play_is_host_only():
    caps = _make_caps()
    p = QProgram()
    p.qdac.play("flux_q0", Square(0.5, 100), dwell=10)
    _, plan = validate(p, caps)
    assert plan[_node(p, "Play")] == frozenset({"host"})


# ---------------------------------------------------------------------------
# Sweep classification: op-children consensus
# ---------------------------------------------------------------------------


def test_sweep_with_qdac_op_classifies_as_host():
    """A sweep whose only op-child is host-side is host-side too, from consensus alone."""
    caps = _make_caps()
    p = QProgram()
    v = p.variable("flux")
    with p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.set_offset("flux_q0", v)
    _, plan = validate(p, caps)
    assert plan[_node(p, "Sweep")] == frozenset({"host"})


def test_sweep_with_unswept_qdac_op_also_classifies_as_host():
    """The qdac operation reads no swept variable and the sweep is still host-side."""
    caps = _make_caps()
    p = QProgram()
    v = p.variable("dummy")
    with p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.play("flux_q0", Square(0.5, 100), dwell=10)
    diagnostics, plan = validate(p, caps)
    assert [d for d in diagnostics if d.severity == "error"] == []
    assert plan[_node(p, "Sweep")] == frozenset({"host"})


def test_sweep_over_an_arbitrary_source_classifies_as_host():
    """The sweep source kind does not enter the domain consensus."""
    caps = _make_caps()
    p = QProgram()
    v = p.variable("flux")
    with p.sweep(v, Values(np.array([0.0, 0.25, 0.5, 0.75]))):
        p.qdac.set_offset("flux_q0", v)
    _, plan = validate(p, caps)
    assert plan[_node(p, "Sweep")] == frozenset({"host"})


def test_no_forced_host_diagnostic_when_consensus_alone_picks_host():
    """``forced-host`` reports a domain a block lost, not one it never had.

    With qdac wired to the host half only, the sweep's available domain set is ``{host}`` from the
    start, so no constraint applies and nothing is reported.
    """
    caps = _make_caps()
    p = QProgram()
    v = p.variable("flux")
    with p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.set_offset("flux_q0", v)
    assert not any(d.code == "forced-host" for d in _diagnostics(p, caps))


# ---------------------------------------------------------------------------
# Predicate: a swept qdac operation lifts its binding sweep to host-side
# ---------------------------------------------------------------------------


def test_swept_offset_forces_the_binding_sweep_host_side():
    """On a bus slot with both halves filled, the constraint is what strips ``rt`` from the sweep.

    The constraint targets the binding sweep, so the operation itself keeps both domains.
    """
    caps = _make_caps(rt=True)
    p = QProgram()
    v = p.variable("flux")
    with p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.set_offset("flux_q0", v)
    diagnostics, plan = validate(p, caps)
    sweep = _node(p, "Sweep")
    assert [(d.severity, d.code, d.node is sweep) for d in diagnostics] == [("warning", "forced-host", True)]
    assert "no FPGA" in diagnostics[0].message
    assert plan[sweep] == frozenset({"host"})
    assert plan[_node(p, "SetOffset")] == frozenset({"host", "rt"})


def test_swept_waveform_parameter_forces_the_binding_sweep_host_side():
    """The predicate reads the variables of the whole operation, waveform parameters included."""
    caps = _make_caps(rt=True)
    p = QProgram()
    v = p.variable("amp")
    with p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.play("flux_q0", Square(v, 100), dwell=10)
    diagnostics, plan = validate(p, caps)
    assert [d.code for d in diagnostics] == ["forced-host"]
    assert "qdac.Play" in diagnostics[0].message
    assert plan[_node(p, "Sweep")] == frozenset({"host"})


def test_variable_with_no_binding_sweep_yields_no_constraint():
    """A variable no sweep binds cannot cost the sweep its real-time domain."""
    caps = _make_caps(rt=True)
    p = QProgram()
    swept = p.variable("swept")
    unbound = p.variable("unbound")
    with p.sweep(swept, Range(0.0, 1.0, 0.1)):
        p.qdac.set_offset("flux_q0", unbound)
    diagnostics, plan = validate(p, caps)
    assert diagnostics == []
    assert plan[_node(p, "Sweep")] == frozenset({"host", "rt"})


def test_predicate_ignores_non_qdac_operations():
    """The predicate is offered every node routed to the qdac bus slot, and constrains only qdac ones."""
    caps = _make_caps(rt=True, extra_bus_tokens=["op.wait"])
    p = QProgram()
    v = p.variable("t")
    with p.sweep(v, Range(100.0, 200.0, 10.0)):
        p.wait("flux_q0", v)
    diagnostics, plan = validate(p, caps)
    assert diagnostics == []
    assert plan[_node(p, "Sweep")] == frozenset({"host", "rt"})


# ---------------------------------------------------------------------------
# Plan rendering
# ---------------------------------------------------------------------------


def test_explain_renders_qdac_operations():
    """``explain`` writes each node as its ``.qp`` line and appends the domain the plan assigns."""
    caps = _make_caps()
    p = QProgram(label="flux-sweep")
    v = p.variable("flux")
    with p.sweep(v, Range(0.0, 1.0, 0.5)):
        p.qdac.set_offset("flux_q0", v)
        p.qdac.play("flux_q0", Ramp(0.0, 1.0, 100), dwell=10)
    out = explain(p, caps)
    assert 'qdac.set_offset "flux_q0" flux' in out
    assert "qdac.play" in out
    assert "[rt|host]" not in out
    assert out.count("[host]") == 3


# ---------------------------------------------------------------------------
# Reference platform
# ---------------------------------------------------------------------------


def test_simulate_executes_qdac_operations():
    """The reference executor treats vendor operations generically, so a qdac program runs on it."""
    p = QProgram()
    v = p.variable("flux")
    with p.sweep(v, Range(0.0, 1.0, 0.25)):
        p.qdac.set_offset("flux_q0", v)
        p.measure("readout_q0", Square(0.5, 100), "weights", name="m0")
    result = simulate(p)
    data = result.get("m0")
    assert data.dims == ("flux", "IQ")
    assert data.shape == (5, 2)
