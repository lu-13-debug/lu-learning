"""本地自动化练习靶场。只监听127.0.0.1，不提供生产部署配置。"""
import argparse
import hmac
import json
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import Store


def make_handler(store):
    sessions = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send_json(self, data, status=200, cookie=None):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def owner(self):
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie.get('session')
            return sessions.get(token.value) if token else None

        def do_GET(self):
            path = urlparse(self.path)
            if path.path == '/':
                body = Path(__file__).with_name('index.html').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path.path == '/health':
                self.send_json({'status': 'ok', 'purpose': 'local-learning'})
            elif path.path == '/api/products':
                query = parse_qs(path.query).get('q', [''])[0]
                self.send_json(store.products(query))
            elif path.path == '/api/me':
                self.send_json({'authenticated': bool(self.owner())})
            elif path.path in ('/api/cart', '/api/orders'):
                owner = self.owner()
                if not owner:
                    return self.send_json({'error': '请先登录'}, 401)
                self.send_json(store.cart(owner) if path.path.endswith('cart') else store.orders(owner))
            else:
                self.send_json({'error': '页面不存在'}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 10000:
                    raise ValueError('请求体大小不合法')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('请求格式错误')
                if path == '/api/login':
                    if not all(isinstance(data.get(key), str) for key in ('username', 'password')):
                        raise ValueError('请输入用户名和密码')
                    if not data['username'].strip() or not data['password']:
                        raise ValueError('请输入用户名和密码')
                    if data['username'] != 'demo' or not hmac.compare_digest(data['password'], 'Demo123!'):
                        return self.send_json({'error': '用户名或密码错误'}, 401)
                    token = secrets.token_urlsafe(32)
                    sessions[token] = token
                    return self.send_json({'message': '登录成功'}, cookie=f'session={token}; HttpOnly; SameSite=Strict; Path=/')
                owner = self.owner()
                if not owner:
                    return self.send_json({'error': '请先登录'}, 401)
                if path == '/api/logout':
                    sessions.pop(owner, None)
                    return self.send_json({'message': '已退出登录'}, cookie='session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')
                if path == '/api/cart/add':
                    store.add_cart(owner, data.get('product_id'), data.get('quantity'))
                elif path == '/api/cart/update':
                    store.update_cart(owner, data.get('product_id'), data.get('quantity'))
                elif path == '/api/cart/remove':
                    store.remove_cart(owner, data.get('product_id'))
                elif path == '/api/checkout':
                    return self.send_json(store.checkout(owner, data.get('address'), data.get('request_key')), 201)
                else:
                    return self.send_json({'error': '接口不存在'}, 404)
                self.send_json(store.cart(owner))
            except (ValueError, TypeError) as exc:
                self.send_json({'error': str(exc)}, 400)

    return Handler


def main():
    parser = argparse.ArgumentParser(description='本地电商自动化测试演示')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', default='runtime/webshop.db')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(Store(args.db)))
    print(f'Demo shop: http://127.0.0.1:{server.server_address[1]}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
