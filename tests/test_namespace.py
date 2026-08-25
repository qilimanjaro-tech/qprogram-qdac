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
"""Tests for :class:`~qprogram_qdac.namespace.QdacNamespace`.

Every namespace method appends one typed operation to the program's active block. The tests pin the
appended node type, the arguments that reach it, and the namespace's identity: one instance per
program, cached across accesses.
"""

from __future__ import annotations

import pytest
from qprogram import ValidationError, Variable
from qprogram.buses import BusRef
from qprogram.sweeps import Range
from qprogram.vendor import VendorNamespace
from qprogram.waveforms import Ramp, Square

from qprogram_qdac import QProgram as QdacQProgram
from qprogram_qdac.namespace import QdacNamespace
from qprogram_qdac.operations import Play, SetOffset, SetTrigger, WaitTrigger

# ---------------------------------------------------------------------------
# wait_trigger
# ---------------------------------------------------------------------------


def test_wait_trigger_appends_op(qdac_program):
    qdac_program.qdac.wait_trigger("flux_q0", port=3)
    op = qdac_program.body.elements[0]
    assert isinstance(op, WaitTrigger)
    assert op.bus == "flux_q0"
    assert op.port == 3


def test_wait_trigger_returns_none(qdac_program):
    assert qdac_program.qdac.wait_trigger("flux_q0", port=1) is None


# ---------------------------------------------------------------------------
# set_trigger
# ---------------------------------------------------------------------------


def test_set_trigger_defaults(qdac_program):
    qdac_program.qdac.set_trigger("flux_q0", duration=50)
    op = qdac_program.body.elements[0]
    assert isinstance(op, SetTrigger)
    assert op.duration == 50
    assert op.position == "start"
    assert op.outputs == ()


def test_set_trigger_with_set_outputs(qdac_program):
    qdac_program.qdac.set_trigger("flux_q0", 50, outputs={3, 1, 2})
    op = qdac_program.body.elements[0]
    assert op.outputs == (1, 2, 3)


def test_set_trigger_with_list_outputs(qdac_program):
    qdac_program.qdac.set_trigger("flux_q0", 50, outputs=[1, 2])
    op = qdac_program.body.elements[0]
    assert op.outputs == (1, 2)


def test_set_trigger_with_generator_outputs(qdac_program):
    """A one-shot iterable is consumed on construction, so the stored tuple is complete."""
    qdac_program.qdac.set_trigger("flux_q0", 50, outputs=(i for i in (3, 1, 2)))
    op = qdac_program.body.elements[0]
    assert op.outputs == (1, 2, 3)


def test_set_trigger_with_position_end_step(qdac_program):
    qdac_program.qdac.set_trigger("flux_q0", 50, position="end_step", outputs=[1])
    op = qdac_program.body.elements[0]
    assert op.position == "end_step"


# ---------------------------------------------------------------------------
# set_offset
# ---------------------------------------------------------------------------


def test_set_offset_with_float(qdac_program):
    qdac_program.qdac.set_offset("flux_q0", 0.42)
    op = qdac_program.body.elements[0]
    assert isinstance(op, SetOffset)
    assert op.offset == pytest.approx(0.42)


def test_set_offset_with_variable(qdac_program):
    v = Variable("flux")
    qdac_program.qdac.set_offset("flux_q0", v)
    op = qdac_program.body.elements[0]
    assert op.offset is v


def test_set_offset_accepts_arithmetic_expression(qdac_program):
    """Arithmetic on a Variable reaches the node as an expression tree that still names it."""
    v = qdac_program.variable("scale")
    qdac_program.qdac.set_offset("flux_q0", v * 2 + 0.1)
    op = qdac_program.body.elements[0]
    assert v in op.variables()


def test_set_offset_keeps_a_schema_bus_ref(qdac_program, flux_tunable_schema):
    """A :class:`~qprogram.BusRef` passed to a qdac op stays a BusRef, coordinates and all."""
    qdac_program.qdac.set_offset(flux_tunable_schema.q[0].flux, 0.5)
    op = qdac_program.body.elements[0]
    assert isinstance(op.bus, BusRef)
    assert (op.bus.element, op.bus.idx, op.bus.kind) == ("q", 0, "flux")


# ---------------------------------------------------------------------------
# play
# ---------------------------------------------------------------------------


