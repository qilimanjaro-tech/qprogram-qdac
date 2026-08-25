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
"""QDAC vendor extensions for QProgram.

This package provides three things:

1. **Runtime registration.** Importing the package is the activation step. It registers the ``qdac``
   vendor namespace on :class:`~qprogram.QProgram`, every QDAC operation with the ``.qp``
   serializer, and the ``qdac-default-v1`` capability profile.
2. **Typed mixin.** :class:`QdacMixin` declares a typed ``.qdac`` property for editor autocomplete.
3. **Pre-combined builder.** :class:`QProgram` here is :class:`qprogram.QProgram` with that mixin
   already applied.

A ``.qp`` file whose header says ``require qdac 0.1`` activates the package on load even when the
caller never imported it. :func:`qprogram.loads` looks the vendor up in the ``qprogram.vendors``
entry-point group declared in ``pyproject.toml`` and imports this module for its side effects.

QDAC is a slow high-precision DAC, most often used for flux biasing on transmon platforms. The
operations it contributes are:

- :meth:`QdacNamespace.play`, which uploads an envelope to one channel's waveform engine;
- :meth:`QdacNamespace.set_trigger` and :meth:`QdacNamespace.wait_trigger`, the trigger-network
  plumbing that lines a QDAC sequence up with another instrument;
- :meth:`QdacNamespace.set_offset`, a DC offset whose swept form lifts the enclosing loop to
  host-side dispatch.

Usage, with the pre-combined builder::

    from qprogram.waveforms import Ramp
    from qprogram_qdac import QProgram

    qp = QProgram(label="flux-sweep")
    qp.qdac.set_offset("flux_q0", 0.42)
    qp.qdac.set_trigger("flux_q0", 50, position="start", outputs={1, 2})
    qp.qdac.play("flux_q0", Ramp(0.0, 1.0, 1000), dwell=10)
    qp.qdac.wait_trigger("flux_q0", port=3)

That program serializes to::

    #!QProgram 1.0

    require qdac 0.1

    metadata:
      label: "flux-sweep"

    body:
      qdac.set_offset "flux_q0" 0.42
      qdac.set_trigger "flux_q0" 50 outputs=[1, 2]
      qdac.play "flux_q0" Ramp(from_amplitude=0.0, to_amplitude=1.0, duration=1000) dwell=10
      qdac.wait_trigger "flux_q0" 3

Usage, with several vendors combined::

    from qprogram import QProgram as BaseQProgram
    from qprogram_qblox import QbloxMixin
    from qprogram_qdac import QdacMixin


    class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
        pass
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from qprogram.qprogram import QProgram as _BaseQProgram
from qprogram.serialization.registry import (
    register_vendor_operation,
    register_vendor_version,
)

from qprogram_qdac.mixin import QdacMixin
from qprogram_qdac.namespace import QdacNamespace
from qprogram_qdac.operations import (
    Play,
    SetOffset,
    SetTrigger,
    WaitTrigger,
)
from qprogram_qdac.profiles import QDAC_DEFAULT_V1
from qprogram_qdac.profiles import _register as _register_qdac_profile

# The installed distribution version is the single source of truth for the qdac vendor protocol
# version: the parser checks a file's ``require qdac <major.minor>`` against it.
try:
    __version__ = version("qprogram-qdac")
except PackageNotFoundError:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0"

# Registering on the base class rather than on this package's QProgram is what makes
# ``program.qdac.<operation>()`` work on any program, mixin or no mixin.
_BaseQProgram.register_vendor("qdac", QdacNamespace)

register_vendor_version("qdac", __version__)

# Every operation takes the default signature-driven serialize / parse pair. SetTrigger's
# ``outputs`` tuple goes through the writer's generic sequence branch (``outputs=[1, 2, 3]``), the
# parser's bracket-aware tokenizer keeps that literal whole, and ``_normalize_outputs`` turns the
# reloaded list back into the canonical sorted tuple.
register_vendor_operation("qdac", "wait_trigger", WaitTrigger)
register_vendor_operation("qdac", "set_trigger", SetTrigger)
register_vendor_operation("qdac", "set_offset", SetOffset)
register_vendor_operation("qdac", "play", Play)

# Importing qprogram_qdac.profiles above already registered the vendor capability tokens, which the
# profile names, so the profile passes token validation here.
_register_qdac_profile()


class QProgram(QdacMixin, _BaseQProgram):
    """:class:`~qprogram.QProgram` pre-combined with :class:`QdacMixin`.

    Behaves exactly like :class:`qprogram.QProgram`, with editor autocomplete for ``qp.qdac.*``.
    """


__all__ = [
    "QDAC_DEFAULT_V1",
    "Play",
    "QProgram",
    "QdacMixin",
    "QdacNamespace",
    "SetOffset",
    "SetTrigger",
    "WaitTrigger",
]
