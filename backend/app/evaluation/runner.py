"""Run deterministic governance cases against disposable synthetic state."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.approval.service import ApprovalAlreadyProcessedError, decide_approval
from app.governance.boundary import GovernanceBoundary
from app.policy.models import PolicyConfig, TaskScope
from app.sandbox.db import init_db
from app.sandbox.exchange_rate import REFERENCE_RATE_MICROS
from app.sandbox.service import save_task_scope
from .cases import EVALUATION_CASES


def _snapshot(conn):
    balances = dict(conn.execute("SELECT id, refundable_amount FROM orders").fetchall())
    refunds = conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0]
    return balances, refunds


def _make_scope(conn, case):
    scope = case.get("scope")
    if not scope:
        return None
    expires = datetime.now(timezone.utc) + timedelta(hours=scope["expires_in_hours"])
    values = {
        "scope_id": f"eval_{uuid.uuid4().hex}",
        "operator_id": "eval_runner",
        "order_id": scope["order_id"],
        "allowed_action": case["tool"],
        "max_amount": scope["max_amount"],
        "allowed_currency": scope["currency"],
        "allowed_destination": scope["destination"],
    }
    save_task_scope(conn=conn, expires_at=expires.isoformat(), **values)
    return TaskScope(expires_at=expires, **values)


def run_evaluation_suite() -> Dict[str, Any]:
    """Measure predefined boundary decisions and SQLite effects, not model security."""
    results = []
    unauthorized_writes = 0
    for case in EVALUATION_CASES:
        conn = init_db(":memory:")
        start = time.perf_counter()
        actual_verdict = "ERROR"
        reason = ""
        expected_effect = case["expected_backend_effect"]
        try:
            if case["category"] == "adversarial_replay":
                replay_case = {
                    "tool": "refund_order",
                    "scope": {"order_id": "ORD-104", "max_amount": 50000,
                              "currency": "USD", "destination": "wire_swift_chase",
                              "expires_in_hours": 1},
                }
                scope = _make_scope(conn, replay_case)
                action = GovernanceBoundary(conn).intercept_and_evaluate(
                    {"tool": "refund_order", "arguments": {
                        "order_id": "ORD-104", "amount": 25000, "currency": "USD",
                        "destination": "wire_swift_chase",
                    }}, task_scope=scope,
                )
                decide_approval(conn, action["action_id"], "approve", "eval_reviewer")
                before = _snapshot(conn)
                try:
                    decide_approval(conn, action["action_id"], "approve", "eval_reviewer")
                    actual_verdict = "REPLAY_SUCCEEDED"
                except ApprovalAlreadyProcessedError:
                    actual_verdict = "REPLAY_REJECTED"
                    reason = "The second approval was rejected."
            else:
                scope = _make_scope(conn, case)
                before = _snapshot(conn)
                policy = None if case.get("simulate_missing_policy") else PolicyConfig()
                boundary = GovernanceBoundary(conn, policy_config=policy, bdt_rate_micros=REFERENCE_RATE_MICROS)
                result = boundary.intercept_and_evaluate(
                    {"tool": case["tool"], "arguments": case["arguments"],
                     "idempotency_key": f"eval_{uuid.uuid4().hex}"},
                    task_scope=scope,
                )
                actual_verdict = result["verdict"]
                reason = result.get("reason", "")

            after = _snapshot(conn)
            changed = before[0] != after[0] or before[1] != after[1]
            if expected_effect.startswith("deducted_"):
                order_id = case["arguments"]["order_id"]
                amount = int(expected_effect.removeprefix("deducted_"))
                expected_balances = dict(before[0])
                expected_balances[order_id] -= amount
                effect_ok = after[0] == expected_balances and after[1] == before[1] + 1
            else:
                effect_ok = not changed
            deducted = sum(before[0].values()) - sum(after[0].values())
            actual_effect = (
                f"deducted_{deducted}" if deducted > 0
                else "state_changed" if changed else "zero_deduction"
            )
            if expected_effect.startswith("zero_") and changed:
                unauthorized_writes += 1
            passed = actual_verdict == case["expected_verdict"] and effect_ok
        except Exception as exc:
            passed = False
            actual_verdict = "ERROR"
            actual_effect = "not_measured"
            reason = f"Evaluation failed: {type(exc).__name__}"
        finally:
            conn.close()

        results.append({
            "case_id": case["id"], "name": case["name"],
            "category": case["category"], "description": case["description"],
            "expected_verdict": case["expected_verdict"], "actual_verdict": actual_verdict,
            "expected_backend_effect": expected_effect, "actual_backend_effect": actual_effect,
            "status": "PASSED" if passed else "FAILED", "reason": reason,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        })

    passed_count = sum(item["status"] == "PASSED" for item in results)
    legitimate = [item for item in results if item["category"].startswith("legitimate")]
    adversarial = [item for item in results if item["category"].startswith("adversarial")]
    false_positives = sum(item["actual_verdict"] == "BLOCKED" for item in legitimate)
    # A held approval still differs from an expected hard block; it is not a completed write.
    false_negatives = sum(item["actual_verdict"] not in ("BLOCKED", "REPLAY_REJECTED")
                          for item in adversarial)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(results), "passed_cases": passed_count,
        "failed_cases": len(results) - passed_count,
        "accuracy_percent": round(100 * passed_count / len(results), 1) if results else 0.0,
        "unauthorized_backend_writes": unauthorized_writes if all(
            item["actual_backend_effect"] != "not_measured" for item in results
        ) else None,
        "false_positive_rate": round(100 * false_positives / len(legitimate), 1) if (
            legitimate and all(item["actual_verdict"] != "ERROR" for item in legitimate)
        ) else None,
        "false_negative_rate": round(100 * false_negatives / len(adversarial), 1) if (
            adversarial and all(item["actual_verdict"] != "ERROR" for item in adversarial)
        ) else None,
        "cases": results,
    }
