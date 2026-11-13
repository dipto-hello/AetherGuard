"""Deterministic policy and atomic synthetic action execution."""
import json
import sqlite3
import uuid
from typing import Any, Dict, Optional

from app.policy.models import PolicyConfig, PolicyVerdict, TaskScope, ActionIntent
from app.policy.engine import evaluate_policy
from app.policy.storage import load_policy
from app.sandbox.exchange_rate import get_policy_rate_micros
from app.sandbox.service import get_order, get_task_scope, execute_sandbox_refund, DuplicateIdempotencyError, scope_refunded_amount

_DEFAULT_POLICY = object()


class GovernanceBoundary:
    def __init__(self, conn: sqlite3.Connection, policy_config: Optional[PolicyConfig] = _DEFAULT_POLICY):
        self.conn = conn
        self.policy_config = policy_config

    def intercept_and_evaluate(self, action_payload: Dict[str, Any], task_scope: Optional[TaskScope] = None, *,
                               require_refund_approval: bool = False) -> Dict[str, Any]:
        tool = action_payload.get('tool', '')
        arguments = action_payload.get('arguments', {})
        idempotency_key = action_payload.get('idempotency_key') or f'idemp_{uuid.uuid4().hex}'
        action_id = f'act_{uuid.uuid4().hex}'
        scope_id = task_scope.scope_id if task_scope else None
        intent = ActionIntent(action_id=action_id, tool=tool, arguments=arguments,
                              idempotency_key=idempotency_key, task_scope_id=scope_id)
        fingerprint = intent.compute_fingerprint()
        bdt_rate = get_policy_rate_micros() if tool == 'refund_order' and arguments.get('currency') == 'BDT' else None

        with self.conn:
            if not self.conn.in_transaction:
                self.conn.execute('BEGIN IMMEDIATE')
            # Legacy refunds predate the action registry; never reuse their keys.
            if self.conn.execute('SELECT 1 FROM refunds WHERE idempotency_key = ?', (idempotency_key,)).fetchone():
                raise DuplicateIdempotencyError('Idempotency key has already been used')
            try:
                self.conn.execute('INSERT INTO action_requests VALUES (?, ?, ?, ?)',
                                  (idempotency_key, fingerprint, scope_id, action_id))
            except sqlite3.IntegrityError as exc:
                raise DuplicateIdempotencyError('Idempotency key has already been used') from exc

            if scope_id:
                stored_scope = get_task_scope(self.conn, scope_id)
                try:
                    task_scope = TaskScope(**stored_scope) if stored_scope else None
                except Exception:
                    task_scope = None
            order_id = arguments.get('order_id')
            # Raw REST arguments can hold any JSON type; SQLite rejects non-text IDs.
            order = get_order(self.conn, order_id) if tool == 'refund_order' and isinstance(order_id, str) and order_id else None
            policy = load_policy(self.conn) if self.policy_config is _DEFAULT_POLICY else self.policy_config
            verdict, reason = evaluate_policy(tool, arguments, order, task_scope, policy, bdt_rate_micros=bdt_rate)
            if verdict != PolicyVerdict.BLOCKED and tool == 'refund_order' and task_scope:
                if scope_refunded_amount(self.conn, task_scope.scope_id) + arguments['amount'] > task_scope.max_amount:
                    verdict, reason = PolicyVerdict.BLOCKED, 'OUTSIDE_TRUSTED_TASK_SCOPE: Total refunds exceed scope maximum'
            if verdict == PolicyVerdict.ALLOWED and tool == 'refund_order' and require_refund_approval:
                verdict, reason = PolicyVerdict.APPROVAL_REQUIRED, 'TICKET_REVIEW_REQUIRED: Confirm the customer request and exact refund'
            self.conn.execute(
                'INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (f'audit_{uuid.uuid4().hex[:12]}', action_id, tool, verdict.value, reason, fingerprint,
                 json.dumps({'task_scope_id': scope_id, **({'bdt_rate_micros': bdt_rate} if bdt_rate is not None else {})})),
            )
            result = {'verdict': verdict.value, 'reason': reason, 'executed': False,
                      'action_id': action_id, 'fingerprint': fingerprint}
            if verdict == PolicyVerdict.APPROVAL_REQUIRED:
                self.conn.execute(
                    "INSERT INTO pending_actions (action_id, tool, arguments, fingerprint, task_scope_id, status, reason) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (action_id, tool, json.dumps(arguments), fingerprint, scope_id, reason),
                )
                result['pending_approval'] = True
            elif verdict == PolicyVerdict.ALLOWED and tool == 'refund_order':
                result['refund'] = execute_sandbox_refund(
                    self.conn, arguments['order_id'], arguments['amount'], arguments['currency'],
                    arguments['destination'], idempotency_key, action_id,
                )
                result['executed'] = True
            elif verdict == PolicyVerdict.ALLOWED:
                result['executed'] = True
            return result
