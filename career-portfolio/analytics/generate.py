"""固定种子的虚构电商数据；不使用、映射或声称来自真实企业。"""
import numpy as np
import pandas as pd

from .core import CUTOFF, START


def generate_data(seed=20261012, user_count=1000):
    if user_count < 1:
        raise ValueError('user_count 必须为正整数')
    rng = np.random.default_rng(seed)
    channels = ['自然搜索', '内容推荐', '站外广告', '老客邀请']
    users, events, orders = [], [], []
    for user_id in range(1, user_count + 1):
        registered = START + pd.Timedelta(days=int(rng.integers(0, 173)), hours=int(rng.integers(0, 24)))
        channel = str(rng.choice(channels, p=[.35, .30, .25, .10]))
        users.append([user_id, registered.isoformat(), channel])
        # 活跃差异与衰减由生成规则设定，只供分析演示，不作为业务因果证据。
        propensity = float(rng.beta(2, 3))
        days = int((CUTOFF - registered).days)
        for _ in range(int(rng.integers(18, 45))):
            offset = int(rng.integers(0, max(days, 1)))
            if rng.random() > .9 - .45 * offset / max(days, 1):
                continue
            when = registered + pd.Timedelta(days=offset, minutes=int(rng.integers(0, 360)))
            if when + pd.Timedelta(minutes=40) > CUTOFF:
                continue
            product = f'p{int(rng.integers(1, 51)):03d}'
            events.append([f'e{len(events)+1:07d}', user_id, 'browse', when.isoformat(), product])
            if rng.random() < .20 + .45 * propensity:
                cart_time = when + pd.Timedelta(minutes=int(rng.integers(1, 15)))
                events.append([f'e{len(events)+1:07d}', user_id, 'cart', cart_time.isoformat(), product])
                if rng.random() < .48 + .25 * propensity:
                    created = cart_time + pd.Timedelta(minutes=2)
                    paid_at = created + pd.Timedelta(minutes=3)
                    status = str(rng.choice(['paid', 'refunded', 'cancelled', 'pending'], p=[.76, .08, .10, .06]))
                    amount = int(rng.integers(1990, 49900))
                    orders.append([f'o{len(orders)+1:06d}', user_id, created.isoformat(), paid_at.isoformat() if status in ['paid', 'refunded'] else None, status, amount])
                    if status in ['paid', 'refunded']:
                        events.append([f'e{len(events)+1:07d}', user_id, 'purchase', paid_at.isoformat(), product])
    users = pd.DataFrame(users, columns=['user_id', 'registered_at', 'channel'])
    events = pd.DataFrame(events, columns=['event_id', 'user_id', 'event_type', 'event_time', 'product_id'])
    orders = pd.DataFrame(orders, columns=['order_id', 'user_id', 'created_at', 'paid_at', 'status', 'amount_cents'])
    # 注入少量确定性问题。新 ID 防止异常被重复键规则提前吞掉。
    users.loc[0, 'channel'] = None
    users = pd.concat([users, users.iloc[:3]], ignore_index=True)
    events = pd.concat([events, events.iloc[:25], pd.DataFrame([
        ['bad_e_missing_time', 1, 'browse', None, 'p001'],
        ['bad_e_time', 1, 'browse', 'invalid', 'p001'],
        ['bad_e_future', 1, 'browse', '2027-01-01', 'p001'],
        ['bad_e_foreign', user_count + 1, 'browse', '2026-06-01', 'p001'],
    ], columns=events.columns)], ignore_index=True)
    orders = pd.concat([orders, orders.iloc[:8], pd.DataFrame([
        ['bad_o_negative', 1, '2026-06-29', '2026-06-29', 'paid', -100],
        ['bad_o_extreme', 1, '2026-06-29', '2026-06-29', 'paid', 99999999],
        ['bad_o_time', 1, '2026-06-29', 'illegal', 'paid', 10000],
        ['bad_o_missing', 1, '2026-06-29', None, 'paid', 10000],
    ], columns=orders.columns)], ignore_index=True)
    return users, events, orders
