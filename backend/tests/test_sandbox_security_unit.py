import unittest
import os
import tempfile
import threading

from app.sandbox.db import get_connection, init_db
from app.sandbox.service import (
    DuplicateIdempotencyError, execute_sandbox_refund, get_order, reset_synthetic_data, save_task_scope,
)


class SandboxIdempotencyTests(unittest.TestCase):
    def test_concurrent_distinct_refunds_do_not_lose_balance_updates(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = os.path.join(tempdir, "sandbox.db")
            conn = init_db(db_path)
            reset_synthetic_data(conn)
            conn.close()
            barrier = threading.Barrier(2, timeout=5)
            outcomes = []

            class CursorAtReadBarrier:
                def __init__(self, cursor):
                    self.cursor = cursor

                def fetchone(self):
                    row = self.cursor.fetchone()
                    barrier.wait()
                    return row

            class ConnectionAtReadBarrier:
                def __init__(self, conn):
                    self.conn = conn

                @property
                def in_transaction(self):
                    return self.conn.in_transaction

                def execute(self, sql, *args):
                    cursor = self.conn.execute(sql, *args)
                    return CursorAtReadBarrier(cursor) if sql.strip() == "SELECT * FROM orders WHERE id = ?" else cursor

                def __enter__(self):
                    self.conn.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.conn.__exit__(*args)

            def refund(key):
                conn = get_connection(db_path)
                try:
                    result = execute_sandbox_refund(ConnectionAtReadBarrier(conn), "ORD-101", 1000,
                                                    "USD", "card_visa_4242", key)
                    outcomes.append(result)
                except Exception as error:
                    outcomes.append(error)
                finally:
                    conn.close()

            threads = [threading.Thread(target=refund, args=(key,)) for key in ("one", "two")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len(outcomes), 2)
            self.assertTrue(all(isinstance(result, dict) for result in outcomes), repr(outcomes))
            conn = get_connection(db_path)
            try:
                self.assertEqual(get_order(conn, "ORD-101")["refundable_amount"], 23000)
                self.assertEqual(conn.execute("SELECT count(*) FROM refunds").fetchone()[0], 2)
            finally:
                conn.close()

    def test_refund_does_not_commit_callers_transaction(self):
        conn = init_db(":memory:")
        self.addCleanup(conn.close)
        reset_synthetic_data(conn)
        conn.execute("BEGIN")
        execute_sandbox_refund(conn, "ORD-101", 1000, "USD", "card_visa_4242", "rollback")
        conn.rollback()
        self.assertEqual(get_order(conn, "ORD-101")["refundable_amount"], 25000)
        self.assertEqual(conn.execute("SELECT count(*) FROM refunds").fetchone()[0], 0)

    def test_reset_invalidates_scopes_and_pending_actions(self):
        conn = init_db(":memory:")
        self.addCleanup(conn.close)
        reset_synthetic_data(conn)
        save_task_scope(conn, "scope", "operator", "ORD-101", "refund_order", 5000,
                        "USD", "card_visa_4242", "2099-01-01T00:00:00+00:00")
        with conn:
            conn.execute("INSERT INTO pending_actions (action_id,tool,arguments,fingerprint,task_scope_id,status) VALUES ('a','refund_order','{}','hash','scope','pending')")
        reset_synthetic_data(conn)
        self.assertEqual(conn.execute("SELECT count(*) FROM task_scopes").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT status FROM pending_actions WHERE action_id='a'").fetchone()[0], "expired")

    def test_changed_payload_with_same_key_is_rejected(self):
        conn = init_db(":memory:")
        self.addCleanup(conn.close)
        reset_synthetic_data(conn)
        first = execute_sandbox_refund(conn, "ORD-101", 1000, "USD", "card_visa_4242", "same")
        self.assertEqual(first["id"], execute_sandbox_refund(conn, "ORD-101", 1000, "USD", "card_visa_4242", "same")["id"])
        with self.assertRaises(DuplicateIdempotencyError):
            execute_sandbox_refund(conn, "ORD-101", 2000, "USD", "card_visa_4242", "same")
        self.assertEqual(get_order(conn, "ORD-101")["refundable_amount"], 24000)
