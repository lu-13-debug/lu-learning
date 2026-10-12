"""客户工单接口：2026.10 个人接口测试练习的本地被测服务。"""
import argparse
import json
import secrets
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DEMO_USERS = {"alice": "demo123", "bob": "demo123"}
TRANSITIONS = {"open": "in_progress", "in_progress": "resolved"}


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON 字段重复")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError("JSON 不允许 NaN 或 Infinity")


class TicketHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, code, value):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error_json(self, code, message):
        self.send_json(code, {"error": message})

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("请求体大小不合法")
            body = json.loads(self.rfile.read(length).decode("utf-8"),
                              object_pairs_hook=strict_object, parse_constant=reject_constant)
            if not isinstance(body, dict):
                raise ValueError("请求体应为 JSON 对象")
            return body
        except (ValueError, UnicodeError):
            self.error_json(400, "JSON 格式或请求体不合法")
            return None

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def dispatch(self, method):
        parsed = urlsplit(self.path)
        with closing(sqlite3.connect(self.server.db_path, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            if method == "POST" and parsed.path == "/login":
                body = self.read_json()
                if body is None:
                    return
                username = body.get("username")
                if (not isinstance(username, str) or username not in DEMO_USERS
                        or DEMO_USERS[username] != body.get("password")):
                    return self.error_json(401, "用户名或密码错误")
                token = secrets.token_urlsafe(32)
                with conn:
                    conn.execute("INSERT INTO sessions(token,username) VALUES(?,?)", (token, username))
                return self.send_json(200, {"token": token, "username": username})

            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            session = conn.execute("SELECT username FROM sessions WHERE token=?", (token,)).fetchone()
            if session is None:
                return self.error_json(401, "请先登录")
            username = session["username"]

            if parsed.path == "/tickets" and method == "POST":
                body = self.read_json()
                if body is None:
                    return
                title = body.get("title")
                if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
                    return self.error_json(400, "标题去除首尾空白后须为 1 到 100 个字符")
                if "\x00" in title or any(0xD800 <= ord(char) <= 0xDFFF for char in title):
                    return self.error_json(400, "标题不允许 NUL 或孤立 Unicode 代理字符")
                with conn:
                    cursor = conn.execute("INSERT INTO tickets(owner,title,status) VALUES(?,?,?)",
                                          (username, title.strip(), "open"))
                row = conn.execute("SELECT * FROM tickets WHERE id=?", (cursor.lastrowid,)).fetchone()
                return self.send_json(201, dict(row))

            if parsed.path == "/tickets" and method == "GET":
                query = parse_qs(parsed.query, keep_blank_values=True)
                try:
                    if set(query) - {"page", "page_size"} or any(len(v) != 1 for v in query.values()):
                        raise ValueError("参数重复或未知")
                    page = int(query.get("page", ["1"])[0])
                    size = int(query.get("page_size", ["10"])[0])
                    if page < 1 or page > 1000000 or not 1 <= size <= 100:
                        raise ValueError("分页越界")
                except ValueError:
                    return self.error_json(400, "分页参数不合法")
                total = conn.execute("SELECT COUNT(*) FROM tickets WHERE owner=?", (username,)).fetchone()[0]
                rows = conn.execute("SELECT * FROM tickets WHERE owner=? ORDER BY id LIMIT ? OFFSET ?",
                                    (username, size, (page - 1) * size)).fetchall()
                return self.send_json(200, {"items": [dict(row) for row in rows], "total": total,
                                            "page": page, "page_size": size})

            parts = parsed.path.strip("/").split("/")
            if len(parts) != 2 or parts[0] != "tickets" or not parts[1].isascii() or not parts[1].isdigit():
                return self.error_json(404, "接口不存在")
            ticket_id = int(parts[1])
            if ticket_id > 9223372036854775807:
                return self.error_json(404, "工单不存在")
            # 写操作先取 SQLite 写锁，再读取状态，避免并发请求依据旧状态更新。
            if method == "PATCH":
                conn.execute("BEGIN IMMEDIATE")
            ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if ticket is None:
                return self.error_json(404, "工单不存在")
            if ticket["owner"] != username:
                return self.error_json(403, "无权访问他人工单")
            if method == "GET":
                return self.send_json(200, dict(ticket))
            if method != "PATCH":
                return self.error_json(405, "请求方法不支持")
            body = self.read_json()
            if body is None:
                return
            if TRANSITIONS.get(ticket["status"]) != body.get("status") or body.get("status") is None:
                return self.error_json(409, "工单状态流转不合法")
            with conn:
                conn.execute("UPDATE tickets SET status=? WHERE id=?", (body["status"], ticket_id))
            updated = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            self.send_json(200, dict(updated))


def create_server(db_path, port=8000):
    db_path = Path(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tickets(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 100),
                    status TEXT NOT NULL CHECK(status IN ('open','in_progress','resolved'))
                );
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, username TEXT NOT NULL);
            """)
    server = ThreadingHTTPServer(("127.0.0.1", port), TicketHandler)
    server.db_path = db_path
    return server


def main():
    parser = argparse.ArgumentParser(description="客户工单接口个人练习服务")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=Path(__file__).parent / "tickets.sqlite3")
    args = parser.parse_args()
    server = create_server(args.db, args.port)
    print(f"个人练习服务：http://127.0.0.1:{server.server_port}，Ctrl+C 停止", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
