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
"""Tests for the qdac :class:`~qprogram.operations.Operation` subclasses.

The operations are the data nodes of the AST. What they owe their callers is the typed attributes
they store, the introspection methods the validator and the writer walk (``buses``, ``waveforms``,
``variables``), the capability tokens they require, and structural equality: two nodes built from
equivalent arguments must compare and hash the same.
"""

from __future__ import annotations

import numpy as np
import pytest
from qprogram import Variable
from qprogram.waveforms import IQDrag, Ramp, Square

from qprogram_qdac.operations import (
    Play,
    SetOffset,
    SetTrigger,
    WaitTrigger,
    _normalize_outputs,
)

# ---------------------------------------------------------------------------
# _normalize_outputs helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ((), ()),
        ([1, 2, 3], (1, 2, 3)),
        ({3, 1, 2}, (1, 2, 3)),
        ((2, 1, 2, 3, 1), (1, 2, 3)),
        (np.array([4, 2]), (2, 4)),
        ("", ()),
        ("1,2,3", (1, 2, 3)),
        ("3, 1, 2", (1, 2, 3)),
        (range(3), (0, 1, 2)),
    ],
)
def test_normalize_outputs(value, expected):
    """Any iterable of ints, or a comma-separated string, becomes a sorted tuple of unique ints."""
    assert _normalize_outputs(value) == expected


def test_normalize_outputs_rejects_non_int_string():
    with pytest.raises(ValueError):
        _normalize_outputs("not,an,int")


def test_normalize_outputs_rejects_a_non_int_element():
    """The other half of the documented ValueError: an element of an iterable, not a string field."""
    with pytest.raises(ValueError):
        _normalize_outputs([1, "x"])


# ---------------------------------------------------------------------------
# WaitTrigger
# ---------------------------------------------------------------------------


def test_wait_trigger_construct():
    op = WaitTrigger("flux_q0", port=3)
    assert op.bus == "flux_q0"
    assert op.port == 3


def test_wait_trigger_introspection():
    op = WaitTrigger("flux_q0", port=1)
    assert set(op.buses()) == {"flux_q0"}
    assert list(op.waveforms()) == []
    assert list(op.variables()) == []


def test_wait_trigger_required_capabilities():
    assert WaitTrigger("b", 1).required_capabilities() == {"vendor.qdac.wait_trigger"}


def test_wait_trigger_structural_equality():
    a = WaitTrigger("b", 1)
    b = WaitTrigger("b", 1)
    assert a == b
    assert hash(a) == hash(b)


def test_wait_trigger_distinct_when_different():
    assert WaitTrigger("b", 1) != WaitTrigger("b", 2)
    assert WaitTrigger("b", 1) != WaitTrigger("other", 1)


# ---------------------------------------------------------------------------
# SetTrigger
# ---------------------------------------------------------------------------


def test_set_trigger_defaults():
    op = SetTrigger("flux_q0", duration=50)
    assert op.bus == "flux_q0"
    assert op.duration == 50
    assert op.position == "start"
    assert op.outputs == ()


def test_set_trigger_with_set_outputs():
    op = SetTrigger("flux_q0", 50, outputs={3, 1, 2})
    assert op.outputs == (1, 2, 3)


def test_set_trigger_with_list_outputs():
    op = SetTrigger("flux_q0", 50, outputs=[2, 1])
    assert op.outputs == (1, 2)


def test_set_trigger_each_position():
    for pos in ("start", "step", "end", "end_step"):
        op = SetTrigger("flux_q0", 50, position=pos, outputs=[1])
        assert op.position == pos


def test_set_trigger_introspection():
    op = SetTrigger("flux_q0", 50, outputs=[1, 2])
    assert set(op.buses()) == {"flux_q0"}
    assert list(op.waveforms()) == []
    assert list(op.variables()) == []


def test_set_trigger_required_capabilities():
    assert SetTrigger("b", 50, outputs=[1]).required_capabilities() == {"vendor.qdac.set_trigger"}


def test_set_trigger_structural_equality_regardless_of_iterable_form():
    """``outputs`` normalizes on construction, so the iterable the caller used is not observable."""
    a = SetTrigger("b", 50, outputs={1, 2, 3})
    b = SetTrigger("b", 50, outputs=[1, 2, 3])
    c = SetTrigger("b", 50, outputs=(3, 1, 2))
    assert a == b == c
    assert hash(a) == hash(b) == hash(c)


def test_set_trigger_different_positions_not_equal():
    a = SetTrigger("b", 50, position="start", outputs=[1])
    b = SetTrigger("b", 50, position="end", outputs=[1])
    assert a != b


