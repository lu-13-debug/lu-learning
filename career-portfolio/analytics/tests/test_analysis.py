import unittest

import pandas as pd

from analytics.core import clean_data, cohort_retention, funnel_counts, pandas_metrics, sql_metrics, rfm_segments
from analytics.generate import generate_data


def fixture():
    users = pd.DataFrame([
        [1, '2026-01-01', '自然'], [2, '2026-01-01', '广告'],
        [3, '2026-02-01', '自然'], [4, '2026-03-01', None],
    ], columns=['user_id', 'registered_at', 'channel'])
    events = pd.DataFrame([
        ['e1', 1, 'browse', '2026-01-02 09:00:00', 'p1'],
        ['e2', 1, 'cart', '2026-01-02 10:00:00', 'p1'],
        ['e3', 1, 'browse', '2026-02-02', 'p1'],
        ['e4', 2, 'cart', '2026-01-02 08:00:00', 'p1'],
        ['e5', 2, 'browse', '2026-01-02 09:00:00', 'p1'],
        ['e6', 3, 'browse', '2026-02-02 09:00:00', 'p1'],
        ['e7', 3, 'cart', '2026-02-02 10:00:00', 'p1'],
    ], columns=['event_id', 'user_id', 'event_type', 'event_time', 'product_id'])
    orders = pd.DataFrame([
        ['o1', 1, '2026-01-02 10:30:00', '2026-01-02 11:00:00', 'paid', 10000],
        ['o2', 1, '2026-02-02 10:00:00', '2026-02-02 11:00:00', 'paid', 20000],
        ['o3', 2, '2026-01-02 10:00:00', '2026-01-02 11:00:00', 'paid', 5000],
        ['o4', 3, '2026-02-02 10:30:00', '2026-02-02 11:00:00', 'refunded', 9000],
        ['o5', 4, '2026-03-02', None, 'cancelled', 1000],
    ], columns=['order_id', 'user_id', 'created_at', 'paid_at', 'status', 'amount_cents'])
    return users, events, orders


class KnownSampleTests(unittest.TestCase):
    def setUp(self):
        self.tables, self.audit = clean_data(*fixture(), cutoff='2026-03-31 23:59:59')

    def test_independent_metrics_match_hand_calculated_truth(self):
        expected = {'uv': 3, 'paid_orders': 3, 'net_sales_cents': 35000}
        for result in (pandas_metrics(self.tables), sql_metrics(self.tables)):
            for name, value in expected.items():
                self.assertEqual(result[name], value, name)
        metrics = pandas_metrics(self.tables)
        self.assertEqual(metrics['gross_paid_cents'], 44000)
        self.assertEqual(metrics['repeat_buyers'], 1)
        self.assertEqual(metrics['net_buyers'], 2)
        self.assertEqual(metrics['repeat_purchase_rate'], 0.5)
        self.assertEqual(metrics['payment_rate'], 0.8)

    def test_funnel_requires_user_and_strict_time_order_excludes_refund(self):
        self.assertEqual(funnel_counts(self.tables), {'browse': 3, 'cart': 2, 'purchase': 1})

    def test_same_timestamp_is_not_ordered_funnel_step(self):
        self.tables['events'].loc[self.tables['events']['event_id'] == 'e2', 'event_time'] = pd.Timestamp('2026-01-02 09:00:00')
        self.assertEqual(funnel_counts(self.tables)['purchase'], 0)

    def test_cohort_uses_all_registrants_and_leaves_unobserved_empty(self):
        cohort = cohort_retention(self.tables, cutoff='2026-03-31 23:59:59', max_month=3)
        jan = cohort[cohort['cohort'] == '2026-01'].set_index('month_index')
        self.assertEqual(jan.loc[0, 'retention'], 1)
        self.assertEqual(jan.loc[1, 'retention'], 0.5)
        self.assertEqual(jan.loc[2, 'retention'], 0)
        self.assertTrue(pd.isna(jan.loc[3, 'retention']))
        mar = cohort[cohort['cohort'] == '2026-03'].set_index('month_index')
        self.assertEqual(mar.loc[0, 'retention'], 0)
        self.assertTrue(pd.isna(mar.loc[1, 'retention']))

    def test_partial_current_month_is_unobserved(self):
        cohort = cohort_retention(self.tables, cutoff='2026-03-15', max_month=2)
        jan = cohort[cohort['cohort'] == '2026-01'].set_index('month_index')
        self.assertTrue(pd.isna(jan.loc[2, 'retention']))

    def test_last_day_before_end_of_day_is_still_partial_month(self):
        cohort = cohort_retention(self.tables, cutoff='2026-03-31 12:00:00', max_month=2)
        jan = cohort[cohort['cohort'] == '2026-01'].set_index('month_index')
        self.assertTrue(pd.isna(jan.loc[2, 'retention']))

    def test_rfm_keeps_non_buyers_and_excludes_refunded_orders(self):
        rfm = rfm_segments(self.tables, cutoff='2026-03-31 23:59:59').set_index('user_id')
        self.assertEqual(rfm.loc[1, 'frequency'], 2)
        self.assertEqual(rfm.loc[1, 'monetary_cents'], 30000)
        self.assertEqual(rfm.loc[3, 'frequency'], 0)
        self.assertEqual(rfm.loc[3, 'segment'], '未购用户')
        self.assertEqual(len(rfm), 4)

    def test_empty_transactions_do_not_divide_by_zero(self):
        self.tables['orders'] = self.tables['orders'].iloc[:0]
        self.tables['events'] = self.tables['events'].iloc[:0]
        metrics = pandas_metrics(self.tables)
        self.assertEqual(metrics['repeat_purchase_rate'], 0)
        self.assertEqual(metrics['payment_rate'], 0)
        self.assertEqual(sql_metrics(self.tables)['net_sales_cents'], 0)
        self.assertEqual(funnel_counts(self.tables)['purchase'], 0)


