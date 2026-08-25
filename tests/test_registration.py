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
"""Tests for the registration side effects of importing :mod:`qprogram_qdac`.

Importing the package is the activation step. Each test below pins one of the registrations that
import performs: the vendor namespace on :class:`~qprogram.QProgram`, the vendor protocol version,
one ``.qp`` serializer entry per operation, the capability tokens, and the profile bundle. The last
two tests cover the entry point that lets :func:`~qprogram.loads` perform the import itself.
"""

from __future__ import annotations

import importlib.metadata as md

from qprogram import QProgram as BaseQProgram
from qprogram.protocol import CAPABILITY_REGISTRY, PROFILE_REGISTRY
from qprogram.serialization.registry import get_operation_spec, get_vendor_version

import qprogram_qdac
from qprogram_qdac.mixin import QdacMixin
from qprogram_qdac.namespace import QdacNamespace
from qprogram_qdac.operations import Play, SetOffset, SetTrigger, WaitTrigger

_OPERATIONS = {
    "wait_trigger": WaitTrigger,
    "set_trigger": SetTrigger,
    "set_offset": SetOffset,
    "play": Play,
}


def test_vendor_namespace_registered():
    assert BaseQProgram._vendor_registry["qdac"] is QdacNamespace


def test_vendor_version_registered():
    ver = get_vendor_version("qdac")
    assert ver is not None
    assert ver.startswith("0.")


def test_all_operations_registered():
    for name, cls in _OPERATIONS.items():
        spec = get_operation_spec("qdac", name)
        assert spec is not None, f"qdac.{name} not registered"
        assert spec.cls is cls


def test_registered_operations_are_dotted_by_vendor():
    """The qualified name is the keyword the writer emits and the parser matches."""
    for name in _OPERATIONS:
        spec = get_operation_spec("qdac", name)
        assert spec.vendor == "qdac"
        assert spec.qualified_name == f"qdac.{name}"


def test_operations_use_the_signature_driven_callbacks():
    """No operation overrides serialize or parse, so both come from the constructor signature."""
    for name in _OPERATIONS:
        spec = get_operation_spec("qdac", name)
        assert spec.serialize is None
        assert spec.parse is None


def test_vendor_capability_tokens_registered():
    """Tokens are registered before the profile that names them, or profile construction fails."""
    for token in (
        "vendor.qdac.wait_trigger",
        "vendor.qdac.set_trigger",
        "vendor.qdac.set_offset",
        "vendor.qdac.play",
    ):
        assert token in CAPABILITY_REGISTRY, token


def test_profile_registered():
    assert "qdac-default-v1" in PROFILE_REGISTRY


def test_qprogram_qdac_version_string():
    assert isinstance(qprogram_qdac.__version__, str)
    assert qprogram_qdac.__version__.count(".") >= 1


def test_pre_combined_qprogram_carries_the_mixin():
    assert issubclass(qprogram_qdac.QProgram, QdacMixin)
    assert issubclass(qprogram_qdac.QProgram, BaseQProgram)


def test_qdac_declares_vendor_entry_point():
    """The ``qprogram.vendors`` entry point is what lets a ``.qp`` file activate the package."""
    eps = {ep.name: ep.value for ep in md.entry_points(group="qprogram.vendors")}
    assert eps.get("qdac") == "qprogram_qdac"


def test_qdac_entry_point_loads_and_registers():
    """Loading the entry point imports the self-registering module and records the version."""
    (ep,) = [e for e in md.entry_points(group="qprogram.vendors") if e.name == "qdac"]
    mod = ep.load()
    assert mod.__name__ == "qprogram_qdac"
    assert get_vendor_version("qdac") is not None
