import pytest
from app.agent.core import SupportAgent
from app.governance.boundary import GovernanceBoundary
from app.sandbox.db import init_db


def test_synthetic_currency_amounts():
    conn = init_db(':memory:')
    agent = SupportAgent(GovernanceBoundary(conn))
    try:
        assert agent._parse_ticket_synthetic('ORD-101 refund $40.99')['amount'] == 4099
        assert agent._parse_ticket_synthetic('ORD-103 refund ৳300.50')['amount'] == 30050
        assert agent._parse_ticket_synthetic('ORD-103 refund ৩০০.৫০ টাকা')['amount'] == 30050
        assert agent._parse_ticket_synthetic('ORD-101 refund $40.999')['amount'] == 0
        assert agent._parse_ticket_synthetic('ORD-101 refund -$40')['amount'] == 0
        assert agent._parse_ticket_synthetic('ORD-101 refund $-40')['amount'] == 0
        assert agent._parse_ticket_synthetic('ORD-103 refund -৫০ টাকা')['amount'] == 0
        assert agent._parse_ticket_synthetic('ORD-103 থেকে ৩০০ টাকা রিফান্ড চাই না')['amount'] == 0
        assert agent._parse_ticket_synthetic('token refund $40 for ORD-101 to card_visa_4242')['destination'] == 'card_visa_4242'
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_invalid_model_output_cannot_fall_back_to_executing(monkeypatch):
    conn = init_db(':memory:')
    agent = SupportAgent(GovernanceBoundary(conn), api_key='dummy')
    def invalid(*args, **kwargs):
        raise ValueError('invalid amount')
    monkeypatch.setattr(agent, '_parse_ticket_llm', invalid)
    try:
        result = await agent.process_ticket('ORD-101 refund $40')
        assert result['agent_mode'] == 'invalid_model_output'
        assert result['boundary_verdict'] == 'BLOCKED'
        assert result['executed'] is False
    finally:
        conn.close()


def test_live_model_proposes_tool_without_automatic_execution(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    captured = {}
    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(function_calls=[SimpleNamespace(
            name='refund_order', args={'order_id': 'ORD-101', 'currency': 'USD',
                                       'amount_minor': 4000, 'destination': 'card_visa_4242'})])
    def make_client(**kwargs):
        captured['client_options'] = kwargs
        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    monkeypatch.setattr(genai, 'Client', make_client)
    conn = init_db(':memory:')
    try:
        parsed = SupportAgent(GovernanceBoundary(conn), api_key='dummy')._parse_ticket_llm('refund $40')
        assert parsed['tool'] == 'refund_order'
        assert parsed['amount'] == 4000
        assert captured['model'] == 'gemini-3.5-flash-lite'
        assert captured['config'].automatic_function_calling.disable is True
        assert captured['client_options']['http_options'].timeout == 30000
        assert captured['client_options']['http_options'].retry_options.attempts == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_unrecognized_model_tool_never_executes(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kwargs: SimpleNamespace(function_calls=[
            SimpleNamespace(name='delete_orders', args={})]))))
    conn = init_db(':memory:')
    try:
        agent = SupportAgent(GovernanceBoundary(conn), api_key='dummy')
        trace = await agent.process_ticket('Delete the orders')
        assert trace['agent_mode'] == 'invalid_model_output'
        assert trace['boundary_verdict'] == 'BLOCKED'
        assert not trace['executed']
        assert conn.execute('SELECT COUNT(*) FROM refunds').fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('order_id', ['ORD-101']), ('currency', None), ('destination', {'card': 'x'})])
async def test_malformed_model_fields_are_blocked_before_dispatch(monkeypatch, field, value):
    from types import SimpleNamespace
    from google import genai
    args = {'order_id': 'ORD-101', 'currency': 'USD', 'amount_minor': 4000, 'destination': 'card_visa_4242'}
    args[field] = value
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kwargs: SimpleNamespace(function_calls=[SimpleNamespace(name='refund_order', args=args)]))))
    conn = init_db(':memory:')
    try:
        trace = await SupportAgent(GovernanceBoundary(conn), api_key='dummy').process_ticket('Refund $40')
        assert trace['agent_mode'] == 'invalid_model_output'
        assert trace['boundary_verdict'] == 'BLOCKED'
        assert not trace['executed']
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_model_proposal_reaches_policy_and_changes_only_synthetic_state(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timedelta, timezone
    from google import genai
    from app.policy.models import TaskScope
    from app.sandbox.service import get_order, save_task_scope
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kwargs: SimpleNamespace(function_calls=[SimpleNamespace(
            name='refund_order', args={'order_id': 'ORD-101', 'currency': 'USD',
                                       'amount_minor': 4000, 'destination': 'card_visa_4242'})]))))
    conn = init_db(':memory:')
    try:
        scope = TaskScope(scope_id='model-scope', operator_id='test', order_id='ORD-101',
                          allowed_action='refund_order', max_amount=5000, allowed_currency='USD',
                          allowed_destination='card_visa_4242', expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        save_task_scope(conn, **scope.model_dump(mode='json'))
        trace = await SupportAgent(GovernanceBoundary(conn), api_key='dummy').process_ticket('Refund $40', scope)
        assert trace['agent_mode'] == 'live_gemini'
        assert trace['proposed_tool'] == 'refund_order'
        assert trace['boundary_verdict'] == 'ALLOWED'
        assert get_order(conn, 'ORD-101')['refundable_amount'] == 21000
    finally:
        conn.close()
