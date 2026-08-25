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
"""Shared fixtures for the qprogram-qdac test suite.

Importing :mod:`qprogram_qdac` is the activation step: it registers the ``qdac`` vendor namespace,
the ``.qp`` serializer entries and the ``qdac-default-v1`` profile. Every fixture below imports the
package, so the registries are populated before any test runs.
"""

from __future__ import annotations

import pytest
from qprogram import BusSchema
from qprogram import QProgram as BaseQProgram

from qprogram_qdac import QProgram as QdacQProgram


@pytest.fixture
def flux_tunable_schema() -> BusSchema:
    """A flux-tunable transmon preset (q with drive + readout + flux)."""
    return BusSchema.flux_tunable_transmon()


@pytest.fixture
def foreign_schema() -> BusSchema:
    """A second flux-tunable transmon preset, equal in shape to the first but a distinct object.

    A :class:`~qprogram.BusRef` belongs to the schema instance that produced it, so the refs of
    this schema are the ones a program bound to ``flux_tunable_schema`` has to refuse.
    """
    return BusSchema.flux_tunable_transmon()


@pytest.fixture
def qdac_program(flux_tunable_schema: BusSchema) -> QdacQProgram:
    """A typed QDAC program bound to the flux-tunable transmon schema."""
    return QdacQProgram(schema=flux_tunable_schema)


@pytest.fixture
def base_program(flux_tunable_schema: BusSchema) -> BaseQProgram:
    """A base QProgram without the mixin, which reaches ``.qdac`` through dynamic lookup."""
    return BaseQProgram(schema=flux_tunable_schema)
