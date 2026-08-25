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
"""The typed :class:`~qprogram.VendorNamespace` for QDAC operations.

Every method on :class:`QdacNamespace` constructs one
:class:`~qprogram.operations.Operation` subclass and appends it to the program's active block.
The typed signatures are the discoverable surface: the dynamic ``__getattr__`` on
:class:`~qprogram.QProgram` dispatches the same calls, but says nothing about their arguments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram.vendor import VendorNamespace

from qprogram_qdac.operations import (
    Play,
    SetOffset,
    SetTrigger,
    TriggerPosition,
    WaitTrigger,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.variable import Expression
    from qprogram.waveforms.waveform import Waveform


class QdacNamespace(VendorNamespace):
    """The QDAC vendor namespace, reached as ``program.qdac.<operation>()``.

    Available on every :class:`~qprogram.QProgram` instance once :mod:`qprogram_qdac` is imported.
    Each method type-checks its arguments through the signature, builds the matching operation, and
    appends it to whichever block the program has open.
    """

    def wait_trigger(self, bus: str, port: int) -> None:
        """Append a :class:`~qprogram_qdac.operations.WaitTrigger` operation.

        Args:
            bus (str): QDAC channel whose trigger input the sequencer listens on.
            port (int): Trigger input port number on the chassis.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(WaitTrigger(bus=bus, port=port))

    def set_trigger(
        self,
        bus: str,
        duration: int,
        position: TriggerPosition = "start",
        outputs: Iterable[int] = (),
    ) -> None:
        """Append a :class:`~qprogram_qdac.operations.SetTrigger` operation.

        Args:
            bus (str): QDAC channel whose trigger outputs are being configured.
            duration (int): Trigger-active duration in nanoseconds.
            position (TriggerPosition): Sequence event at which the triggers fire, one of
                ``"start"``, ``"step"``, ``"end"``, ``"end_step"``. Default ``"start"``.
            outputs (Iterable[int]): Trigger output indices to arm. Any iterable of ints will do:
                ``set``, ``list``, ``tuple``, generator. Empty by default, which the
                ``qdac.empty-trigger-outputs`` predicate rejects at validation time.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetTrigger(bus=bus, duration=duration, position=position, outputs=outputs))

    def set_offset(self, bus: str, offset: float | Expression) -> None:
        """Append a :class:`~qprogram_qdac.operations.SetOffset` operation.

        Args:
            bus (str): QDAC channel whose DC offset is being set.
            offset (float | Expression): Target offset in volts. Accepts a literal or any
                :class:`~qprogram.Expression`, a loop-bound :class:`~qprogram.Variable` included.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetOffset(bus=bus, offset=offset))

    def play(  # ruff: ignore[too-many-arguments]  bus, envelope and the engine's four timing controls
        self,
        bus: str,
        waveform: Waveform,
        dwell: int = 1,
        delay: int = 0,
        repetitions: int = 1,
        stepped: bool = False,
    ) -> None:
        """Append a :class:`~qprogram_qdac.operations.Play` operation.

        Args:
            bus (str): QDAC channel that emits the waveform.
            waveform (Waveform): Single-channel :class:`~qprogram.waveforms.Waveform` to emit. A
                ``str`` alias is accepted here too, to be resolved later by
                :meth:`~qprogram.QProgram.with_waveforms`.
            dwell (int): Per-sample dwell time in nanoseconds. Default ``1``.
            delay (int): Delay before the first sample, in nanoseconds. Default ``0``.
            repetitions (int): How many times the envelope is emitted. Default ``1``.
            stepped (bool): ``True`` for discrete-step output, ``False`` for continuous
                interpolated output. Default ``False``.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(
            Play(
                bus=bus,
                waveform=waveform,
                dwell=dwell,
                delay=delay,
                repetitions=repetitions,
                stepped=stepped,
            ),
        )
