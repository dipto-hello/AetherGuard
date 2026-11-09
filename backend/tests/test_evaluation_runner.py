from app.evaluation import runner
from app.sandbox.db import init_db


def test_evaluation_uses_isolated_database_and_checks_real_effects():
    conn = init_db(":memory:")
    before = [tuple(row) for row in conn.execute("SELECT * FROM orders ORDER BY id")]
    report = runner.run_evaluation_suite()
    after = [tuple(row) for row in conn.execute("SELECT * FROM orders ORDER BY id")]
    assert before == after
    assert report["total_cases"] == len(report["cases"])
    for result in report["cases"]:
        assert "expected_backend_effect" in result
        assert "actual_backend_effect" in result
    missing_policy = next(case for case in report["cases"] if case["case_id"] == "CASE-09")
    assert "FAIL_CLOSED" in missing_policy["reason"]
    assert report["false_positive_rate"] == 0.0
    assert report["false_negative_rate"] == 0.0
    conn.close()


def test_evaluation_measures_failed_decisions_and_backend_effects(monkeypatch):
    case = dict(runner.EVALUATION_CASES[0])
    case["expected_verdict"] = "BLOCKED"
    case["category"] = "adversarial_test"
    case["expected_backend_effect"] = "zero_deduction"
    monkeypatch.setattr(runner, "EVALUATION_CASES", [case])
    report = runner.run_evaluation_suite()
    assert report["failed_cases"] == 1
    assert report["false_negative_rate"] == 100.0
    assert report["unauthorized_backend_writes"] == 1
    assert report["cases"][0]["actual_backend_effect"] == "deducted_4000"


def test_fresh_database_is_seeded_without_resetting_existing_data(tmp_path):
    path = str(tmp_path / "sandbox.db")
    conn = init_db(path)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 4
    conn.execute("UPDATE orders SET refundable_amount = 123 WHERE id = 'ORD-101'")
    conn.commit()
    conn.close()
    conn = init_db(path)
    assert conn.execute("SELECT refundable_amount FROM orders WHERE id = 'ORD-101'").fetchone()[0] == 123
    conn.close()


def test_mcp_startup_does_not_reset_an_existing_empty_database(tmp_path, monkeypatch):
    from app import mcp_entrypoint

    path = str(tmp_path / "sandbox.db")
    conn = init_db(path)
    conn.execute("DELETE FROM orders")
    conn.commit()
    conn.close()
    monkeypatch.setenv("AETHERGUARD_DB_PATH", path)

    class Server:
        def run(self, transport):
            assert transport == "stdio"

    monkeypatch.setattr(mcp_entrypoint, "create_governed_mcp_server", lambda conn, *a, **kw: Server())
    mcp_entrypoint.main()
    conn = init_db(path)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    conn.close()
