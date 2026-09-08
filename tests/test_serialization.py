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
"""Tests for the ``.qp`` text form of the qdac operations.

The wire form of a vendor operation is ``qdac.<name> <args>``, emitted by the signature-driven
serializer and read back by the signature-driven parser. The tests pin the emitted text, the
``require qdac`` header line, the version-compatibility rules that header is checked against, and
byte stability: dumping a reloaded program must reproduce the file it came from.
"""

from __future__ import annotations

import pytest
from _header import HEADER, REQUIRE, VENDOR_MAJOR
from qprogram import ParseError, Variable, dumps, loads
from qprogram.sweeps import Range
from qprogram.waveforms import Ramp, Square

from qprogram_qdac import QProgram as QdacQProgram
from qprogram_qdac.operations import Play, SetOffset, SetTrigger, WaitTrigger

# ---------------------------------------------------------------------------
# Vendor require header
# ---------------------------------------------------------------------------


def test_dumps_includes_require_qdac():
    p = QdacQProgram()
    p.qdac.set_offset("flux_q0", 0.42)
    assert "require qdac" in dumps(p)


def test_dumps_no_require_when_no_qdac_ops():
    """The header lists the vendors a file actually uses, not the ones the builder could reach."""
    p = QdacQProgram()
    p.wait("flux_q0", 100)
    assert "require qdac" not in dumps(p)


# ---------------------------------------------------------------------------
# Per-operation round-trips
# ---------------------------------------------------------------------------


def test_wait_trigger_round_trip():
    p = QdacQProgram()
    p.qdac.wait_trigger("flux_q0", port=3)
    text = dumps(p)
    assert "qdac.wait_trigger" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, WaitTrigger)
    assert op.bus == "flux_q0"
    assert op.port == 3


def test_set_trigger_minimal_round_trip():
    """Arguments left at their default are omitted from the line and rebuilt by the parser."""
    p = QdacQProgram()
    p.qdac.set_trigger("flux_q0", duration=50)
    text = dumps(p)
    assert "qdac.set_trigger" in text
    assert "outputs" not in text
    assert "position" not in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetTrigger)
    assert op.outputs == ()
    assert op.position == "start"


def test_set_trigger_with_outputs_round_trip():
    """``outputs`` travels as a bracket literal, already sorted and deduplicated."""
    p = QdacQProgram()
    p.qdac.set_trigger("flux_q0", 50, outputs={3, 1, 2})
    text = dumps(p)
    assert "outputs=[1, 2, 3]" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert op.outputs == (1, 2, 3)


@pytest.mark.parametrize("position", ["step", "end", "end_step"])
def test_set_trigger_non_default_position_round_trip(position):
    p = QdacQProgram()
    p.qdac.set_trigger("flux_q0", 50, position=position, outputs=[1])
    text = dumps(p)
    assert f'position="{position}"' in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert op.position == position


def test_set_offset_float_round_trip():
    p = QdacQProgram()
    p.qdac.set_offset("flux_q0", 0.42)
    text = dumps(p)
    assert "qdac.set_offset" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetOffset)
    assert op.offset == pytest.approx(0.42)


def test_set_offset_with_variable_round_trip():
    """A variable is written as its identifier, so the reloaded node names the same variable."""
    p = QdacQProgram()
    v = p.variable("flux")
    p.qdac.set_offset("flux_q0", v)
    reloaded = loads(dumps(p))
    op = reloaded.body.elements[0]
    assert isinstance(op.offset, Variable)
    assert op.offset.id == v.id


def test_play_round_trip():
    p = QdacQProgram()
    p.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=10, delay=5, repetitions=2, stepped=True)
    text = dumps(p)
    assert "qdac.play" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, Play)
    assert op.bus == "flux_q0"
    assert op.dwell == 10
    assert op.delay == 5
    assert op.repetitions == 2
    assert op.stepped is True


