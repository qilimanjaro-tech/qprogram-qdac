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
"""The header lines the suite writes into its ``.qp`` fixtures, and what the installed core does.

Both versions in a fixture header follow an installed library rather than the numbers a test was
written under: the core DSL's `FORMAT_VERSION` for ``#!QProgram``, and this package's own
version, truncated to ``major.minor`` the way the writer truncates it, for ``require qdac``. A
fixture therefore stays loadable across a release of either. The tests that are about the
version rules build their own ``require`` line from `VENDOR_MAJOR`. `needs_core_migrations` skips
what only holds once the core DSL this package resolves is 0.2 or newer.
"""

from __future__ import annotations

from importlib.metadata import version

import pytest
from qprogram.serialization._format import FORMAT_VERSION

import qprogram_qdac

HEADER = f"#!QProgram {FORMAT_VERSION}"
# The core's own version, not its FORMAT_VERSION: the format was numbered 1.0 before 0.2, so only
# the distribution version orders the two releases correctly.
CORE_VERSION = tuple(int(part) for part in version("qprogram").split(".")[:2])
needs_core_migrations = pytest.mark.skipif(
    CORE_VERSION < (0, 2),
    reason="qprogram before 0.2 rounded a patch off a require line instead of refusing it",
)
VENDOR_VERSION = ".".join(qprogram_qdac.__version__.split(".")[:2])
VENDOR_MAJOR = VENDOR_VERSION.split(".")[0]
REQUIRE = f"require qdac {VENDOR_VERSION}"
