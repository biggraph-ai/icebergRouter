"""Reviewed provider boundary primitives with no bundled provider SDK."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import multiprocessing
import queue
from typing import Protocol

from iceberg_router.contracts._validation import require_text
from iceberg_router.contracts.adapters import OperationContext, OperationResult
from iceberg_router.contracts.options import OperationKind
from iceberg_router.contracts.resources import ResourceIdentity


class TransportDeadlineExceeded(TimeoutError):
    """Caller-visible deadline expired; dispatched work may still be running."""


def _sandbox_worker(transport, context, output) -> None:
    try:
        import resource

        seconds = max(1, (context.node.limits.timeout_ms + 999) // 1000)
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
        output.put((True, transport(context)))
    except BaseException as error:
        output.put((False, (type(error).__name__, str(error))))


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
    resource: ResourceIdentity
    transport: SingleAttemptTransport

    def __post_init__(self) -> None:
        if not isinstance(self.operation_kind, OperationKind):
            raise TypeError("operation_kind must be OperationKind")
        require_text(self.adapter_version, "adapter_version", maximum=128)
        if not isinstance(self.resource, ResourceIdentity):
            raise TypeError("resource must be ResourceIdentity")
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
        if context.node.resource != self.resource:
            raise ValueError(
                f"resource {context.node.resource.key!r} does not match "
                f"adapter resource {self.resource.key!r}"
            )
        if not context.node.bounded_contract.strict_eligible:
            raise ValueError("operation lacks reviewed bounded-contract evidence")
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="iceberg-transport")
        future = pool.submit(self.transport, context)
        try:
            result = future.result(timeout=context.node.limits.timeout_ms / 1000)
        except FutureTimeout as error:
            future.cancel()
            raise TransportDeadlineExceeded(
                "transport deadline expired; upstream work may continue"
            ) from error
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if not isinstance(result, OperationResult):
            raise TypeError("transport must return OperationResult")
        return result


@dataclass(frozen=True, slots=True)
class SandboxedToolAdapter:
    """Run one local deterministic tool in a killable child process.

    This Linux/POSIX boundary enforces a wall deadline and CPU limit. It is not a
    filesystem or network isolation claim; deployments needing those guarantees
    must place the child inside a separately reviewed OS sandbox.
    """

    adapter_version: str
    resource: ResourceIdentity
    transport: SingleAttemptTransport

    def __post_init__(self) -> None:
        require_text(self.adapter_version, "adapter_version", maximum=128)
        if not isinstance(self.resource, ResourceIdentity):
            raise TypeError("resource must be ResourceIdentity")
        if not callable(self.transport):
            raise TypeError("transport must be callable")

    def execute(self, context: OperationContext) -> OperationResult:
        if context.node.kind is not OperationKind.DETERMINISTIC_TOOL:
            raise ValueError("sandbox adapter only executes deterministic tools")
        if context.node.operation_version != self.adapter_version:
            raise ValueError("tool operation version does not match sandbox adapter")
        if context.node.resource != self.resource:
            raise ValueError("tool resource does not match sandbox adapter")
        if not context.node.bounded_contract.strict_eligible:
            raise ValueError("tool lacks reviewed bounded-contract evidence")
        process_context = multiprocessing.get_context("fork")
        output = process_context.Queue(maxsize=1)
        process = process_context.Process(
            target=_sandbox_worker, args=(self.transport, context, output), daemon=True
        )
        process.start()
        process.join(context.node.limits.timeout_ms / 1000)
        if process.is_alive():
            process.terminate()
            process.join()
            output.close()
            raise TransportDeadlineExceeded("local tool exceeded enforced deadline")
        try:
            successful, value = output.get_nowait()
        except queue.Empty as error:
            raise RuntimeError("sandboxed tool exited without a result") from error
        finally:
            output.close()
        if not successful:
            raise RuntimeError(f"sandboxed tool failed: {value[0]}: {value[1]}")
        if not isinstance(value, OperationResult):
            raise TypeError("sandboxed tool must return OperationResult")
        return value


__all__ = (
    "SingleAttemptAdapter",
    "SingleAttemptTransport",
    "SandboxedToolAdapter",
    "TransportDeadlineExceeded",
)
