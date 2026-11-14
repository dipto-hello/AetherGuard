from app.sandbox import exchange_rate
import pytest


@pytest.mark.parametrize("bad_rate", [12442, 1.2442, 0.000001, 1_000_000])
def test_out_of_band_quote_keeps_reference_rate(monkeypatch, bad_rate):
    from io import BytesIO
    body = '{"result":"success","base_code":"USD","rates":{"BDT":%s},"time_last_update_unix":1794268800}' % bad_rate
    monkeypatch.setattr(exchange_rate, "urlopen", lambda url, timeout: BytesIO(body.encode()))
    assert exchange_rate.get_policy_rate_micros() == exchange_rate.REFERENCE_RATE_MICROS
    assert exchange_rate.get_display_quote()["source"] == "bangladesh_bank"


@pytest.mark.parametrize("failure", ["offline", "incomplete"])
def test_display_quote_cache_and_provider_failure(monkeypatch, failure):
    from http.client import IncompleteRead
    from io import BytesIO
    from urllib.error import URLError

    time = 1
    calls = []

    def upstream(url, timeout):
        calls.append(url)
        if len(calls) > 1:
            if failure == "incomplete":
                raise IncompleteRead(b'{"result"')
            raise URLError("offline")
        return BytesIO(b'{"result":"success","base_code":"USD","rates":{"BDT":125.25},"time_last_update_unix":1794268800}')

    monkeypatch.setattr(exchange_rate, "monotonic", lambda: time)
    monkeypatch.setattr(exchange_rate, "urlopen", upstream)
    monkeypatch.setattr(exchange_rate, "_refresh_after", 0)
    monkeypatch.setattr(exchange_rate, "_quote", dict(exchange_rate._quote))
    quote = exchange_rate.get_display_quote()
    assert quote["bdt_per_usd"] == 125.25 and not quote["stale"]
    assert exchange_rate.get_display_quote() == quote
    assert len(calls) == 1
    time += 3601
    assert exchange_rate.get_display_quote() == {**quote, "stale": True}
