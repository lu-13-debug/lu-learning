"""客户工单接口的真实 HTTP 集成测试（个人练习）。"""
import importlib.util
import json
import sqlite3
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

BASE = Path(__file__).resolve().parent


class TicketAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_available = importlib.util.find_spec("server") is not None
        if not cls.module_available:
            return
        from server import create_server
        cls.db_path = BASE / "test-tickets.sqlite3"
        cls.db_path.unlink(missing_ok=True)
        cls.server = create_server(cls.db_path, port=0)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        if not cls.module_available:
            return
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=3)
        cls.db_path.unlink(missing_ok=True)

    def setUp(self):
        self.assertTrue(self.module_available, "尚未实现被测服务 server.py")
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute("DELETE FROM tickets")
                conn.execute("DELETE FROM sessions")
        self.alice = self.login("alice")
        self.bob = self.login("bob")

    def request(self, method, path, body=None, token=None, raw=None):
        headers = {}
        data = None
        if body is not None or raw is not None:
            data = raw if raw is not None else json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            response = self.client.open(req, timeout=4)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def login(self, username):
        code, body = self.request("POST", "/login", {"username": username, "password": "demo123"})
        self.assertEqual(code, 200)
        return body["token"]

    def create(self, title="打印机无法连接", token=None):
        code, body = self.request("POST", "/tickets", {"title": title}, token or self.alice)
        self.assertEqual(code, 201)
        return body

    def test_01_login_success_and_unique_sessions(self):
        self.assertNotEqual(self.alice, self.login("alice"))
        self.assertNotEqual(self.alice, self.bob)

    def test_02_wrong_credentials_return_401(self):
        for credentials in ({"username": "alice", "password": "wrong"},
                            {"username": "unknown"}, {"username": "alice"},
                            {"username": ["alice"], "password": "demo123"}):
            with self.subTest(credentials=credentials):
                code, body = self.request("POST", "/login", credentials)
                self.assertEqual(code, 401)
                self.assertEqual(body["error"], "用户名或密码错误")

    def test_03_unauthenticated_and_forged_token_return_401(self):
        for token in (None, "forged-token"):
            with self.subTest(token=token):
                self.assertEqual(self.request("GET", "/tickets", token=token)[0], 401)

    def test_04_create_ticket_and_sql_persistence_match(self):
        ticket = self.create()
        with closing(sqlite3.connect(self.db_path)) as conn:
            stored = conn.execute("SELECT owner,title,status FROM tickets WHERE id=?", (ticket["id"],)).fetchone()
        self.assertEqual(stored, ("alice", "打印机无法连接", "open"))
        self.assertEqual(ticket["status"], "open")

    def test_05_title_length_inclusive_boundaries(self):
        for size in (1, 100):
            with self.subTest(size=size):
                self.assertEqual(self.create("工" * size)["title"], "工" * size)

    def test_06_empty_long_or_nonstring_title_rejected(self):
        for title in ("", "   ", "工" * 101, 123, None, "\u0000", "a\u0000b", "\ud800", "\udfff"):
            with self.subTest(title=title):
                self.assertEqual(self.request("POST", "/tickets", {"title": title}, self.alice)[0], 400)
        self.assertEqual(self.request("GET", "/tickets", token=self.alice)[1]["total"], 0)

    def test_07_list_pagination_is_ordered_and_has_total(self):
        created = [self.create(f"工单{i}") for i in range(3)]
        code, body = self.request("GET", "/tickets?page=2&page_size=2", token=self.alice)
        self.assertEqual(code, 200)
        self.assertEqual(body["total"], 3)
        self.assertEqual([t["id"] for t in body["items"]], [created[2]["id"]])
        self.assertEqual(self.request("GET", "/tickets?page=3&page_size=2", token=self.alice)[1]["items"], [])

    def test_08_invalid_pagination_rejected(self):
        for query in ("page=0", "page=x", "page_size=101", "page_size=-1", "page=1&page=2"):
            with self.subTest(query=query):
                self.assertEqual(self.request("GET", "/tickets?" + query, token=self.alice)[0], 400)

    def test_09_valid_state_flow_is_persisted(self):
        ticket = self.create()
        for status in ("in_progress", "resolved"):
            code, body = self.request("PATCH", f"/tickets/{ticket['id']}", {"status": status}, self.alice)
            self.assertEqual(code, 200)
            self.assertEqual(body["status"], status)
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT status FROM tickets WHERE id=?", (ticket["id"],)).fetchone()[0], "resolved")

    def test_10_illegal_transitions_do_not_change_database(self):
        ticket = self.create()
        for status in ("resolved", "open", "unknown"):
            with self.subTest(status=status):
                self.assertEqual(self.request("PATCH", f"/tickets/{ticket['id']}", {"status": status}, self.alice)[0], 409)
        self.assertEqual(self.request("GET", f"/tickets/{ticket['id']}", token=self.alice)[1]["status"], "open")

    def test_11_resolved_ticket_cannot_reopen(self):
        ticket = self.create()
        for status in ("in_progress", "resolved"):
            self.request("PATCH", f"/tickets/{ticket['id']}", {"status": status}, self.alice)
        self.assertEqual(self.request("PATCH", f"/tickets/{ticket['id']}", {"status": "open"}, self.alice)[0], 409)

    def test_12_missing_ticket_or_endpoint_return_404(self):
        self.assertEqual(self.request("GET", "/tickets/999999", token=self.alice)[0], 404)
        self.assertEqual(self.request("PATCH", "/tickets/999999", {"status": "in_progress"}, self.alice)[0], 404)
        self.assertEqual(self.request("GET", "/missing", token=self.alice)[0], 404)

    def test_13_users_cannot_read_or_modify_other_users_tickets(self):
        ticket = self.create()
        self.assertEqual(self.request("GET", "/tickets", token=self.bob)[1]["total"], 0)
        self.assertEqual(self.request("GET", f"/tickets/{ticket['id']}", token=self.bob)[0], 403)
        self.assertEqual(self.request("PATCH", f"/tickets/{ticket['id']}", {"status": "in_progress"}, self.bob)[0], 403)
        self.assertEqual(self.request("GET", f"/tickets/{ticket['id']}", token=self.alice)[1]["status"], "open")

    def test_14_malformed_duplicate_or_nonobject_json_return_400(self):
        for raw in (b'{broken', b'[]', b'{"title":"a","title":"b"}', b'\xff', b'{"title":NaN}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("POST", "/tickets", token=self.alice, raw=raw)[0], 400)

    def test_15_sql_injection_like_title_is_stored_as_plain_text(self):
        text = "'); DROP TABLE tickets; --"
        ticket = self.create(text)
        self.assertEqual(self.request("GET", f"/tickets/{ticket['id']}", token=self.alice)[1]["title"], text)
        self.assertEqual(self.request("GET", "/tickets", token=self.alice)[1]["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