class CleaningTests(unittest.TestCase):
    def test_audit_accounts_for_each_removed_row_and_channel_imputation(self):
        users, events, orders = fixture()
        events = pd.concat([events, events.iloc[[0]], pd.DataFrame([
            ['bad1', 1, 'browse', None, 'p1'],
            ['bad2', 1, 'browse', 'not-a-date', 'p1'],
            ['bad3', 999, 'browse', '2026-02-01', 'p1'],
            ['bad4', 1, 'browse', '2027-01-01', 'p1'],
            ['bad5', 3, 'browse', '2026-01-01', 'p1'],
        ], columns=events.columns)], ignore_index=True)
        orders = pd.concat([orders, pd.DataFrame([
            ['bad1', 1, '2026-02-02', '2026-02-02', 'paid', -1],
            ['bad2', 1, '2026-02-02', '2026-02-02', 'paid', 100.5],
            ['bad3', 1, '2026-02-02', None, 'paid', 100],
            ['bad4', 1, '2026-02-02', '2026-02-01', 'paid', 100],
            ['bad5', 1, '2026-02-02', None, 'unknown', 100],
        ], columns=orders.columns)], ignore_index=True)
        tables, audit = clean_data(users, events, orders, cutoff='2026-03-31 23:59:59')
        self.assertEqual(len(tables['events']), 7)
        self.assertEqual(len(tables['orders']), 5)
        self.assertEqual(tables['users'].loc[tables['users']['user_id'] == 4, 'channel'].iloc[0], '未知')
        for name, raw in [('users', users), ('events', events), ('orders', orders)]:
            entry = audit[name]
            self.assertEqual(entry['input_rows'], len(raw))
            self.assertEqual(entry['output_rows'] + sum(entry['removed'].values()), len(raw))
        self.assertEqual(audit['events']['removed']['duplicate_id'], 1)
        self.assertEqual(audit['orders']['removed']['invalid_amount'], 2)

    def test_user_primary_keys_registration_and_foreign_keys_are_cleaned(self):
        users, events, orders = fixture()
        users = pd.concat([users, users.iloc[[0]], pd.DataFrame([
            [None, '2026-01-01', '自然'], [5, 'invalid', '自然'],
            [6, '2027-01-01', '自然'],
        ], columns=users.columns)], ignore_index=True)
        tables, audit = clean_data(users, events, orders, cutoff='2026-03-31 23:59:59')
        self.assertEqual(len(tables['users']), 4)
        self.assertEqual(audit['users']['removed']['duplicate_id'], 1)
        self.assertEqual(audit['users']['removed']['missing_id'], 1)
        self.assertEqual(audit['users']['removed']['invalid_time'], 2)


class GenerationTests(unittest.TestCase):
    def test_seed_reproducibility_and_injected_data_issues(self):
        first = generate_data(seed=42, user_count=30)
        second = generate_data(seed=42, user_count=30)
        for left, right in zip(first, second):
            pd.testing.assert_frame_equal(left, right)
        tables, audit = clean_data(*first)
        self.assertEqual(len(tables['users']), 30)
        self.assertGreater(audit['events']['input_rows'], audit['events']['output_rows'])
        self.assertGreater(audit['orders']['removed']['invalid_amount'], 0)


class ReportTests(unittest.TestCase):
    def test_pipeline_writes_reconciled_outputs_and_offline_report(self):
        from pathlib import Path
        import json
        from analytics.run import run
        target = Path(__file__).parent / '_work'
        result = run(output_dir=target, seed=42, user_count=30, save_data=False)
        self.assertEqual(result['reconciliation']['status'], 'PASS')
        self.assertEqual(len(result['reconciliation']['checks']), 3)
        loaded = json.loads((target / 'metrics.json').read_text(encoding='utf-8'))
        self.assertEqual(loaded['metrics']['net_sales_cents'], result['metrics']['net_sales_cents'])
        html = (target / 'report.html').read_text(encoding='utf-8')
        self.assertIn('<svg', html)
        self.assertIn('合成数据', html)
        self.assertNotIn('<script src=', html)
        for name in ['daily_sales.csv', 'cohort_retention.csv', 'rfm_segments.csv', 'cleaning_audit.csv', 'reconciliation.csv']:
            self.assertTrue((target / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
