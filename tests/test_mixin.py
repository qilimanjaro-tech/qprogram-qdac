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
"""Tests for :class:`~qprogram_qdac.mixin.QdacMixin`, the typed ``.qdac`` property.

The mixin is an autocomplete surface over the dynamic vendor lookup, so the invariants under test
are that both routes reach the same namespace class, that the namespace is cached per program
instance, and that the mixin composes with another vendor's mixin through the MRO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from qprogram import QProgram as BaseQProgram
from qprogram.vendor import VendorNamespace

from qprogram_qdac import QProgram as QdacQProgram
from qprogram_qdac.mixin import QdacMixin
from qprogram_qdac.namespace import QdacNamespace

if TYPE_CHECKING:
    from collections.abc import Iterator


class _SpareNamespace(VendorNamespace):
    """A second vendor namespace, registered temporarily to test mixin composition."""


@pytest.fixture
def spare_vendor() -> Iterator[type[VendorNamespace]]:
    """Register the ``spare`` vendor for one test and drop it again afterwards."""
    BaseQProgram.register_vendor("spare", _SpareNamespace)
    yield _SpareNamespace
    BaseQProgram._vendor_registry.pop("spare", None)


def test_qprogram_subclasses_mixin():
    assert issubclass(QdacQProgram, QdacMixin)
    assert issubclass(QdacQProgram, BaseQProgram)


def test_mixin_property_returns_namespace():
    qp = QdacQProgram()
    assert isinstance(qp.qdac, QdacNamespace)


def test_mixin_property_caches_per_instance():
    qp = QdacQProgram()
    first = qp.qdac
    second = qp.qdac
    assert first is second


def test_mixin_namespace_distinct_per_instance():
    qp1 = QdacQProgram()
    qp2 = QdacQProgram()
    assert qp1.qdac is not qp2.qdac


def test_dynamic_lookup_on_base_qprogram_reaches_the_namespace(base_program):
    """A program built without the mixin gets ``.qdac`` from QProgram's dynamic ``__getattr__``."""
    assert isinstance(base_program.qdac, QdacNamespace)


def test_mixins_compose_through_the_mro(spare_vendor):
    """Two vendor mixins listed in the MRO each keep their own typed property."""

    class _SpareMixin:
        @property
        def spare(self) -> VendorNamespace:
            return spare_vendor(self)

    class _TwoVendorProgram(QdacMixin, _SpareMixin, BaseQProgram):
        pass

    qp = _TwoVendorProgram()
    assert isinstance(qp.qdac, QdacNamespace)
    assert isinstance(qp.spare, spare_vendor)
