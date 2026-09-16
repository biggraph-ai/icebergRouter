"""Reviewed provider boundary primitives with no bundled provider SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from iceberg_router.contracts._validation import require_text
from iceberg_router.contracts.adapters import OperationContext, OperationResult
from iceberg_router.contracts.options import OperationKind


class SingleAttemptTransport(Protocol):
    """Injected transport representing exactly one physical provider attempt."""

    def __call__(self, context: OperationContext) -> OperationResult: ...


@dataclass(frozen=True, slots=True)
class SingleAttemptAdapter:
    """Validate an operation kind and invoke an injected transport exactly once.

    The wrapper performs no retry, fallback, pricing inference, exception coercion,
    or usage defaulting. The executor owns exception-to-unknown handling. Code
    behind ``transport`` must be separately reviewed because this wrapper cannot
    detect retries hidden inside an SDK or remote gateway.
    """

    operation_kind: OperationKind
    adapter_version: str
    transport: SingleAttemptTransport

    def __post_init__(self) -> None:
        if not isinstance(self.operation_kind, OperationKind):
            raise TypeError("operation_kind must be OperationKind")
        require_text(self.adapter_version, "adapter_version", maximum=128)
        if not callable(self.transport):
            raise TypeError("transport must be callable")

    def execute(self, context: OperationContext) -> OperationResult:
        if not isinstance(context, OperationContext):
            raise TypeError("context must be OperationContext")
        if context.node.kind is not self.operation_kind:
            raise ValueError(
                f"adapter for {self.operation_kind.value} cannot execute "
                f"{context.node.kind.value}"
            )
        if context.node.operation_version != self.adapter_version:
            raise ValueError(
                f"operation version {context.node.operation_version!r} does not match "
                f"adapter version {self.adapter_version!r}"
            )
        result = self.transport(context)
        if not isinstance(result, OperationResult):
            raise TypeError("transport must return OperationResult")
        return result


__all__ = ("SingleAttemptAdapter", "SingleAttemptTransport")
