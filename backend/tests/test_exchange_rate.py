from app.sandbox import exchange_rate
import pytest


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