def test_play_default_args_round_trip():
    p = QdacQProgram()
    p.qdac.play("flux_q0", Square(0.5, 100))
    text = dumps(p)
    for kwarg in ("dwell", "delay", "repetitions", "stepped"):
        assert kwarg not in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, Play)
    assert op.bus == "flux_q0"
    assert op.dwell == 1
    assert op.delay == 0
    assert op.repetitions == 1
    assert op.stepped is False


# ---------------------------------------------------------------------------
# Reading a hand-written file
# ---------------------------------------------------------------------------


def test_loads_hand_written_file():
    """The documented wire form parses, and the writer reproduces it byte for byte."""
    text = (
        f"{HEADER}\n"
        "\n"
        f"{REQUIRE}\n"
        "\n"
        "body:\n"
        '  qdac.set_offset "flux_q0" 0.42\n'
        '  qdac.set_trigger "flux_q0" 20 position="step" outputs=[1, 2]\n'
        '  qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=100) dwell=10 stepped=true\n'
        '  qdac.wait_trigger "flux_q0" 3\n'
    )
    p = loads(text)
    offset, trigger, play, wait_trigger = p.body.elements
    assert offset.offset == pytest.approx(0.42)
    assert (trigger.duration, trigger.position, trigger.outputs) == (20, "step", (1, 2))
    assert (play.dwell, play.stepped) == (10, True)
    assert wait_trigger.port == 3
    assert dumps(p) == text


# ---------------------------------------------------------------------------
# Combined with core ops
# ---------------------------------------------------------------------------


def test_round_trip_qdac_and_core_ops(flux_tunable_schema):
    p = QdacQProgram(schema=flux_tunable_schema)
    p.qdac.set_offset(flux_tunable_schema.q[0].flux, 0.5)
    p.wait(flux_tunable_schema.q[0].flux, 100)
    p.qdac.play(flux_tunable_schema.q[0].flux, Ramp(0.0, 1.0, 1000), dwell=10)
    text = dumps(p)
    assert dumps(loads(text)) == text


# ---------------------------------------------------------------------------
# Vendor compatibility check
# ---------------------------------------------------------------------------


def test_loads_with_matching_qdac_require_ok():
    p = QdacQProgram()
    p.qdac.set_offset("flux_q0", 0.42)
    assert loads(dumps(p)).body.elements


def test_loads_with_older_minor_accepted():
    """A file written against the extension's first minor still loads."""
    text = f'{HEADER}\nrequire qdac {VENDOR_MAJOR}.0\nbody:\n  qdac.set_offset "flux" 0.5\n'
    assert loads(text).body.elements


def test_loads_with_future_minor_rejected():
    """The installed extension cannot promise a minor it does not have."""
    text = f'{HEADER}\nrequire qdac {VENDOR_MAJOR}.99\nbody:\n  qdac.set_offset "flux" 0.5\n'
    with pytest.raises(ParseError, match="minor version too old"):
        loads(text)


def test_loads_with_wrong_major_rejected():
    text = f'{HEADER}\nrequire qdac 999.0\nbody:\n  qdac.set_offset "flux" 0.5\n'
    with pytest.raises(ParseError, match="major versions must match"):
        loads(text)


# ---------------------------------------------------------------------------
# Byte stability across a feature-rich program
# ---------------------------------------------------------------------------


def test_full_features_round_trip(flux_tunable_schema):
    p = QdacQProgram(label="big-qdac", schema=flux_tunable_schema)
    v = p.variable("scale")
    with p.average(100), p.sweep(v, Range(0.0, 1.0, 0.1)):
        p.qdac.set_offset(flux_tunable_schema.q[0].flux, v)
        p.qdac.set_trigger(
            flux_tunable_schema.q[0].flux,
            duration=20,
            position="step",
            outputs={1, 2},
        )
        p.qdac.play(flux_tunable_schema.q[0].flux, Ramp(0.0, 1.0, 500), dwell=10, stepped=True)
        p.qdac.wait_trigger(flux_tunable_schema.q[0].flux, port=1)

    text = dumps(p)
    reloaded = loads(text)
    assert dumps(reloaded) == text
    assert reloaded.body == p.body
