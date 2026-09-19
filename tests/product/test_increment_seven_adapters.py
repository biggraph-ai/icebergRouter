from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.adapters import SingleAttemptAdapter  # noqa: E402
from iceberg_router.contracts import (  # noqa: E402
    AccountId,
    AttemptId,
    AuthorizationId,
    Branch,
    BranchOutcome,
    DecisionId,
    Nanodollars,
    NodeId,
    OperationAdapter,
    OperationContext,
    OperationKind,
    OperationLimits,
    OperationNode,
    OperationResult,
    RequestId,
    ReservationId,
    UsageState,
)


def node(kind: OperationKind = OperationKind.MODEL_CALL) -> OperationNode:
    return OperationNode(
        NodeId("operation"),
        kind,
        AccountId("provider-account"),
        Nanodollars(100),
        OperationLimits(1, 1_000, 100, 100),
        "operation-v1",
        (Branch(BranchOutcome.SUCCESS, NodeId("complete")),),
    )


def context(kind: OperationKind = OperationKind.MODEL_CALL) -> OperationContext:
    return OperationContext(
        RequestId("request-1"),
        DecisionId("decision-1"),
        node(kind),
        1,
        AttemptId("attempt-1"),
        AuthorizationId("authorization-1"),
        ReservationId("reservation-1"),
        {"prompt": "offline fixture"},
    )


class RecordingTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, operation_context):
        self.calls.append(operation_context)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class AdapterContractTests(unittest.TestCase):
    def test_context_requires_authorized_attempt_identity(self):
        valid = context()
        self.assertEqual(valid.attempt_number, 1)
        with self.assertRaises(ValueError):
            OperationContext(
                valid.request_id,
                valid.decision_id,
                valid.node,
                0,
                valid.attempt_id,
                valid.authorization_id,
                valid.reservation_id,
                valid.payload,
            )
        with self.assertRaises(TypeError):
            OperationContext(
                valid.request_id,
                valid.decision_id,
                valid.node,
                True,
                valid.attempt_id,
                valid.authorization_id,
                valid.reservation_id,
                valid.payload,
            )

    def test_result_keeps_unknown_usage_distinct_from_zero(self):
        unknown = OperationResult(BranchOutcome.UNKNOWN, UsageState.UNKNOWN, None)
        known_zero = OperationResult(
            BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(0)
        )
        self.assertIsNone(unknown.actual_cost)
        self.assertEqual(known_zero.actual_cost, Nanodollars(0))
        with self.assertRaises(ValueError):
            OperationResult(
                BranchOutcome.SUCCESS, UsageState.UNKNOWN, Nanodollars(0)
            )

    def test_unfunded_outcome_is_reserved_for_governor(self):
        with self.assertRaises(ValueError):
            OperationResult(BranchOutcome.UNFUNDED, UsageState.UNKNOWN, None)

    def test_single_attempt_adapter_invokes_transport_once(self):
        expected = OperationResult(
            BranchOutcome.SUCCESS,
            UsageState.KNOWN,
            Nanodollars(9),
            "output-1",
            "receipt-1",
        )
        transport = RecordingTransport(expected)
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", transport
        )
        operation_context = context()
        self.assertIsInstance(adapter, OperationAdapter)
        self.assertEqual(adapter.execute(operation_context), expected)
        self.assertEqual(transport.calls, [operation_context])

    def test_kind_mismatch_fails_before_transport(self):
        transport = RecordingTransport(
            OperationResult(BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(1))
        )
        adapter = SingleAttemptAdapter(
            OperationKind.VERIFY, "verify-adapter-v1", transport
        )
        with self.assertRaises(ValueError):
            adapter.execute(context(OperationKind.MODEL_CALL))
        self.assertEqual(transport.calls, [])
        version_mismatch = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v2", transport
        )
        with self.assertRaises(ValueError):
            version_mismatch.execute(context(OperationKind.MODEL_CALL))
        self.assertEqual(transport.calls, [])

    def test_bad_transport_result_is_not_coerced(self):
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", RecordingTransport({"cost": 0})
        )
        with self.assertRaises(TypeError):
            adapter.execute(context())

    def test_transport_exception_propagates_without_adapter_retry(self):
        transport = RecordingTransport(TimeoutError("offline timeout"))
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", transport
        )
        with self.assertRaises(TimeoutError):
            adapter.execute(context())
        self.assertEqual(len(transport.calls), 1)

    def test_adapter_configuration_is_strict(self):
        with self.assertRaises(ValueError):
            SingleAttemptAdapter(OperationKind.MODEL_CALL, "", RecordingTransport(None))
        with self.assertRaises(TypeError):
            SingleAttemptAdapter(OperationKind.MODEL_CALL, "adapter-v1", object())


if __name__ == "__main__":
    unittest.main()
