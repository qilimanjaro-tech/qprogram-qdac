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
"""The QDAC operations, as AST nodes.

Each class is a concrete :class:`~qprogram.operations.Operation` subclass that a program holds in
its AST. They are typed attributes plus the capability tokens those attributes require.

QDAC is a slow high-precision DAC, most often used for flux biasing on transmon platforms. Its
waveform engine emits an envelope from a programmable sequencer with explicit dwell, delay,
repetition and stepping controls. These operations expose those controls, plus the trigger network
the engine listens to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from qprogram.operations.operation import Operation

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.variable import Expression
    from qprogram.waveforms.waveform import Waveform


TriggerPosition = Literal["start", "step", "end", "end_step"]
"""The four trigger-fire positions the QDAC sequencer recognizes.

- ``"start"``: the trigger fires when the sequence begins.
- ``"step"``: the trigger fires at the start of every step of a stepped sequence.
- ``"end"``: the trigger fires when the sequence finishes.
- ``"end_step"``: the trigger fires at the end of every step.
"""


def _normalize_outputs(value: Iterable[int] | str) -> tuple[int, ...]:
    """Return ``value`` as a sorted tuple of unique output indices.

    Accepts any iterable of integers (``set``, ``list``, ``tuple``, numpy array, ``range``,
    generator), and the comma-separated string a hand-written ``.qp`` file may carry
    (``outputs="1,2,3"``). Duplicates are dropped and the result is sorted, so two spellings of the
    same set of outputs hash and compare the same. Coercion is ``int()``, so a real-numbered element
    is truncated towards zero rather than rejected.

    Args:
        value (Iterable[int] | str): Output indices, or a comma-separated string of them.

    Returns:
        The indices as a sorted tuple, with duplicates removed.

    Raises:
        TypeError: If ``value`` is not iterable, or an element is of a type ``int()`` will not take.
        ValueError: If a comma-separated field is not a valid integer literal.
    """
    if isinstance(value, str):
        return tuple(sorted({int(p.strip()) for p in value.split(",") if p.strip()}))
    return tuple(sorted({int(x) for x in value}))


class WaitTrigger(Operation):
    """A halt on a QDAC channel until an external trigger arrives on one input port.

    This is how a QDAC sequence lines up with hardware on another instrument, a qblox sequencer's
    ``set_trigger`` for instance. The QDAC sequencer stops until the trigger fires, and emits no
    waveform while it waits.

    Args:
        bus (str): QDAC channel whose trigger input the sequencer listens on.
        port (int): Trigger input port number on the chassis, typically 1-based.
    """

    def __init__(self, bus: str, port: int) -> None:
        self.bus = bus
        self.port = port

    def required_capabilities(self) -> set[str]:
        """Return the single ``vendor.qdac.wait_trigger`` token."""
        return {"vendor.qdac.wait_trigger"}


class SetTrigger(Operation):
    """An arming of one or more QDAC trigger outputs at a chosen sequence position.

    The QDAC chassis carries an internal trigger bus with several output lines. This operation arms
    a subset of them to fire for ``duration`` nanoseconds at a sequence event: sequence start, every
    step, sequence end, or every step's end.

    Args:
        bus (str): QDAC channel whose trigger outputs are being configured.
        duration (int): Trigger-active duration in nanoseconds.
        position (TriggerPosition): Sequence event at which the triggers fire, one of ``"start"``,
            ``"step"``, ``"end"``, ``"end_step"``. Default ``"start"``.
        outputs (Iterable[int] | str): Trigger output indices to arm. Any iterable of ints, or a
            comma-separated string of them. Empty by default, which the
            ``qdac.empty-trigger-outputs`` predicate rejects at validation time.

    Attributes:
        outputs (tuple[int, ...]): The argument as stored, sorted and deduplicated on the way in, so
            ``{2, 1}`` and ``[1, 2, 1]`` produce equal operations.

    Raises:
        TypeError: If ``outputs`` is not iterable, or holds an element of a type ``int()`` will not
            take.
        ValueError: If ``outputs`` is a string whose comma-separated fields are not integers.
    """

    def __init__(
        self,
        bus: str,
        duration: int,
        position: TriggerPosition = "start",
        outputs: Iterable[int] | str = (),
    ) -> None:
        self.bus = bus
        self.duration = duration
        self.position: TriggerPosition = position
        self.outputs: tuple[int, ...] = _normalize_outputs(outputs)

    def required_capabilities(self) -> set[str]:
        """Return the single ``vendor.qdac.set_trigger`` token."""
        return {"vendor.qdac.set_trigger"}


class SetOffset(Operation):
    """A static DC offset on a QDAC channel.

    The channel holds ``offset`` volts until another operation changes it.

    Args:
        bus (str): QDAC channel whose DC offset is being set.
        offset (float | Expression): Target offset in volts. Accepts a literal or any
            :class:`~qprogram.Expression`, a loop-bound :class:`~qprogram.Variable` included. A
            swept offset is re-uploaded once per iteration, which is what the
            :mod:`qprogram_qdac.profiles` constraint on the enclosing loop expresses.
    """

    def __init__(self, bus: str, offset: float | Expression) -> None:
        self.bus = bus
        self.offset = offset

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qdac.set_offset`` plus the tokens contributed by the ``offset`` expression."""
        from qprogram.protocol import expression_tokens  # ruff: ignore[import-outside-top-level]

        return {"vendor.qdac.set_offset"} | expression_tokens(self.offset)


class Play(Operation):
    """An envelope emitted from a QDAC channel's waveform engine.

    The channel comes from ``bus``, so the operation routes to that bus's capability slot like every
    other QDAC operation. The rest of the arguments are the waveform-engine program: the envelope
    and its timing.

    Args:
        bus (str): QDAC channel that emits the waveform.
        waveform (Waveform): Single-channel :class:`~qprogram.waveforms.Waveform` whose envelope is
            uploaded to the waveform engine. A ``str`` alias is accepted here too, to be resolved
            later by :meth:`~qprogram.QProgram.with_waveforms`.
        dwell (int): Per-sample dwell time in nanoseconds, which sets the emission rate. Default
            ``1``.
        delay (int): Delay in nanoseconds between sequence start and the first sample. Default
            ``0``.
        repetitions (int): How many times the engine emits the envelope in total, the first
            emission included. Default ``1``.
        stepped (bool): ``True`` to step through the samples discretely, re-arming the DAC for each
            one, ``False`` for continuous interpolated output. Default ``False``.
    """

    WAVEFORM_ATTRS: ClassVar[tuple[str, ...]] = ("waveform",)

    def __init__(  # ruff: ignore[too-many-arguments]  bus, envelope and the engine's four timing controls
        self,
        bus: str,
        waveform: Waveform,
        dwell: int = 1,
        delay: int = 0,
        repetitions: int = 1,
        stepped: bool = False,
    ) -> None:
        self.bus = bus
        self.waveform = waveform
        self.dwell = dwell
        self.delay = delay
        self.repetitions = repetitions
        self.stepped = stepped

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qdac.play`` plus the tokens describing the waveform.

        ``waveform.single`` is always required, since the engine drives one channel. A registered
        waveform class contributes its per-class token from :func:`qprogram.protocol.waveform_token`
        on top, ``waveform.ramp`` for a :class:`~qprogram.waveforms.Ramp` for instance.
        """
        from qprogram.protocol import waveform_token  # ruff: ignore[import-outside-top-level]

        caps = {"vendor.qdac.play", "waveform.single"}
        tok = waveform_token(self.waveform)
        if tok is not None:
            caps.add(tok)
        return caps
