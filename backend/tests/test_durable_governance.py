import pytest
from datetime import datetime, timedelta, timezone

from app.policy.models import TaskScope
from app.governance.boundary import GovernanceBoundary
from app.sandbox.db import init_db, get_connection
from app.sandbox.service import get_order, save_task_scope, DuplicateIdempotencyError


def scope_for(conn, amount=30000):
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    values = dict(scope_id='durable-scope', operator_id='operator', order_id='ORD-101',
                  allowed_action='refund_order', max_amount=amount, allowed_currency='USD',
                  allowed_destination='card_visa_4242')
    save_task_scope(conn, expires_at=expiry.isoformat(), **values)
    return TaskScope(expires_at=expiry, **values)


def payload(amount, key='durable-key'):
    return {'tool': 'refund_order', 'idempotency_key': key,
            'arguments': {'order_id': 'ORD-101', 'amount': amount, 'currency': 'USD',
                          'destination': 'card_visa_4242'}}


def test_scope_maximum_limits_total_of_distinct_refunds(tmp_path):
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn, amount=4000)
    assert GovernanceBoundary(conn).intercept_and_evaluate(payload(3000, 'first'), scope)['executed']
    result = GovernanceBoundary(conn).intercept_and_evaluate(payload(2000, 'second'), scope)
    assert result['verdict'] == 'BLOCKED'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 22000
    conn.close()


def test_approval_rechecks_remaining_scope_budget(tmp_path):
    from app.approval.service import decide_approval, ApprovalError
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn, amount=10000)
    boundary = GovernanceBoundary(conn)
    pending = boundary.intercept_and_evaluate(payload(8000, 'pending'), scope)
    assert pending['verdict'] == 'APPROVAL_REQUIRED'
    assert boundary.intercept_and_evaluate(payload(3000, 'first'), scope)['executed']
    with pytest.raises(ApprovalError):
        decide_approval(conn, pending['action_id'], 'approve', 'reviewer')
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 22000
    conn.close()


def test_concurrent_distinct_requests_share_scope_budget(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = str(tmp_path / 'sandbox.db')
    conn = init_db(path)
    scope = scope_for(conn, amount=4000)
    conn.close()
    def submit(key):
        db = get_connection(path)
        try:
            return GovernanceBoundary(db).intercept_and_evaluate(payload(3000, key), scope)['verdict']
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, ('first', 'second')))
    assert sorted(outcomes) == ['ALLOWED', 'BLOCKED']
    conn = get_connection(path)
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 22000
    conn.close()


def test_approval_uses_its_own_action_key_despite_predictable_key_collision(tmp_path):
    from app.approval.service import decide_approval
    from app.policy.models import PolicyConfig
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn, amount=6000)
    pending = GovernanceBoundary(conn).intercept_and_evaluate(payload(6000, 'original-request'), scope)
    assert pending['verdict'] == 'APPROVAL_REQUIRED'
    other = scope.model_copy(update={'scope_id': 'other-scope'})
    save_task_scope(conn, **other.model_dump(mode='json'))
    collision_key = f"idemp_appr_{pending['action_id']}"
    other_action = GovernanceBoundary(conn, PolicyConfig(auto_allow_threshold=10000)).intercept_and_evaluate(
        payload(6000, collision_key), other)
    assert other_action['executed']
    approved = decide_approval(conn, pending['action_id'], 'approve', 'reviewer')
    assert approved['refund']['action_id'] == pending['action_id']
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 13000
    conn.close()


def test_approval_fails_closed_if_action_request_no_longer_matches(tmp_path):
    from app.approval.service import decide_approval, ApprovalError
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn, amount=6000)
    pending = GovernanceBoundary(conn).intercept_and_evaluate(payload(6000, 'original-request'), scope)
    conn.execute("UPDATE action_requests SET fingerprint='changed' WHERE action_id=?", (pending['action_id'],))
    conn.commit()
    with pytest.raises(ApprovalError):
        decide_approval(conn, pending['action_id'], 'approve', 'reviewer')
    assert conn.execute('SELECT status FROM pending_actions WHERE action_id=?', (pending['action_id'],)).fetchone()[0] == 'pending'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000
    conn.close()


def test_pending_request_replay_and_changed_payload_are_rejected(tmp_path):
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn)
    first = GovernanceBoundary(conn).intercept_and_evaluate(payload(10000), scope)
    assert first['verdict'] == 'APPROVAL_REQUIRED'
    with pytest.raises(DuplicateIdempotencyError):
        GovernanceBoundary(conn).intercept_and_evaluate(payload(10000), scope)
    with pytest.raises(DuplicateIdempotencyError):
        GovernanceBoundary(conn).intercept_and_evaluate(payload(20000), scope)
    assert conn.execute('SELECT count(*) FROM pending_actions').fetchone()[0] == 1
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000
    conn.close()


def test_executed_key_remains_reserved_after_reset(tmp_path):
    from app.sandbox.service import reset_synthetic_data
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn)
    assert GovernanceBoundary(conn).intercept_and_evaluate(payload(1000), scope)['executed']
    reset_synthetic_data(conn)
    scope = scope_for(conn)
    with pytest.raises(DuplicateIdempotencyError):
        GovernanceBoundary(conn).intercept_and_evaluate(payload(1000), scope)
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000
    conn.close()