# ---------------------------------------------------------------------------
# SetOffset
# ---------------------------------------------------------------------------


def test_set_offset_float():
    op = SetOffset("flux_q0", 0.42)
    assert op.bus == "flux_q0"
    assert op.offset == pytest.approx(0.42)


def test_set_offset_with_variable():
    v = Variable("flux")
    op = SetOffset("flux_q0", v)
    assert op.offset is v
    assert list(op.variables()) == [v]


def test_set_offset_required_capabilities_constant():
    assert SetOffset("b", 0.5).required_capabilities() == {"vendor.qdac.set_offset"}


def test_set_offset_required_capabilities_variable():
    v = Variable("flux")
    caps = SetOffset("b", v).required_capabilities()
    assert "vendor.qdac.set_offset" in caps
    assert "expr.variable" in caps


def test_set_offset_required_capabilities_expression():
    """An expression argument contributes one token per node kind in its tree."""
    v = Variable("flux")
    caps = SetOffset("b", v * 2 + 0.1).required_capabilities()
    assert caps == {"vendor.qdac.set_offset", "expr.variable", "expr.binary_op", "expr.constant"}


def test_set_offset_introspection():
    op = SetOffset("flux_q0", 0.5)
    assert set(op.buses()) == {"flux_q0"}
    assert list(op.waveforms()) == []


# ---------------------------------------------------------------------------
# Play
# ---------------------------------------------------------------------------


def test_play_defaults():
    wf = Square(0.5, 100)
    op = Play("flux_q0", wf)
    assert op.bus == "flux_q0"
    assert op.waveform is wf
    assert op.dwell == 1
    assert op.delay == 0
    assert op.repetitions == 1
    assert op.stepped is False


def test_play_all_args():
    wf = Ramp(0.0, 1.0, 1000)
    op = Play("flux_q0", wf, dwell=10, delay=5, repetitions=3, stepped=True)
    assert op.bus == "flux_q0"
    assert op.dwell == 10
    assert op.delay == 5
    assert op.repetitions == 3
    assert op.stepped is True


def test_play_introspection():
    wf = Square(0.5, 100)
    op = Play("flux_q0", wf)
    assert set(op.buses()) == {"flux_q0"}
    assert list(op.waveforms()) == [wf]
    assert list(op.variables()) == []


def test_play_required_capabilities_includes_waveform_tokens():
    caps = Play("flux_q0", Ramp(0.0, 1.0, 100)).required_capabilities()
    assert "vendor.qdac.play" in caps
    assert "waveform.single" in caps
    assert "waveform.ramp" in caps


def test_play_required_capabilities_unregistered_waveform_class():
    """A waveform class with no registered token contributes only the single-channel kind token."""

    class _Fake(Square):
        pass

    caps = Play("flux_q0", _Fake(0.5, 100)).required_capabilities()
    assert caps == {"vendor.qdac.play", "waveform.single"}


def test_play_required_capabilities_with_a_waveform_name():
    """A ``str`` in the waveform position has no class token, so only the kind token is added.

    Nothing rejects the name here. Resolving it through a :class:`~qprogram.WaveformLibrary` is a
    step the caller owes the program before lowering.
    """
    caps = Play("flux_q0", "flux_ramp").required_capabilities()
    assert caps == {"vendor.qdac.play", "waveform.single"}


def test_play_required_capabilities_always_include_the_single_channel_token():
    """The engine drives one channel, so ``waveform.single`` is reported whatever the envelope is.

    An IQ envelope therefore reaches the node, and the token set alone does not prove the samples
    are real-valued. What stops the program is the per-class token missing from a single-channel
    profile.
    """
    caps = Play("flux_q0", IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1)).required_capabilities()
    assert caps == {"vendor.qdac.play", "waveform.single", "waveform.iq_drag"}


def test_play_structural_equality():
    wf = Square(0.5, 100)
    a = Play("flux_q0", wf, dwell=10, delay=0, repetitions=1, stepped=False)
    b = Play("flux_q0", wf, dwell=10, delay=0, repetitions=1, stepped=False)
    assert a == b
    assert hash(a) == hash(b)


def test_play_distinct_when_args_differ():
    wf = Square(0.5, 100)
    assert Play("flux_q0", wf, dwell=10) != Play("flux_q0", wf, dwell=20)
    assert Play("flux_q0", wf, stepped=True) != Play("flux_q0", wf, stepped=False)
    assert Play("flux_q0", wf) != Play("flux_q1", wf)
