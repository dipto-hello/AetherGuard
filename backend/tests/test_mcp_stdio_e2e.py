"""
End-to-End Tests for AetherGuard Governed MCP Server over stdio transport.
Verifies external MCP client interoperability via the official MCP SDK.
"""
import pytest
import sys
import os
import json
import tempfile
import asyncio
from datetime import datetime, timedelta, timezone
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.approval.service import decide_approval


@pytest.mark.asyncio
async def test_concurrent_stdio_refunds_respect_scope_budget(temp_db_path):
    conn = init_db(temp_db_path)
    save_task_scope(conn, scope_id='concurrent', operator_id='test', order_id='ORD-101',
                    allowed_action='refund_order', max_amount=4000, allowed_currency='USD',
                    allowed_destination='card_visa_4242',
                    expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
    conn.close()
    params = StdioServerParameters(command=sys.executable, args=['-m', 'app.mcp_entrypoint'],
                                   env={**os.environ, 'AETHERGUARD_DB_PATH': temp_db_path})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            async def refund(key):
                result = await session.call_tool('refund_order', {
                    'order_id': 'ORD-101', 'amount': 3000, 'currency': 'USD',
                    'destination': 'card_visa_4242', 'reason': 'synthetic',
                    'scope_id': 'concurrent', 'idempotency_key': key,
                })
                assert not result.is_error
                return json.loads(result.content[0].text)['verdict']
            outcomes = await asyncio.gather(refund('one'), refund('two'))
    assert sorted(outcomes) == ['ALLOWED', 'BLOCKED']
    conn = init_db(temp_db_path)
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 22000
    conn.close()

@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    conn = init_db(path)
    reset_synthetic_data(conn)
    conn.close()
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

@pytest.mark.asyncio
async def test_mcp_stdio_tool_discovery_and_order_lookup(temp_db_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_entrypoint"],
        env={**os.environ, "AETHERGUARD_DB_PATH": temp_db_path}
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            assert init_res is not None

            # Tool discovery
            tools_list = await session.list_tools()
            tool_names = [t.name for t in tools_list.tools]
            assert "lookup_order" in tool_names
            assert "refund_order" in tool_names

            # Tool call: lookup_order
            call_res = await session.call_tool("lookup_order", {"order_id": "ORD-101"})
            assert not call_res.is_error
            data = json.loads(call_res.content[0].text)
            assert data["order_id"] == "ORD-101"
            assert data["customer_name"] == "Rahim Chowdhury"
            assert data["refundable_amount"] == 25000
            assert data["original_destination"] == "card_visa_4242"

@pytest.mark.asyncio
async def test_mcp_stdio_refund_blocked_without_scope(temp_db_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_entrypoint"],
        env={**os.environ, "AETHERGUARD_DB_PATH": temp_db_path}
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Attempt refund without trusted scope
            call_res = await session.call_tool(
                "refund_order",
                {
                    "order_id": "ORD-101",
                    "amount": 2000,
                    "currency": "USD",
                    "destination": "card_visa_4242",
                    "reason": "Unscoped refund attempt", "idempotency_key": "stdio-unscoped"
                }
            )
            assert not call_res.is_error
            result = json.loads(call_res.content[0].text)
            assert result["verdict"] == "BLOCKED"
            assert result["executed"] is False
            assert "OUTSIDE_TRUSTED_TASK_SCOPE" in result["reason"]

    # Verify sandbox state untouched
    conn = init_db(temp_db_path)
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 25000
    conn.close()

@pytest.mark.asyncio
async def test_mcp_stdio_refund_allowed_with_scope_executes(temp_db_path):
    # Pre-grant trusted task scope
    conn = init_db(temp_db_path)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-stdio-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    conn.close()

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_entrypoint"],
        env={**os.environ, "AETHERGUARD_DB_PATH": temp_db_path}
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            call_res = await session.call_tool(
                "refund_order",
                {
                    "order_id": "ORD-101",
                    "amount": 3500,  # $35.00 <= $50 auto-allow
                    "currency": "USD",
                    "destination": "card_visa_4242",
                    "reason": "Legitimate discount concession",
                    "scope_id": "scope-stdio-01", "idempotency_key": "stdio-allow"
                }
            )
            assert not call_res.is_error
            result = json.loads(call_res.content[0].text)
            assert result["verdict"] == "ALLOWED"
            assert result["executed"] is True
            assert result["refund"]["amount"] == 3500

    # Verify physical sandbox deduction
    conn = init_db(temp_db_path)
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 21500  # 25000 - 3500
    conn.close()

@pytest.mark.asyncio
async def test_mcp_stdio_approval_required_and_resolution(temp_db_path):
    # Pre-grant scope for up to $300
    conn = init_db(temp_db_path)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-stdio-02",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    conn.close()

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_entrypoint"],
        env={**os.environ, "AETHERGUARD_DB_PATH": temp_db_path}
    )
    action_id = None

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Propose $150 refund ($150 > $50 auto-allow, <= $300 scope)
            call_res = await session.call_tool(
                "refund_order",
                {
                    "order_id": "ORD-101",
                    "amount": 15000,
                    "currency": "USD",
                    "destination": "card_visa_4242",
                    "reason": "Damaged goods return",
                    "scope_id": "scope-stdio-02", "idempotency_key": "stdio-approval"
                }
            )
            assert not call_res.is_error
            result = json.loads(call_res.content[0].text)
            assert result["verdict"] == "APPROVAL_REQUIRED"
            assert result["executed"] is False
            assert result["pending_approval"] is True
            action_id = result["action_id"]

    # Sandbox remains untouched prior to human approval
    conn = init_db(temp_db_path)
    order_before = get_order(conn, "ORD-101")
    assert order_before["refundable_amount"] == 25000

    # Human operator reviews and approves via decide_approval
    resolution = decide_approval(
        conn=conn,
        action_id=action_id,
        decision="approve",
        reviewer_id="operator_dipto",
        reason="Approved after inspecting damaged item photos"
    )
    assert resolution["status"] == "executed"
    assert resolution["refund"]["amount"] == 15000

    # Verify sandbox is now updated
    order_after = get_order(conn, "ORD-101")
    assert order_after["refundable_amount"] == 10000  # 25000 - 15000
    conn.close()
