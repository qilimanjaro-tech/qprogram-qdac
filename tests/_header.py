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
"""The header lines the suite writes into its ``.qp`` fixtures.

Both versions in a fixture header follow an installed library rather than the numbers a test was
written under: the core DSL's `FORMAT_VERSION` for ``#!QProgram``, and this package's own
version, truncated to ``major.minor`` the way the writer truncates it, for ``require qdac``. A
fixture therefore stays loadable across a release of either. The tests that are about the
version rules build their own ``require`` line from `VENDOR_MAJOR`.
"""

from __future__ import annotations

from qprogram.serialization._format import FORMAT_VERSION

import qprogram_qdac

HEADER = f"#!QProgram {FORMAT_VERSION}"
VENDOR_VERSION = ".".join(qprogram_qdac.__version__.split(".")[:2])
VENDOR_MAJOR = VENDOR_VERSION.split(".")[0]
REQUIRE = f"require qdac {VENDOR_VERSION}"
