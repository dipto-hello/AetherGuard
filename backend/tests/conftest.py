"""Keep API tests away from the user's persistent sandbox."""
import os
import tempfile
import pytest
from pathlib import Path

_test_data = tempfile.TemporaryDirectory(prefix="aetherguard-tests-")
os.environ["AETHERGUARD_DB_PATH"] = str(Path(_test_data.name) / "sandbox.db")
os.environ["AETHERGUARD_OPERATOR_TOKEN"] = "test-only-operator-token"
os.environ.pop("GEMINI_API_KEY", None)


@pytest.fixture
def stub_ticket_provider(monkeypatch):
    from app.agent.core import SupportAgent
    from tests.offline_ticket_fixture import OfflineTicketFixture

    provider = OfflineTicketFixture()
    live_parser = SupportAgent._parse_ticket_llm
    test_key = "offline-test-provider"

    def parse(agent, ticket_text, *, api_key=None):
        if api_key == test_key:
            return provider.propose(ticket_text)
        return live_parser(agent, ticket_text, api_key=api_key)

    monkeypatch.setenv("GEMINI_API_KEY", test_key)
    monkeypatch.setattr(SupportAgent, "_parse_ticket_llm", parse)


@pytest.fixture(autouse=True)
def offline_exchange_rate(monkeypatch):
    """Tests never reach the live rate provider; they use the dated reference rate."""
    from app.sandbox import exchange_rate

    def offline(url, timeout):
        raise OSError("network disabled in tests")

    monkeypatch.setattr(exchange_rate, "urlopen", offline)
    monkeypatch.setattr(exchange_rate, "_quote", dict(exchange_rate._quote))
    monkeypatch.setattr(exchange_rate, "_refresh_after", 0)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    try:
        from app.main import _RATE_LIMITS
        _RATE_LIMITS.clear()
    except ImportError:
        pass
    yield
    try:
        from app.main import _RATE_LIMITS
        _RATE_LIMITS.clear()
    except ImportError:
        pass


def pytest_unconfigure(config):
    _test_data.cleanup()
