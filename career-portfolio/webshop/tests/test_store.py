import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path


class StoreTests(unittest.TestCase):
    def setUp(self):
        try:
            self.Store = importlib.import_module('webshop.store').Store
        except ImportError:
            self.fail('缺少购物车与订单存储实现')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'shop.db'
        self.store = self.Store(self.path)
        self.owner = 'isolated-buyer'

    def test_empty_cart_cannot_checkout(self):
        with self.assertRaisesRegex(ValueError, '购物车为空'):
            self.store.checkout(self.owner, '深圳市测试地址123号', 'key')

    def test_quantity_boundaries_and_types(self):
        for qty in [0, -1, 21, 1.5, True, '1']:
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                self.store.add_cart(self.owner, 1, qty)

    def test_cart_update_remove_and_isolation(self):
        self.store.add_cart(self.owner, 1, 2)
        self.assertEqual(self.store.cart(self.owner)['total_cents'], 25800)
        self.assertEqual(self.store.cart('other')['items'], [])
        self.store.update_cart(self.owner, 1, 3)
        self.assertEqual(self.store.cart(self.owner)['total_cents'], 38700)
        self.store.remove_cart(self.owner, 1)
        self.assertEqual(self.store.cart(self.owner)['items'], [])

    def test_unknown_or_sold_out_product_rejected(self):
        for pid in [999, 3]:
            with self.subTest(pid=pid), self.assertRaises(ValueError):
                self.store.add_cart(self.owner, pid, 1)

    def test_short_address_rejected_without_clearing_cart(self):
        self.store.add_cart(self.owner, 1, 1)
        with self.assertRaisesRegex(ValueError, '地址'):
            self.store.checkout(self.owner, '深圳', 'key')
        self.assertEqual(len(self.store.cart(self.owner)['items']), 1)

    def test_checkout_is_atomic_and_idempotent(self):
        self.store.add_cart(self.owner, 1, 2)
        order = self.store.checkout(self.owner, '深圳市测试街道123号', 'key')
        again = self.store.checkout(self.owner, '深圳市测试街道123号', 'key')
        self.assertEqual(order, again)
        self.assertEqual(order['total_cents'], 25800)
        self.assertEqual(self.store.cart(self.owner)['items'], [])
        with self.store.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT SUM(quantity * price_cents) FROM order_items').fetchone()[0], 25800)
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0], 98)

    def test_insufficient_stock_rolls_back_entire_order(self):
        self.store.add_cart(self.owner, 1, 2)
        self.store.add_cart(self.owner, 2, 1)
        with self.store.connect() as conn:
            conn.execute('UPDATE products SET stock=0 WHERE id=2')
        with self.assertRaisesRegex(ValueError, '库存'):
            self.store.checkout(self.owner, '深圳市测试街道123号', 'key')
        with self.store.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0], 100)
        self.assertEqual(len(self.store.cart(self.owner)['items']), 2)

    def test_order_history_is_isolated(self):
        self.store.add_cart(self.owner, 1, 1)
        self.store.checkout(self.owner, '深圳市测试街道123号', 'key')
        self.assertEqual(len(self.store.orders(self.owner)), 1)
        self.assertEqual(self.store.orders('other'), [])

    def test_search_does_not_interpret_sql(self):
        self.assertEqual(len(self.store.products('键盘')), 1)
        self.assertEqual(self.store.products("' OR 1=1 --"), [])


if __name__ == '__main__':
    unittest.main()
