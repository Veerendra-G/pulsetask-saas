import asyncio
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from psycopg2 import errors as pg_errors
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main  # noqa: E402
from models import TaskCreate, TaskUpdate, UserRegister  # noqa: E402


class FakeCursor:
    def __init__(self, fetchone_results=None, fetchall_results=None, execute_side_effect=None, rowcount=0):
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.execute_side_effect = execute_side_effect
        self.rowcount = rowcount
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if self.execute_side_effect:
            raise self.execute_side_effect

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self, cursor_obj):
        self.cursor_obj = cursor_obj
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class MainApiTests(unittest.TestCase):
    def test_get_db_closes_on_success_and_rolls_back_on_error(self):
        conn_ok = FakeConn(FakeCursor())
        with patch.object(main, "get_db_connection", return_value=conn_ok):
            gen = main.get_db()
            yielded = next(gen)
            self.assertIs(yielded, conn_ok)
            with self.assertRaises(StopIteration):
                next(gen)
        self.assertTrue(conn_ok.closed)
        self.assertFalse(conn_ok.rolled_back)

        conn_err = FakeConn(FakeCursor())
        with patch.object(main, "get_db_connection", return_value=conn_err):
            gen = main.get_db()
            next(gen)
            with self.assertRaises(RuntimeError):
                gen.throw(RuntimeError("boom"))
        self.assertTrue(conn_err.rolled_back)
        self.assertTrue(conn_err.closed)

    def test_register_validates_email_and_whitespace_password(self):
        conn = FakeConn(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            main.register(UserRegister(email="invalid-email", password="secret123", name="Test"), conn=conn)
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx2:
            main.register(UserRegister(email="a@example.com", password="      ", name="Test"), conn=conn)
        self.assertEqual(ctx2.exception.status_code, 400)

    def test_register_duplicate_returns_409_and_hides_internal_errors(self):
        conn_dup = FakeConn(FakeCursor(fetchone_results=[None]))
        with self.assertRaises(HTTPException) as ctx:
            main.register(UserRegister(email="dup@example.com", password="password123", name="Dup"), conn=conn_dup)
        self.assertEqual(ctx.exception.status_code, 409)

        conn_err = FakeConn(FakeCursor(execute_side_effect=RuntimeError("sensitive sql details")))
        with self.assertRaises(HTTPException) as ctx_err:
            main.register(UserRegister(email="ok@example.com", password="password123", name="Ok"), conn=conn_err)
        self.assertEqual(ctx_err.exception.status_code, 500)
        self.assertNotIn("sensitive sql details", ctx_err.exception.detail)

    def test_create_task_validation_and_unique_conflict(self):
        conn = FakeConn(FakeCursor())
        with self.assertRaises(HTTPException) as ctx_empty:
            main.create_task(TaskCreate(title="   "), current_user=None, conn=conn)
        self.assertEqual(ctx_empty.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_bad_id:
            main.create_task(TaskCreate(title="Valid", id="bad id!"), current_user=None, conn=conn)
        self.assertEqual(ctx_bad_id.exception.status_code, 400)

        conn_dup = FakeConn(FakeCursor(execute_side_effect=pg_errors.UniqueViolation("duplicate key")))
        with self.assertRaises(HTTPException) as ctx_dup:
            main.create_task(TaskCreate(title="Valid", id="task-1"), current_user=None, conn=conn_dup)
        self.assertEqual(ctx_dup.exception.status_code, 409)
        self.assertTrue(conn_dup.rolled_back)

    def test_update_task_enforces_ownership(self):
        owned_row = {
            "id": "task-owned",
            "title": "Secret",
            "description": "",
            "status": "todo",
            "priority": "medium",
            "project": "Engineering",
            "due_date": None,
            "tags": [],
            "user_id": "user-owner",
            "created_at": None,
        }

        # Guest cannot edit user-owned task
        conn_guest = FakeConn(FakeCursor(fetchone_results=[owned_row]))
        with self.assertRaises(HTTPException) as ctx_unauth:
            main.update_task("task-owned", TaskUpdate(title="Hacked"), current_user=None, conn=conn_guest)
        self.assertEqual(ctx_unauth.exception.status_code, 401)

        # Different user cannot edit user-owned task
        conn_other = FakeConn(FakeCursor(fetchone_results=[owned_row]))
        with self.assertRaises(HTTPException) as ctx_forbid:
            main.update_task(
                "task-owned",
                TaskUpdate(title="Hacked"),
                current_user={"id": "user-attacker"},
                conn=conn_other,
            )
        self.assertEqual(ctx_forbid.exception.status_code, 403)

        # Owner can edit
        updated_row = {**owned_row, "title": "Updated"}
        conn_owner = FakeConn(FakeCursor(fetchone_results=[owned_row, updated_row]))
        res = main.update_task(
            "task-owned",
            TaskUpdate(title="Updated"),
            current_user={"id": "user-owner"},
            conn=conn_owner,
        )
        self.assertEqual(res["title"], "Updated")
        self.assertTrue(conn_owner.committed)

    def test_delete_task_enforces_ownership(self):
        owned_row = {"id": "task-owned", "user_id": "user-owner"}

        conn_guest = FakeConn(FakeCursor(fetchone_results=[owned_row]))
        with self.assertRaises(HTTPException) as ctx_unauth:
            main.delete_task("task-owned", current_user=None, conn=conn_guest)
        self.assertEqual(ctx_unauth.exception.status_code, 401)

        conn_other = FakeConn(FakeCursor(fetchone_results=[owned_row]))
        with self.assertRaises(HTTPException) as ctx_forbid:
            main.delete_task("task-owned", current_user={"id": "user-other"}, conn=conn_other)
        self.assertEqual(ctx_forbid.exception.status_code, 403)

        conn_owner = FakeConn(FakeCursor(fetchone_results=[owned_row, {"id": "task-owned"}]))
        res = main.delete_task("task-owned", current_user={"id": "user-owner"}, conn=conn_owner)
        self.assertTrue(res["success"])
        self.assertTrue(conn_owner.committed)

    def test_clear_completed_tasks_scopes_guest_to_null_user_id(self):
        cursor_guest = FakeCursor(rowcount=2)
        conn_guest = FakeConn(cursor_guest)
        res_guest = main.clear_completed_tasks(current_user=None, conn=conn_guest)
        self.assertEqual(res_guest["deletedCount"], 2)
        query_guest, _ = cursor_guest.executed[0]
        self.assertIn("user_id IS NULL", query_guest)

        cursor_user = FakeCursor(rowcount=3)
        conn_user = FakeConn(cursor_user)
        res_user = main.clear_completed_tasks(current_user={"id": "user-1"}, conn=conn_user)
        self.assertEqual(res_user["deletedCount"], 3)
        query_user, params_user = cursor_user.executed[0]
        self.assertIn("user_id = %s", query_user)
        self.assertEqual(params_user, ("user-1",))

    def test_health_check_handles_db_failure_cleanly(self):
        with patch.object(main, "get_db_connection", side_effect=RuntimeError("db down")):
            res = main.health_check()
        self.assertEqual(res["status"], "degraded")
        self.assertIn("unavailable", res["database"])

    def test_model_enum_validation(self):
        with self.assertRaises(ValidationError):
            TaskCreate(title="Bad status", status="unknown")
        with self.assertRaises(ValidationError):
            TaskUpdate(priority="critical")

    def test_asgi_openapi_and_cors_config(self):
        # Verify OpenAPI schema builds cleanly without route or model errors
        async def fetch_openapi():
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/openapi.json",
                "raw_path": b"/api/openapi.json",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
            }
            messages = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            await main.app(scope, receive, send)
            return messages

        messages = asyncio.run(fetch_openapi())
        self.assertEqual(messages[0]["status"], 200)
        body = json.loads(b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body"))
        self.assertIn("/api/tasks", body["paths"])

        cors_mw = [m for m in main.app.user_middleware if m.cls is main.CORSMiddleware][0]
        self.assertFalse(cors_mw.kwargs["allow_credentials"])


if __name__ == "__main__":
    unittest.main()
