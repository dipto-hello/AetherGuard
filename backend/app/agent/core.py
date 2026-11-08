"""Bilingual support-ticket proposals for the governed synthetic sandbox."""
import re
import asyncio
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from decimal import Decimal, InvalidOperation

from app.governance.boundary import GovernanceBoundary
from app.sandbox.service import get_order, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.governance.mcp_server import create_governed_mcp_server
from mcp.client.client import Client

class SupportAgent:
    """
    Ticket processor using the governed MCP tool path.
    The in-process agent shares a database connection with the boundary.
    """
    def __init__(self, boundary: GovernanceBoundary, api_key: Optional[str] = None):
        self.boundary = boundary
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def _detect_language(self, text: str) -> str:
        """Detect if ticket contains Bengali script"""
        bengali_range = re.compile(r'[\u0980-\u09FF]')
        return "bn" if bengali_range.search(text) else "en"

    def _parse_ticket_synthetic(self, ticket_text: str) -> Dict[str, Any]:
        """
        High-fidelity deterministic parser for benchmark and offline evaluation.
        Accurately extracts order_id, currency, amount (in minor units), and destination.
        """
        lang = self._detect_language(ticket_text)
        
        # 1. Extract Order ID (e.g. ORD-101, ORD-102, ORD-103, ORD-104)
        order_match = re.search(r'(ORD-\d+)', ticket_text, re.IGNORECASE)
        order_id = order_match.group(1).upper() if order_match else None

        # 2. Extract Currency & Amount
        currency = "USD"
        amount_minor = 0

        # Check for BDT / Taka (English & Bengali)
        if "bdt" in ticket_text.lower() or "টাকা" in ticket_text or "৳" in ticket_text:
            currency = "BDT"
            # Match digits or Bengali numerals
            bengali_digits = {'০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4', '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'}
            normalized_text = "".join(bengali_digits.get(c, c) for c in ticket_text)
            amount_match = re.search(r'(?:৳\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:টাকা|bdt|৳))', normalized_text, re.IGNORECASE)
            if amount_match:
                amount_minor = self._minor_units(amount_match.group(1) or amount_match.group(2))
        else:
            # Match dollar amounts like $40, $250, $5,000, 40 dollars
            amount_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:dollars?|usd)', ticket_text, re.IGNORECASE)
            if amount_match:
                raw_amt = (amount_match.group(1) or amount_match.group(2)).replace(',', '')
                amount_minor = self._minor_units(raw_amt)

        if re.search(r'(?:[-−]\s*[$৳]\s*[\d০-৯]|[$৳]\s*[-−]\s*[\d০-৯]|[-−]\s*[\d০-৯][\d০-৯,.]*\s*(?:টাকা|bdt|usd|dollars?))', ticket_text, re.IGNORECASE):
            amount_minor = 0

        # shortcut: intent heuristics miss some phrasings; require review when reliable intent matters.
        if (not re.search(r'\brefund\b|রিফান্ড|ফেরত', ticket_text, re.IGNORECASE)
                or re.search(r"\b(?:no|not|never|without|don['’]?t|cannot|can['’]?t|withdrawn|withdraw|revoked|retracted)\b|চাই\s*না|দিবেন\s*না|করবেন\s*না|প্রত্যাহার", ticket_text, re.IGNORECASE)):
            amount_minor = 0

        # 3. Destination extraction / diversion detection
        destination = None
        # Check explicit destination patterns or diversion attempts
        dest_patterns = [
            r'\b(?:to|destination|wallet|account|address|card|into|হ্যাকারের|একাউন্টে|ওয়ালেটে|কার্ডে)\b\s*[:=]?\s*([a-zA-Z0-9_]{3,32})',
            r'(card_[a-zA-Z0-9_]+)',
            r'(bkash_[0-9]+)',
            r'(wire_[a-zA-Z0-9_]+)',
            r'(0x[a-fA-F0-9]{6,40})',
            r'(attacker_[a-zA-Z0-9_]+)',
            r'(hacker_[a-zA-Z0-9_]+)',
            r'(wallet_[a-zA-Z0-9_]+)'
        ]
        ignored_tokens = {"order", "dollars", "refund", "please", "urgent", "customer", "support", "taka", "usd", "bdt", "my"}
        for pattern in dest_patterns:
            m = re.search(pattern, ticket_text, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if cand.lower() not in ignored_tokens and len(cand) >= 3:
                    destination = cand
                    break

        if not destination and order_id:
            # Fall back to authoritative original payment destination from order
            order = get_order(self.boundary.conn, order_id)
            if order:
                destination = order["original_destination"]

        return {
            "order_id": order_id,
            "currency": currency,
            "amount": amount_minor,
            "destination": destination,
            "language": lang
        }

    @staticmethod
    def _minor_units(raw_amount: str) -> int:
        try:
            amount = Decimal(raw_amount.replace(',', '')) * 100
            return int(amount) if amount == amount.to_integral_value() else 0
        except (InvalidOperation, ValueError, OverflowError):
            return 0

    MODEL_PRIORITY_CHAIN = [
        "gemini-3.5-flash-lite",  # Primary choice (multimodal, 500 req/day)
        "gemini-3.1-flash-lite",  # Fallback 1 (multimodal, 500 req/day)
        "gemma-4-31b-it",         # Fallback 2 (high-volume text filter)
    ]

    def _parse_ticket_llm(self, ticket_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Get a model proposal; the SDK must never execute the tool itself. Follows priority fallback chain."""
        from google import genai
        from google.genai import types

        declaration = types.FunctionDeclaration(
            name="refund_order",
            description="Propose a refund for a customer support ticket; the server evaluates authorization.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "order_id": {"type": "STRING", "description": "The order identifier, e.g. ORD-101 or ORD-103"},
                    "currency": {"type": "STRING", "enum": ["USD", "BDT"], "description": "Currency code (USD or BDT)"},
                    "amount_minor": {
                        "type": "INTEGER",
                        "description": "Refund amount in integer minor currency units (e.g. cents for USD, poisha for BDT: $40 is 4000, $250 is 25000, ৳50 is 5000)",
                    },
                    "destination": {
                        "type": "STRING",
                        "description": "The refund destination account, card, or original payment method requested",
                    },
                },
                "required": ["order_id", "currency", "amount_minor", "destination"],
            },
        )
        client = genai.Client(
            api_key=api_key or self.api_key,
            http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)),
        )

        last_error = None
        for model_name in self.MODEL_PRIORITY_CHAIN:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=(
                        "Consider the following support ticket in English or Bengali. "
                        "Propose a refund only when the ticket requests one; use integer minor units (cents/poisha). "
                        "Do not invent an external destination.\nTicket:\n" + ticket_text
                    ),
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(function_declarations=[declaration])],
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                calls = response.function_calls or []
                if len(calls) != 1 or calls[0].name != "refund_order" or not isinstance(calls[0].args, dict):
                    raise ValueError(f"Model {model_name} did not return one supported refund proposal")
                data = calls[0].args
                if type(data.get("amount_minor")) is not int:
                    raise ValueError(f"Model {model_name} amount must be an integer number of minor units")
                if (
                    not isinstance(data.get("order_id"), str) or not data["order_id"]
                    or data.get("currency") not in ("USD", "BDT")
                    or not isinstance(data.get("destination"), str) or not data["destination"]
                ):
                    raise ValueError(f"Model {model_name} returned invalid refund fields")

                order_id = data.get("order_id")
                destination = data.get("destination", "").strip()

                generic_destinations = {
                    "original payment card", "original card", "original", "my card", "my account",
                    "original destination", "payment card", "default", "card", "original payment method",
                    "original account", "বিকাশ একাউন্ট", "বিকাশ", "কার্ড"
                }
                dest_lower = destination.lower()
                bengali_generic = ["আগের বিকাশ", "আগের কার্ড", "আমার বিকাশ", "আমার কার্ড", "আমার একাউন্ট", "বিকাশ নম্বর", "বিকাশ একাউন্ট", "বিকাশে", "বিকাশ"]
                if order_id and (dest_lower in generic_destinations or any(p in dest_lower for p in bengali_generic)):
                    order = get_order(self.boundary.conn, order_id)
                    if order and order.get("original_destination"):
                        destination = order["original_destination"]

                return {
                    "tool": calls[0].name,
                    "order_id": order_id,
                    "currency": data.get("currency"),
                    "amount": data["amount_minor"],
                    "destination": destination,
                    "language": self._detect_language(ticket_text),
                    "model_used": model_name,
                }
            except Exception as err:
                last_error = err
                continue

        raise last_error or ValueError("All priority models failed to return a valid proposal")

    async def process_ticket(
        self,
        ticket_text: str,
        task_scope: Optional[TaskScope] = None,
        force_mode: Optional[str] = None,
        api_key: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reads ticket, performs read-only order lookup, and dispatches proposed action
        through the Zero-Trust Governance Boundary.
        """
        mode = "synthetic_engine"
        parsed = None
        effective_key = api_key or self.api_key

        if effective_key and force_mode != "synthetic":
            try:
                parsed = await asyncio.to_thread(self._parse_ticket_llm, ticket_text, api_key=effective_key)
                model_tag = parsed.get("model_used", "gemini-3.5-flash-lite")
                mode = "live_gemini"
            except (ValueError, TypeError, KeyError, AttributeError):
                parsed = {"order_id": None, "currency": "USD", "amount": 0, "destination": None,
                          "language": self._detect_language(ticket_text)}
                mode = "invalid_model_output"
            except Exception:
                parsed = self._parse_ticket_synthetic(ticket_text)
                mode = "synthetic_fallback"
        else:
            parsed = self._parse_ticket_synthetic(ticket_text)

        order_id = parsed["order_id"]
        order = get_order(self.boundary.conn, order_id) if order_id else None

        # Build proposed tool call
        action_payload = {
            "tool": parsed.get("tool", "refund_order"),
            "arguments": {
                "order_id": order_id,
                "amount": parsed["amount"],
                "currency": parsed["currency"],
                "destination": parsed["destination"],
                "reason": "Customer support refund request"
            },
            "idempotency_key": idempotency_key or f"agent_ticket_{uuid.uuid4().hex}"
        }

        # Scope comes from the trusted operator, not from the ticket or model.
        tool_args = dict(action_payload['arguments'])
        tool_args['order_id'] = tool_args['order_id'] or ''
        tool_args['destination'] = tool_args['destination'] or ''
        tool_args['scope_id'] = task_scope.scope_id if task_scope else None
        tool_args['idempotency_key'] = action_payload['idempotency_key']
        server = create_governed_mcp_server(self.boundary.conn, self.boundary)
        async with Client(server) as client:
            response = await client.call_tool(action_payload['tool'], tool_args)
        if response.is_error or not response.content:
            raise RuntimeError('MCP refund tool failed; execution outcome must be checked before retry')
        evaluation = json.loads(response.content[0].text)
        if evaluation.get('error') == 'IDEMPOTENCY_KEY_REUSED':
            raise DuplicateIdempotencyError('Idempotency key has already been used; inspect the existing action')
        if 'verdict' not in evaluation:
            raise RuntimeError('MCP refund tool returned no decision; check execution outcome before retry')

        # Explicit visual pipeline stages
        pipeline_stages = [
            {
                "id": "stage_1",
                "name": "Support Ticket Received",
                "status": "completed",
                "details": f"Processed {parsed['language'].upper()} ticket ({len(ticket_text)} chars)"
            },
            {
                "id": "stage_2",
                "name": "Bilingual Agent Reasoning",
                "status": "completed",
                "details": f"Mode: {mode.replace('_', ' ').title()} | Extracted {order_id or 'Unknown'} ({parsed['currency']} {parsed['amount']/100:.2f})"
            },
            {
                "id": "stage_3",
                "name": "MCP Tool Proposal",
                "status": "completed",
                "details": "SDK client invoked the governed tool using in-memory transport"
            },
            {
                "id": "stage_4",
                "name": "Zero-Trust Policy & Task Scope Firewall",
                "status": "allowed" if evaluation["verdict"] == "ALLOWED" else ("approval" if evaluation["verdict"] == "APPROVAL_REQUIRED" else "blocked"),
                "details": evaluation["reason"]
            },
            {
                "id": "stage_5",
                "name": "Sandbox Enterprise DB Impact",
                "status": "executed" if evaluation["executed"] else ("pending" if evaluation.get("pending_approval") else "neutralized"),
                "details": f"Deducted {evaluation.get('refund', {}).get('currency', '')} {evaluation.get('refund', {}).get('amount', 0)/100:.2f}" if evaluation["executed"] else ("Awaiting Human Operator Approval" if evaluation.get("pending_approval") else "Zero backend mutation — database protected")
            }
        ]

        return {
            "ticket_text": ticket_text,
            "language": parsed["language"],
            "agent_mode": mode,
            "parsed_parameters": parsed,
            "order_state": {
                "order_id": order["id"] if order else None,
                "paid_amount": order["paid_amount"] if order else None,
                "refundable_amount": order["refundable_amount"] if order else None,
                "original_destination": order["original_destination"] if order else None
            } if order else None,
            "proposed_tool": action_payload["tool"],
            "boundary_verdict": evaluation["verdict"],
            "boundary_reason": evaluation["reason"],
            "executed": evaluation["executed"],
            "action_id": evaluation.get("action_id"),
            "fingerprint": evaluation.get("fingerprint"),
            "refund": evaluation.get("refund"),
            "pending_approval": evaluation.get("pending_approval", False),
            "transport": "mcp_in_memory",
            "pipeline_stages": pipeline_stages
        }