def test_concurrent_requests_with_same_key_produce_one_pending_action(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = str(tmp_path / 'sandbox.db')
    conn = init_db(path)
    scope = scope_for(conn)
    conn.close()
    def submit():
        db = get_connection(path)
        try:
            try:
                return GovernanceBoundary(db).intercept_and_evaluate(payload(10000), scope)['verdict']
            except DuplicateIdempotencyError:
                return 'DUPLICATE'
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(outcomes) == ['APPROVAL_REQUIRED', 'DUPLICATE']
    conn = get_connection(path)
    assert conn.execute('SELECT count(*) FROM pending_actions').fetchone()[0] == 1
    conn.close()


def test_legacy_migration_keeps_refunds_and_reserves_existing_keys(tmp_path):
    from app.sandbox.service import execute_sandbox_refund, reset_synthetic_data
    path = str(tmp_path / 'legacy.db')
    conn = init_db(path)
    execute_sandbox_refund(conn, 'ORD-101', 1000, 'USD', 'card_visa_4242', 'legacy-key')
    conn.execute('DROP TABLE action_requests')
    conn.execute('DROP TABLE policy_config')
    conn.commit()
    conn.close()
    conn = init_db(path)
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 24000
    assert conn.execute('SELECT count(*) FROM refunds').fetchone()[0] == 1
    reset_synthetic_data(conn)
    scope = scope_for(conn)
    with pytest.raises(DuplicateIdempotencyError):
        GovernanceBoundary(conn).intercept_and_evaluate(payload(1000, 'legacy-key'), scope)
    conn.close()


def test_legacy_pending_actions_expire_on_registry_migration(tmp_path):
    path = str(tmp_path / 'legacy-pending.db')
    conn = init_db(path)
    scope_for(conn)
    conn.execute("INSERT INTO pending_actions (action_id,tool,arguments,fingerprint,task_scope_id,status) VALUES ('old','refund_order','{}','old','durable-scope','pending')")
    conn.execute('DROP TABLE action_requests')
    conn.commit()
    conn.close()
    conn = init_db(path)
    assert conn.execute("SELECT status FROM pending_actions WHERE action_id='old'").fetchone()[0] == 'expired'
    conn.close()


def test_scope_budget_upgrade_expires_old_authority_preserves_history(tmp_path):
    path = str(tmp_path / 'old-budget.db')
    conn = init_db(path)
    scope = scope_for(conn, amount=4000)
    assert GovernanceBoundary(conn).intercept_and_evaluate(payload(3000, 'old'), scope)['executed']
    conn.execute('DROP TABLE IF EXISTS schema_migrations')
    conn.commit()
    conn.close()
    conn = init_db(path)
    result = GovernanceBoundary(conn).intercept_and_evaluate(payload(1000, 'new'), scope)
    assert result['verdict'] == 'BLOCKED'
    assert conn.execute('SELECT count(*) FROM refunds').fetchone()[0] == 1
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 22000
    conn.close()


def test_registry_recovery_expires_existing_scopes(tmp_path):
    path = str(tmp_path / 'registry-recovery.db')
    conn = init_db(path)
    scope = scope_for(conn, amount=4000)
    assert GovernanceBoundary(conn).intercept_and_evaluate(payload(3000, 'old'), scope)['executed']
    conn.execute('DROP TABLE action_requests')
    conn.commit()
    conn.close()
    conn = init_db(path)
    result = GovernanceBoundary(conn).intercept_and_evaluate(payload(1000, 'new'), scope)
    assert result['verdict'] == 'BLOCKED'
    assert conn.execute('SELECT count(*) FROM refunds').fetchone()[0] == 1
    conn.close()


def test_policy_shared_between_connections_and_restart(tmp_path):
    from app.policy.storage import load_policy, save_policy
    path = str(tmp_path / 'sandbox.db')
    first = init_db(path)
    policy = load_policy(first)
    policy.hard_ceiling_threshold = 9000
    save_policy(first, policy)
    first.close()
    second = init_db(path)
    assert load_policy(second).hard_ceiling_threshold == 9000
    scope = scope_for(second)
    result = GovernanceBoundary(second).intercept_and_evaluate(payload(10000), scope)
    assert result['verdict'] == 'BLOCKED'
    second.execute('DELETE FROM policy_config')
    second.commit()
    second.close()
    third = init_db(path)
    assert load_policy(third) is None
    third.close()


def test_deleted_scope_cannot_authorize_stale_request(tmp_path):
    conn = init_db(str(tmp_path / 'sandbox.db'))
    scope = scope_for(conn)
    conn.execute('DELETE FROM task_scopes WHERE scope_id = ?', (scope.scope_id,))
    conn.commit()
    result = GovernanceBoundary(conn).intercept_and_evaluate(payload(1000), scope)
    assert result['verdict'] == 'BLOCKED'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000
    conn.close()


@pytest.mark.asyncio
async def test_mcp_uses_updated_policy(tmp_path):
    import json
    from app.governance.mcp_server import create_governed_mcp_server
    from app.policy.storage import load_policy, save_policy
    path = str(tmp_path / 'sandbox.db')
    conn = init_db(path)
    scope_for(conn)
    server = create_governed_mcp_server(conn, authenticated_caller='operator')
    other = get_connection(path)
    policy = load_policy(other)
    policy.hard_ceiling_threshold = 9000
    save_policy(other, policy)
    other.close()
    response = await server.call_tool('refund_order', {
        'order_id': 'ORD-101', 'amount': 10000, 'currency': 'USD',
        'destination': 'card_visa_4242', 'reason': 'test', 'scope_id': 'durable-scope',
        'idempotency_key': 'mcp-key',
    })
    assert json.loads(response.content[0].text)['verdict'] == 'BLOCKED'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000
    conn.close()
