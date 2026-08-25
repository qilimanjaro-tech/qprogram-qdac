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
"""The typed mixin that spells ``.qdac`` out on a QProgram subclass.

The mixin exists for editor support and nothing else. At runtime the base
:class:`~qprogram.QProgram`'s dynamic ``__getattr__`` already routes ``program.qdac.*`` to the
registered :class:`~qprogram_qdac.namespace.QdacNamespace`. Type checkers and editors cannot see
that dispatch, so the mixin declares the namespace as a typed ``@property``.

Usage, one vendor::

    from qprogram_qdac import QProgram

    qp = QProgram()
    qp.qdac.set_offset("flux_q0", 0.42)

Usage, several vendors combined by a platform::

    from qprogram import QProgram as BaseQProgram
    from qprogram_qblox import QbloxMixin
    from qprogram_qdac import QdacMixin


    class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
        pass
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram_qdac.namespace import QdacNamespace

if TYPE_CHECKING:
    from qprogram.qprogram import QProgram as _BaseQProgram


class QdacMixin:
    """Mixin that adds a typed ``.qdac`` property to a QProgram subclass.

    Combine it with :class:`qprogram.QProgram` through multiple inheritance, listing one mixin per
    vendor. :class:`qprogram_qdac.QProgram` is that combination already made.
    """

    @property
    def qdac(self: _BaseQProgram) -> QdacNamespace:  # type: ignore[misc]
        """This program's typed QDAC namespace.

        The first access builds a :class:`QdacNamespace` bound to the program and stores it on the
        instance, so every later access hands back the same object.
        """
        # Reading and writing the cache through ``object`` keeps it clear of any attribute hooks
        # a QProgram subclass installs, and of the vendor lookup in ``QProgram.__getattr__``.
        try:
            return object.__getattribute__(self, "_qdac_ns")  # ruff: ignore[unnecessary-dunder-call]
        except AttributeError:
            pass
        ns = QdacNamespace(self)
        object.__setattr__(self, "_qdac_ns", ns)  # ruff: ignore[unnecessary-dunder-call]
        return ns
