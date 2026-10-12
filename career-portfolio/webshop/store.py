"""金额用整数分存储；下单在同一 SQLite 事务中完成。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    price_cents INTEGER NOT NULL CHECK(price_cents>=0),
                    stock INTEGER NOT NULL CHECK(stock>=0), category TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cart (
                    owner TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
                    PRIMARY KEY(owner, product_id));
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL,
                    total_cents INTEGER NOT NULL, address TEXT NOT NULL,
                    request_key TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(owner, request_key));
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity INTEGER NOT NULL, price_cents INTEGER NOT NULL);
            ''')
            conn.executemany('INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)', [
                (1, '轻巧无线键盘', 12900, 100, '数码办公'),
                (2, '便携保温杯', 5900, 100, '生活好物'),
                (3, '桌面阅读灯', 8900, 0, '数码办公'),
                (4, '帆布通勤包', 7900, 100, '生活好物'),
            ])

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def quantity(value):
        if type(value) is not int or not 1 <= value <= 20:
            raise ValueError('数量必须是1到20之间的整数')
        return value

    def products(self, query=''):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM products WHERE instr(name, ?) > 0 ORDER BY id', (query,))]

    def cart(self, owner):
        with self.connect() as conn:
            items = [dict(row) for row in conn.execute('''
                SELECT p.id, p.name, p.price_cents, c.quantity, p.stock
                FROM cart c JOIN products p ON c.product_id=p.id WHERE c.owner=? ORDER BY p.id
            ''', (owner,))]
        return {'items': items, 'total_cents': sum(x['price_cents'] * x['quantity'] for x in items)}

    def add_cart(self, owner, product_id, quantity):
        self.quantity(quantity)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if product is None:
                raise ValueError('商品不存在')
            current = conn.execute('SELECT quantity FROM cart WHERE owner=? AND product_id=?',
                                   (owner, product_id)).fetchone()
            total = quantity + (current['quantity'] if current else 0)
            self.quantity(total)
            if total > product['stock']:
                raise ValueError('商品库存不足')
            conn.execute('''INSERT INTO cart VALUES (?,?,?)
                ON CONFLICT(owner,product_id) DO UPDATE SET quantity=excluded.quantity''',
                         (owner, product_id, total))

    def update_cart(self, owner, product_id, quantity):
        self.quantity(quantity)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            product = conn.execute('SELECT stock FROM products WHERE id=?', (product_id,)).fetchone()
            if product is None or quantity > product['stock']:
                raise ValueError('商品库存不足')
            updated = conn.execute('UPDATE cart SET quantity=? WHERE owner=? AND product_id=?',
                                  (quantity, owner, product_id))
            if updated.rowcount == 0:
                raise ValueError('购物车中无此商品')

    def remove_cart(self, owner, product_id):
        with self.connect() as conn:
            conn.execute('DELETE FROM cart WHERE owner=? AND product_id=?', (owner, product_id))

    def checkout(self, owner, address, request_key):
        if not isinstance(address, str) or not 8 <= len(address.strip()) <= 200:
            raise ValueError('收货地址需填写8到200个字符')
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 100:
            raise ValueError('缺少有效请求编号')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT * FROM orders WHERE owner=? AND request_key=?',
                                    (owner, request_key)).fetchone()
            if existing:
                return dict(existing)
            items = conn.execute('''SELECT c.product_id,c.quantity,p.price_cents,p.stock
                FROM cart c JOIN products p ON p.id=c.product_id WHERE c.owner=?''', (owner,)).fetchall()
            if not items:
                raise ValueError('购物车为空')
            if any(x['quantity'] > x['stock'] for x in items):
                raise ValueError('商品库存不足，请调整购物车')
            total = sum(x['quantity'] * x['price_cents'] for x in items)
            cursor = conn.execute('INSERT INTO orders(owner,total_cents,address,request_key) VALUES (?,?,?,?)',
                                  (owner, total, address.strip(), request_key))
            order_id = cursor.lastrowid
            for item in items:
                conn.execute('INSERT INTO order_items VALUES (?,?,?,?)',
                             (order_id, item['product_id'], item['quantity'], item['price_cents']))
                conn.execute('UPDATE products SET stock=stock-? WHERE id=?',
                             (item['quantity'], item['product_id']))
            conn.execute('DELETE FROM cart WHERE owner=?', (owner,))
            return dict(conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone())

    def orders(self, owner):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM orders WHERE owner=? ORDER BY id DESC', (owner,))]
