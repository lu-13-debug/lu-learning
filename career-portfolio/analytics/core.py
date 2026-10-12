"""清洗与指标计算。金额全程使用整数分，避免浮点对账误差。"""
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

START = pd.Timestamp('2026-01-01')
CUTOFF = pd.Timestamp('2026-06-30 23:59:59')


def clean_data(users, events, orders, cutoff=CUTOFF):
    cutoff = pd.Timestamp(cutoff)
    tables, audit = {}, {}
    for name, raw, key in [('users', users, 'user_id'), ('events', events, 'event_id'), ('orders', orders, 'order_id')]:
        frame = raw.copy()
        entry = {'input_rows': len(frame), 'removed': {}, 'imputed': {}}

        def remove(reason, mask):
            nonlocal frame
            entry['removed'][reason] = int(mask.sum())
            frame = frame.loc[~mask].copy()

        remove('missing_id', frame[key].isna() | frame[key].astype(str).str.strip().eq(''))
        if name == 'users':
            ids = pd.to_numeric(frame[key], errors='coerce')
            remove('invalid_id', ids.isna() | ids.le(0) | ids.mod(1).ne(0))
            frame[key] = pd.to_numeric(frame[key]).astype('int64')
        remove('duplicate_id', frame.duplicated(key, keep='first'))
        if name == 'users':
            frame['registered_at'] = pd.to_datetime(frame['registered_at'], errors='coerce', format='mixed')
            remove('invalid_time', frame['registered_at'].isna() | frame['registered_at'].lt(START) | frame['registered_at'].gt(cutoff))
            entry['imputed']['missing_channel'] = int(frame['channel'].isna().sum())
            frame['channel'] = frame['channel'].fillna('未知')
        else:
            ids = pd.to_numeric(frame['user_id'], errors='coerce')
            remove('unknown_user', ~ids.isin(tables['users']['user_id']))
            frame['user_id'] = pd.to_numeric(frame['user_id']).astype('int64')
            registered = frame['user_id'].map(tables['users'].set_index('user_id')['registered_at'])
            column = 'event_time' if name == 'events' else 'created_at'
            frame[column] = pd.to_datetime(frame[column], errors='coerce', format='mixed')
            invalid = frame[column].isna() | frame[column].lt(registered) | frame[column].gt(cutoff)
            if name == 'orders':
                frame['paid_at'] = pd.to_datetime(frame['paid_at'], errors='coerce', format='mixed')
                paid = frame['status'].isin(['paid', 'refunded'])
                invalid |= paid & (frame['paid_at'].isna() | frame['paid_at'].lt(frame['created_at']) | frame['paid_at'].gt(cutoff))
            remove('invalid_time', invalid)
            if name == 'events':
                remove('invalid_event_type', ~frame['event_type'].isin(['browse', 'cart', 'purchase']))
                remove('missing_product', frame['product_id'].isna())
            else:
                remove('invalid_status', ~frame['status'].isin(['paid', 'refunded', 'cancelled', 'pending']))
                amount = pd.to_numeric(frame['amount_cents'], errors='coerce')
                remove('invalid_amount', amount.isna() | ~np.isfinite(amount) | amount.le(0) | amount.gt(1000000) | amount.mod(1).ne(0))
                frame['amount_cents'] = pd.to_numeric(frame['amount_cents']).astype('int64')
                # 未支付订单不保留伪支付时间。
                frame.loc[~frame['status'].isin(['paid', 'refunded']), 'paid_at'] = pd.NaT
        entry['output_rows'] = len(frame)
        tables[name], audit[name] = frame.reset_index(drop=True), entry
    return tables, audit


def pandas_metrics(tables):
    orders = tables['orders']
    paid = orders.loc[orders['status'].eq('paid')]
    transacted = orders.loc[orders['status'].isin(['paid', 'refunded'])]
    counts = paid.groupby('user_id').size()
    buyers, repeat = len(counts), int(counts.ge(2).sum())
    return {
        'uv': int(tables['events']['user_id'].nunique()),
        'paid_orders': len(paid), 'net_sales_cents': int(paid['amount_cents'].sum()),
        'gross_paid_cents': int(transacted['amount_cents'].sum()),
        'refunded_cents': int(orders.loc[orders['status'].eq('refunded'), 'amount_cents'].sum()),
        'submitted_orders': len(orders), 'transacted_orders': len(transacted),
        'payment_rate': len(transacted) / len(orders) if len(orders) else 0,
        'net_buyers': buyers, 'repeat_buyers': repeat,
        'repeat_purchase_rate': repeat / buyers if buyers else 0,
    }


