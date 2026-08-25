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
"""The capability profile bundle for the QDAC vendor extension.

Ships :data:`QDAC_DEFAULT_V1`, the bus-level profile listing what the QDAC waveform engine supports
on one bus (one channel). A qdac platform attaches it to the flux buses of its schema and leaves the
drive and readout buses to another vendor, qblox for instance. The platform-level slot is filled by
the core-shipped ``qprogram-base-v1``, the same as for any other vendor.

The profile carries two predicates:

- A soft :class:`~qprogram.DomainConstraint` excluding ``"rt"``, emitted whenever a qdac operation
  reads a loop-bound :class:`~qprogram.Variable`. QDAC has no FPGA, so every swept parameter (a DC
  offset, a waveform-engine setting, a waveform's own parameters) has to be re-uploaded from the
  host between iterations. The constraint names the enclosing loop, which the classifier drops to
  ``{host}`` and reports as a ``forced-host`` warning quoting the constraint's reason; everything
  outside the qdac operation is left alone.
- A hard ``qdac.empty-trigger-outputs`` error :class:`~qprogram.Diagnostic` for a
  :class:`~qprogram_qdac.operations.SetTrigger` that arms no output.

Registered as a side effect of importing :mod:`qprogram_qdac`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram.protocol import (
    Diagnostic,
    DomainConstraint,
    Profile,
    ValidationContext,
    register_capability_tokens,
    register_profile,
)

from qprogram_qdac.operations import Play, SetOffset, SetTrigger, WaitTrigger

# Register the vendor tokens *before* constructing the profile that names them:
# Profile.__post_init__ checks every listed token against CAPABILITY_REGISTRY.
register_capability_tokens(
    "vendor.qdac.wait_trigger",
    "vendor.qdac.set_trigger",
    "vendor.qdac.set_offset",
    "vendor.qdac.play",
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.blocks.block import Block
    from qprogram.operations.operation import Operation


_QDAC_OP_CLASSES: tuple[type, ...] = (WaitTrigger, SetTrigger, SetOffset, Play)
"""Every qdac :class:`~qprogram.operations.Operation` subclass.

:func:`_qdac_op_with_swept_var_is_host_only` filters on it. A predicate runs on every node the
validator visits within its slot, core operations included, so it has to recognize its own nodes
rather than trusting routing to have done it.
"""


def _qdac_op_with_swept_var_is_host_only(
    node: Operation | Block,
    ctx: ValidationContext,
) -> Iterable[Diagnostic | DomainConstraint]:
    """Constrain the binding loop of any variable a qdac operation reads to host-side dispatch.

    QDAC has no FPGA. Every parameter change goes through the host's slow-control plane, at
    millisecond latency, so a qdac operation that reads a variable bound by an enclosing
    :class:`~qprogram.blocks.Sweep` cannot sit inside a real-time hardware loop. The loop has to
    dispatch host-side and re-upload the value once per iteration.

    The constraint targets the **binding loop block**, never the qdac operation, which is what the
    spec requires and what keeps the operation's own classification untouched. What changes is the
    loop: its support drops from rt-or-host to host only.

    Variables are read off the node with :meth:`~qprogram.operations.Operation.variables`, which
    descends into expression arguments and waveform parameters. A
    ``play(bus, Square(amplitude=v))`` is therefore caught as surely as a ``set_offset(bus, v)``.

    On a platform that fills only the host half of its qdac bus slots the constraint changes
    nothing: the operation is host-only by construction there, and op-children consensus lifts the
    loop on its own. What the constraint covers is a platform that fills both halves, and when it
    does fire it supplies the reason text the loop's ``forced-host`` warning quotes.

    Args:
        node (Operation | Block): The AST node currently being checked.
        ctx (ValidationContext): Validation context, used to find the loop that binds each variable.

    Yields:
        One :class:`~qprogram.DomainConstraint` excluding ``"rt"`` per distinct binding loop reached
        from ``node``. Nothing when ``node`` is not a qdac operation, or reads no bound variable.
    """
    if not isinstance(node, _QDAC_OP_CLASSES):
        return
    seen_loops: set[int] = set()
    for var in node.variables():
        binding_loop = ctx.binding_loop_of(var)
        if binding_loop is None or id(binding_loop) in seen_loops:
            continue
        seen_loops.add(id(binding_loop))
        yield DomainConstraint(
            node=binding_loop,
            exclude=frozenset({"rt"}),
            reason=(
                f"qdac.{type(node).__name__} references loop-bound variable {var.id!r}; "
                f"qdac has no FPGA, so the loop must dispatch host-side."
            ),
        )


def _set_trigger_outputs_required(
    node: Operation | Block,
    ctx: ValidationContext,  # ruff: ignore[unused-function-argument]  a purely structural check
) -> Iterable[Diagnostic | DomainConstraint]:
    """Reject a :class:`~qprogram_qdac.operations.SetTrigger` that arms no output.

    A trigger with an empty ``outputs`` set fires onto nothing, which is a mistake in every domain
    rather than something host-side dispatch could rescue. That makes it a
    :class:`~qprogram.Diagnostic` and not a :class:`~qprogram.DomainConstraint`.

    Args:
        node (Operation | Block): The AST node currently being checked.
        ctx (ValidationContext): Validation context. Unused: the check reads only the node.

    Yields:
        One ``qdac.empty-trigger-outputs`` error :class:`~qprogram.Diagnostic` when ``node`` is a
        ``SetTrigger`` with no outputs. Nothing otherwise.
    """
    if not isinstance(node, SetTrigger):
        return
    if not node.outputs:
        yield Diagnostic(
            severity="error",
            code="qdac.empty-trigger-outputs",
            message=(
                "SetTrigger has no outputs configured. Specify at least one output index, e.g. "
                "outputs={1} or outputs=[1, 2]."
            ),
            node=node,
        )


_BUS_OPS: frozenset[str] = frozenset(
    {
        "vendor.qdac.wait_trigger",
        "vendor.qdac.set_trigger",
        "vendor.qdac.set_offset",
        "vendor.qdac.play",
    },
)
"""The qdac vendor operation tokens.