def test_play_appends_op_default_kwargs(qdac_program):
    wf = Ramp(0.0, 1.0, 1000)
    qdac_program.qdac.play("flux_q0", wf)
    op = qdac_program.body.elements[0]
    assert isinstance(op, Play)
    assert op.bus == "flux_q0"
    assert op.waveform is wf
    assert op.dwell == 1
    assert op.delay == 0
    assert op.repetitions == 1
    assert op.stepped is False


def test_play_with_all_kwargs(qdac_program):
    wf = Square(0.5, 100)
    qdac_program.qdac.play("flux_q0", wf, dwell=10, delay=5, repetitions=3, stepped=True)
    op = qdac_program.body.elements[0]
    assert op.bus == "flux_q0"
    assert op.dwell == 10
    assert op.delay == 5
    assert op.repetitions == 3
    assert op.stepped is True


def test_play_returns_none(qdac_program):
    assert qdac_program.qdac.play("flux_q0", Ramp(0.0, 1.0, 100)) is None


# ---------------------------------------------------------------------------
# Bus validation
# ---------------------------------------------------------------------------

# One entry per namespace method, each given the namespace and the bus to hand it. Every method
# routes its bus through ``VendorNamespace._append``, so the whole surface is covered here rather
# than one method at a time.
_BUS_CALLS = [
    pytest.param(lambda ns, bus: ns.wait_trigger(bus, port=1), id="wait_trigger"),
    pytest.param(lambda ns, bus: ns.set_trigger(bus, 50, outputs=[1]), id="set_trigger"),
    pytest.param(lambda ns, bus: ns.set_offset(bus, 0.5), id="set_offset"),
    pytest.param(lambda ns, bus: ns.play(bus, Ramp(0.0, 1.0, 100)), id="play"),
]


@pytest.mark.parametrize("call", _BUS_CALLS)
def test_bus_ref_from_a_foreign_schema_is_rejected(qdac_program, foreign_schema, call):
    """A ref carrying the wrong schema is refused before the operation reaches the block.

    The two schemas are the same preset, so the ref's path is one the program's own schema would
    also produce. Only the recorded producer separates them.
    """
    with pytest.raises(ValidationError, match="different BusSchema"):
        call(qdac_program.qdac, foreign_schema.q[0].flux)
    assert qdac_program.body.elements == []


@pytest.mark.parametrize("call", _BUS_CALLS)
def test_bus_ref_from_the_program_schema_is_accepted(qdac_program, flux_tunable_schema, call):
    """The same call with the program's own schema appends, which is what isolates the schema check."""
    call(qdac_program.qdac, flux_tunable_schema.q[0].flux)
    assert len(qdac_program.body.elements) == 1


def test_plain_string_bus_opts_out_of_the_schema_check(qdac_program):
    """Only a BusRef is checked, so a raw string spelling the same path is taken as written."""
    qdac_program.qdac.set_offset("q0/flux", 0.5)
    op = qdac_program.body.elements[0]
    assert not isinstance(op.bus, BusRef)
    assert op.bus == "q0/flux"


# ---------------------------------------------------------------------------
# Namespace identity
# ---------------------------------------------------------------------------


def test_namespace_is_subclass_of_vendor_namespace():
    assert issubclass(QdacNamespace, VendorNamespace)


def test_namespace_holds_program_reference(qdac_program):
    ns = qdac_program.qdac
    assert ns._program is qdac_program


def test_namespace_cached_per_instance(qdac_program):
    assert qdac_program.qdac is qdac_program.qdac


def test_namespace_distinct_per_program():
    p1 = QdacQProgram()
    p2 = QdacQProgram()
    assert p1.qdac is not p2.qdac


# ---------------------------------------------------------------------------
# Integration with control flow
# ---------------------------------------------------------------------------


def test_qdac_ops_inside_sweep(qdac_program):
    """Ops append to whichever block is active, so both land inside the sweep."""
    v = qdac_program.variable("scale")
    with qdac_program.sweep(v, Range(0.0, 1.0, 0.1)):
        qdac_program.qdac.set_offset("flux_q0", v)
        qdac_program.qdac.play("flux_q0", Ramp(0.0, 1.0, 100), dwell=10)
    sweep = qdac_program.body.elements[0]
    assert len(sweep.elements) == 2
    assert isinstance(sweep.elements[0], SetOffset)
    assert isinstance(sweep.elements[1], Play)
