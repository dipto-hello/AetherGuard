"""Deterministic provider double for existing governance tests. Never imported by the app."""
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from app.agent.core import SupportAgent


class OfflineTicketFixture:
    _BENGALI_DIGITS = SupportAgent._BENGALI_DIGITS
    _detect_language = SupportAgent._detect_language

    @staticmethod
    def _is_generic_destination(destination: Optional[str]) -> bool:
        """Identify generic or original payment placeholders that require authoritative enrichment."""
        if not destination or not destination.strip():
            return True
        dest_lower = destination.strip().lower()
        generic_destinations = {
            "original payment card", "original card", "original", "my card", "my account",
            "original destination", "payment card", "default", "card", "original payment method",
            "original account", "original visa card", "my original visa card", "কার্ড",
            "আগের বিকাশ", "আগের কার্ড", "আমার বিকাশ", "আমার কার্ড", "আমার একাউন্ট",
            "বিকাশ নম্বর", "বিকাশ একাউন্ট", "বিকাশে", "বিকাশ",
            "বিকাশ নম্বর (bkash number)", "আমার বিকাশ নম্বরে", "আমার বিকাশ একাউন্টে", "আগের বিকাশ একাউন্টে",
        }
        return dest_lower in generic_destinations

    _NON_ACTIONABLE_REFUND = re.compile(
        r'\b(?:no|not|never|don[\'’]?t|cannot|can[\'’]?t|do\s+not)\s+(?:want\s+(?:a\s+)?)?refund\b|'
        r'\brefund\b[^\w\n.?!]{0,30}\b(?:is\s+)?(?:not\s+needed|not\s+wanted|withdrawn|withdraw|revoked|retracted|cancelled|canceled)\b|'
        r'\b(?:refund\s+request\s+)?(?:withdrawn|withdraw|revoked|retracted)\b|'
        r'\b(?:no|without)\s+refund\b|'
        r'\b(?:maybe|perhaps|only if|what if|would it be possible|whether|if the customer)\b|'
        r'যদি|রাজি হলে|সম্মতি দিলে|হয়তো|সম্ভব কি|'
        r'(?:রিফান্ড|ফেরত|refund)\s+(?:না\s+(?:দিন|দেন|দিতে|করুন)|(?:দিতে|করতে)\s+(?:হবে|পারবেন)\s*না)|'
        r'চাই\s*না|দিবেন\s*না|করবেন\s*না|নেব\s*না|নিব\s*না|দরকার\s*নেই|প্রয়োজন\s*নেই|প্রত্যাহার',
        re.IGNORECASE
    )

    def _parse_ticket_synthetic(self, ticket_text: str) -> Dict[str, Any]:
        """
        High-fidelity deterministic parser for benchmark and offline evaluation.
        Accurately extracts order_id, currency, amount (in minor units), and destination.
        """
        lang = self._detect_language(ticket_text)

        # 1. Normalize Bengali numerals across the entire ticket first
        normalized_text = ticket_text.translate(self._BENGALI_DIGITS)

        # Extract Order ID (e.g. ORD-101, ORD-102, ORD-103, ORD-104)
        order_match = re.search(r'(ORD-\d+)', normalized_text, re.IGNORECASE)
        order_id = order_match.group(1).upper() if order_match else None

        # 2. Extract Currency & Amount
        currency = "USD"
        amount_minor = 0

        # Check for BDT / Taka (English & Bengali)
        if "bdt" in ticket_text.lower() or "টাকা" in ticket_text or "৳" in ticket_text:
            currency = "BDT"
            amount_match = re.search(r'(?:৳\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:টাকা|bdt|৳))', normalized_text, re.IGNORECASE)
            if amount_match:
                amount_minor = self._minor_units(amount_match.group(1) or amount_match.group(2))
        else:
            # Match dollar amounts like $40, $250, $5,000, 40 dollars
            amount_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:dollars?|usd)', normalized_text, re.IGNORECASE)
            if amount_match:
                raw_amt = (amount_match.group(1) or amount_match.group(2)).replace(',', '')
                amount_minor = self._minor_units(raw_amt)

        if re.search(r'(?:[-−]\s*[$৳]\s*[\d০-৯]|[$৳]\s*[-−]\s*[\d০-৯]|[-−]\s*[\d০-৯][\d০-৯,.]*\s*(?:টাকা|bdt|usd|dollars?))', ticket_text, re.IGNORECASE):
            amount_minor = 0

        if not re.search(r'\brefund\b|রিফান্ড|ফেরত', ticket_text, re.IGNORECASE) or self._NON_ACTIONABLE_REFUND.search(ticket_text):
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

        if destination and self._is_generic_destination(destination):
            destination = None

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


    def propose(self, ticket_text, *, api_key=None):
        proposal = self._parse_ticket_synthetic(ticket_text)
        if self._NON_ACTIONABLE_REFUND.search(ticket_text):
            proposal["needs_clarification"] = True
        return proposal
