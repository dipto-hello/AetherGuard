"""Keep API tests away from the user's persistent sandbox."""
import os
import tempfile
from pathlib import Path

_test_data = tempfile.TemporaryDirectory(prefix="aetherguard-tests-")
os.environ["AETHERGUARD_DB_PATH"] = str(Path(_test_data.name) / "sandbox.db")
os.environ["AETHERGUARD_OPERATOR_TOKEN"] = "test-only-operator-token"
os.environ.pop("GEMINI_API_KEY", None)


def pytest_unconfigure(config):
    _test_data.cleanup()
