"""Keep API tests away from the user's persistent sandbox."""
import os
import tempfile
import pytest
from pathlib import Path

_test_data = tempfile.TemporaryDirectory(prefix="aetherguard-tests-")
os.environ["AETHERGUARD_DB_PATH"] = str(Path(_test_data.name) / "sandbox.db")
os.environ["AETHERGUARD_OPERATOR_TOKEN"] = "test-only-operator-token"
os.environ.pop("GEMINI_API_KEY", None)


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
