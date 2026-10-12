"""从 career-portfolio 根运行：python -m analytics.run。"""
import argparse
import json
from pathlib import Path
import sqlite3

import pandas as pd
import numpy as np

from .core import START, CUTOFF, clean_data, cohort_retention, funnel_counts, pandas_metrics, rfm_segments, sql_metrics
from .generate import generate_data
from .report import build_report


def run(output_dir=None, seed=20261012, user_count=1000, save_data=True):
    base = Path(__file__).resolve().parent
    output = Path(output_dir) if output_dir else base / 'outputs'
    output.mkdir(parents=True, exist_ok=True)
    raw = generate_data(seed=seed, user_count=user_count)
    tables, audit = clean_data(*raw)
    metrics, sql = pandas_metrics(tables), sql_metrics(tables)
    checks = [{'metric': key, 'pandas': metrics[key], 'sql': sql[key], 'match': metrics[key] == sql[key]}
              for key in ['uv', 'paid_orders', 'net_sales_cents']]
    if not all(check['match'] for check in checks):
        raise AssertionError(f'SQL/Pandas 对账失败：{checks}')
    orders = tables['orders']
    transacted = orders.loc[orders['status'].isin(['paid', 'refunded'])].copy()
    transacted['date'] = transacted['paid_at'].dt.strftime('%Y-%m-%d')
    transacted['net_sales_cents'] = transacted['amount_cents'].where(transacted['status'].eq('paid'), 0)
    transacted['refunded_cents'] = transacted['amount_cents'].where(transacted['status'].eq('refunded'), 0)
    transacted['paid_orders'] = transacted['status'].eq('paid').astype(int)
    daily = transacted.groupby('date').agg(gross_paid_cents=('amount_cents', 'sum'), net_sales_cents=('net_sales_cents', 'sum'), refunded_cents=('refunded_cents', 'sum'), paid_orders=('paid_orders', 'sum'))
    daily = daily.reindex(pd.date_range(START, CUTOFF, freq='D').strftime('%Y-%m-%d'), fill_value=0).rename_axis('date').reset_index()
    cohort, rfm = cohort_retention(tables), rfm_segments(tables)
    result = {'data_source': 'synthetic / 合成数据；个人实战项目', 'seed': seed,
              'window': {'start': str(START), 'cutoff': str(CUTOFF), 'timezone': 'Asia/Shanghai（无时区本地时间）'},
              'runtime': {'pandas': pd.__version__, 'numpy': np.__version__},
              'rows': {name: len(frame) for name, frame in tables.items()},
              'metrics': metrics, 'funnel': funnel_counts(tables),
              'segments': {str(name): int(value) for name, value in rfm['segment'].value_counts().items()},
              'cleaning_audit': audit, 'reconciliation': {'status': 'PASS', 'checks': checks}}
    (output / 'metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    daily.to_csv(output / 'daily_sales.csv', index=False)
    cohort.to_csv(output / 'cohort_retention.csv', index=False, na_rep='')
    rfm.to_csv(output / 'rfm_segments.csv', index=False, na_rep='')
    pd.DataFrame(checks).to_csv(output / 'reconciliation.csv', index=False)
    audit_rows = [{'table': table, 'action': 'removed', 'reason': reason, 'rows': count} for table, entry in audit.items() for reason, count in entry['removed'].items()]
    audit_rows += [{'table': table, 'action': 'imputed', 'reason': reason, 'rows': count} for table, entry in audit.items() for reason, count in entry['imputed'].items()]
    pd.DataFrame(audit_rows).to_csv(output / 'cleaning_audit.csv', index=False)
    (output / 'report.html').write_text(build_report(result, daily, cohort, rfm), encoding='utf-8')
    if save_data:
        data = base / 'data'
        data.mkdir(exist_ok=True)
        for name, frame in zip(['users', 'events', 'orders'], raw):
            frame.to_csv(data / f'raw_{name}.csv', index=False)
        with sqlite3.connect(data / 'commerce.sqlite') as connection:
            for name, frame in tables.items():
                frame.to_sql(name, connection, index=False, if_exists='replace')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--seed', type=int, default=20261012)
    parser.add_argument('--users', type=int, default=1000)
    parser.add_argument('--no-data', action='store_true', help='只输出报告，不落原始数据及 SQLite 文件')
    args = parser.parse_args()
    result = run(args.output_dir, args.seed, args.users, not args.no_data)
    print(json.dumps({'rows': result['rows'], 'metrics': result['metrics'], 'funnel': result['funnel'], 'reconciliation': result['reconciliation']['status']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
