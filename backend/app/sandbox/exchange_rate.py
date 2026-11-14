"""USD/BDT quotes shared by the synthetic refund policy and dashboard."""
from datetime import datetime, timezone
from decimal import Decimal
from http.client import HTTPException
from json import load
from math import isfinite
from threading import Lock
from time import monotonic
from urllib.request import urlopen

_URL = "https://open.er-api.com/v6/latest/USD"
# shortcut: dated public reference for offline demos, replace with a persisted quote for deployments.
_quote = {"bdt_per_usd": 124.42, "as_of": "2026-11-10", "source": "bangladesh_bank", "stale": True}
REFERENCE_RATE_MICROS = 124_420_000
# The live quote sets refund limits, so an upstream value outside this band is ignored.
_RATE_BAND = (100, 160)
_refresh_after = 0.0
_lock = Lock()


def get_policy_rate_micros():
    return int(Decimal(str(get_display_quote()["bdt_per_usd"])) * 1_000_000)


def get_display_quote():
    global _quote, _refresh_after
    with _lock:
        if monotonic() >= _refresh_after:
            try:
                with urlopen(_URL, timeout=3) as response:
                    data = load(response)
                rate = data["rates"]["BDT"]
                if data["result"] != "success" or data["base_code"] != "USD" or type(rate) not in (int, float) or not isfinite(rate) or not _RATE_BAND[0] <= rate <= _RATE_BAND[1]:
                    raise ValueError("Invalid USD/BDT quote")
                rate = round(rate, 6)
                date = datetime.fromtimestamp(data["time_last_update_unix"], timezone.utc).date().isoformat()
                _quote = {"bdt_per_usd": rate, "as_of": date, "source": "exchange_rate_api", "stale": False}
                _refresh_after = monotonic() + 3600
            except (OSError, HTTPException, ValueError, TypeError, KeyError, OverflowError):
                _quote = {**_quote, "stale": True}
                _refresh_after = monotonic() + 300
        return dict(_quote)