def sql_metrics(tables):
    with sqlite3.connect(':memory:') as connection:
        for name, frame in tables.items():
            frame.to_sql(name, connection, index=False, if_exists='replace')
        sql = (Path(__file__).parent / 'sql' / 'key_metrics.sql').read_text(encoding='utf-8')
        cursor = connection.execute(sql)
        return dict(zip([item[0] for item in cursor.description], cursor.fetchone()))


def funnel_counts(tables):
    """跨会话用户漏斗；browse < cart < 未退款支付，严格时间递增。"""
    events = tables['events']
    first_browse = events.loc[events['event_type'].eq('browse')].groupby('user_id')['event_time'].min()
    if first_browse.empty:
        return {'browse': 0, 'cart': 0, 'purchase': 0}
    carts = events.loc[events['event_type'].eq('cart')].copy()
    carts = carts.loc[carts['event_time'].gt(carts['user_id'].map(first_browse))]
    first_cart = carts.groupby('user_id')['event_time'].min()
    if first_cart.empty:
        return {'browse': len(first_browse), 'cart': 0, 'purchase': 0}
    paid = tables['orders'].loc[tables['orders']['status'].eq('paid')].copy()
    paid = paid.loc[paid['paid_at'].gt(paid['user_id'].map(first_cart))]
    return {'browse': len(first_browse), 'cart': len(first_cart), 'purchase': int(paid['user_id'].nunique())}


def cohort_retention(tables, cutoff=CUTOFF, max_month=5):
    """分母为当月所有注册用户；行为活跃为任一有效事件。只展示完整自然月。"""
    users, events = tables['users'].copy(), tables['events'].copy()
    users['cohort'] = users['registered_at'].dt.to_period('M')
    events['active_month'] = events['event_time'].dt.to_period('M')
    cohort_by_user = users.set_index('user_id')['cohort']
    events['cohort'] = events['user_id'].map(cohort_by_user)
    cutoff = pd.Timestamp(cutoff)
    last_complete = cutoff.to_period('M')
    # 数据精度为整秒；月末当天尚未到 23:59:59 仍属于未完整观察。
    if cutoff < cutoff.to_period('M').end_time.floor('s'):
        last_complete -= 1
    rows = []
    for cohort, count in users.groupby('cohort').size().items():
        for index in range(max_month + 1):
            active_month = cohort + index
            observed = active_month <= last_complete
            active = int(events.loc[events['cohort'].eq(cohort) & events['active_month'].eq(active_month), 'user_id'].nunique()) if observed else None
            rows.append({'cohort': str(cohort), 'month_index': index, 'cohort_users': int(count),
                         'active_users': active, 'retention': active / count if observed else None})
    return pd.DataFrame(rows, columns=['cohort', 'month_index', 'cohort_users', 'active_users', 'retention'])


def rfm_segments(tables, cutoff=CUTOFF):
    paid = tables['orders'].loc[tables['orders']['status'].eq('paid')]
    grouped = paid.groupby('user_id').agg(last_paid_at=('paid_at', 'max'), frequency=('order_id', 'count'), monetary_cents=('amount_cents', 'sum'))
    result = tables['users'][['user_id']].merge(grouped, on='user_id', how='left')
    result['frequency'] = result['frequency'].fillna(0).astype(int)
    result['monetary_cents'] = result['monetary_cents'].fillna(0).astype('int64')
    result['recency_days'] = (pd.Timestamp(cutoff).normalize() - result['last_paid_at'].dt.normalize()).dt.days
    # 演示用固定业务规则，不声称经真实营销实验验证。
    result['segment'] = np.select([
        result['frequency'].eq(0),
        result['recency_days'].gt(60),
        result['frequency'].ge(3) & result['monetary_cents'].ge(50000),
        result['frequency'].ge(2),
    ], ['未购用户', '沉睡买家', '高价值活跃买家', '活跃复购买家'], default='活跃首购买家')
    return result