Every qdac operation carries a ``bus`` attribute, so it routes to the per-bus
:class:`~qprogram.BusCapabilities` slot the platform attaches qdac to rather than to the
platform-level slot.
"""

_WAVEFORMS: frozenset[str] = frozenset(
    {
        "waveform.single",
        "waveform.arbitrary",
        "waveform.chained",
        "waveform.cosine",
        "waveform.flat_top",
        "waveform.gaussian",
        "waveform.ramp",
        "waveform.sine",
        "waveform.square",
        "waveform.sech",
        "waveform.snz",
        "waveform.tukey",
    },
)
"""The single-channel waveform tokens the QDAC waveform engine renders.

Waveform tokens live on the bus profile because a waveform reaches the hardware through a bus. QDAC
drives one channel per bus, so ``waveform.iq`` and the IQ waveform classes are left out on purpose:
a program playing an :class:`~qprogram.waveforms.IQDrag` on a qdac bus fails validation with a
``missing-capability`` diagnostic.
"""


QDAC_DEFAULT_V1 = Profile(
    name="qdac-default-v1",
    version=(0, 1, 0),
    extends=None,
    capabilities=_BUS_OPS | _WAVEFORMS,
    limits={
        # The waveform engine has a hard floor on dwell time, below which its output interpolation
        # breaks down. No core check reads this limit; it is published here for platforms that wire
        # in a predicate of their own.
        "min_dwell_ns": 100,
    },
    predicates=(
        _qdac_op_with_swept_var_is_host_only,
        _set_trigger_outputs_required,
    ),
    vendor_versions={"qdac": (0, 1, 0)},
)
"""The default QDAC bus-level capability profile.

Because qdac has no FPGA, a platform fills the ``host`` half of each qdac-driven bus slot with this
profile and leaves the ``rt`` half empty. Every qdac operation is then host-side by design, and a
loop whose operations are all qdac classifies as host-side through op-children consensus alone. A
platform that does fill both halves gets the same outcome for swept programs, this time from the
profile's own :class:`~qprogram.DomainConstraint` predicate.

The profile holds every qdac vendor token (``wait_trigger``, ``set_trigger``, ``set_offset``,
``play``) plus the single-channel waveforms the engine renders. The platform-level slot of a qdac
platform's :class:`~qprogram.PlatformCapabilities` uses the core-shipped ``qprogram-base-v1``
directly: qdac has no bus-less operations, so it contributes nothing at that level.
"""


def _register() -> None:
    """Idempotently register :data:`QDAC_DEFAULT_V1` on the global profile registry."""
    register_profile(QDAC_DEFAULT_V1)


__all__ = ["QDAC_DEFAULT_V1"]
