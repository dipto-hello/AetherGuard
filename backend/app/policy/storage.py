"""Persistent, shared demo policy."""
from app.policy.models import PolicyConfig


def _valid(policy):
    return (policy.enforce_task_scope and policy.require_exact_destination_match
            and policy.auto_allow_threshold > 0
            and policy.hard_ceiling_threshold >= policy.auto_allow_threshold
            and set(policy.allowed_tools) <= {'refund_order', 'lookup_order'})


def load_policy(conn):
    try:
        row = conn.execute('SELECT config FROM policy_config WHERE id = 1').fetchone()
        if not row:
            return None
        policy = PolicyConfig.model_validate_json(row[0])
        if not _valid(policy):
            return None
        return policy
    except Exception:
        return None


def save_policy(conn, policy):
    if not _valid(policy):
        raise ValueError('Invalid policy thresholds or required controls')
    from contextlib import nullcontext
    with nullcontext() if conn.in_transaction else conn:
        cursor = conn.execute('UPDATE policy_config SET config = ? WHERE id = 1', (policy.model_dump_json(),))
        if cursor.rowcount != 1:
            raise ValueError('Policy configuration is unavailable')
