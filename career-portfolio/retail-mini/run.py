"""标准库实现的零售日报练习。全部输入为可复现模拟数据。"""
import csv
from datetime import date, timedelta
import html
import json
from pathlib import Path
import random
import sqlite3
from statistics import median

ROOT = Path(__file__).resolve().parent
SEED = 20261012
INJECTED_DATE = "2026-02-14"
INJECTED_STORE = "S03"
SOURCE_FIELDS = ["date", "store_id", "sku", "qty", "unit_price_cents"]


def generate_sales():
    """8 家门店、60 个完整日期、12 个 SKU；固定单个门店日期的下滑。"""
    rng = random.Random(SEED)
    rows = []
    for offset in range(60):
        day = (date(2026, 1, 1) + timedelta(days=offset)).isoformat()
        for store in range(1, 9):
            store_id = f"S{store:02d}"
            for sku in range(1, 13):
                qty = 10 + store * 2 + rng.randint(-2, 2)
                if day == INJECTED_DATE and store_id == INJECTED_STORE:
                    qty = max(1, qty // 5)
                rows.append({"date": day, "store_id": store_id,
                             "sku": f"SKU{sku:02d}", "qty": qty,
                             "unit_price_cents": 500 + sku * 175})
    return rows


def analyze(rows):
    """SQL 负责汇总，Python 按完整自然日窗口补充可解释的异常标记。"""
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE sales (date TEXT, store_id TEXT, sku TEXT, "
                     "qty INTEGER CHECK(qty >= 0), "
                     "unit_price_cents INTEGER CHECK(unit_price_cents >= 0))")
        conn.executemany("INSERT INTO sales VALUES (:date,:store_id,:sku,:qty,:unit_price_cents)", rows)
        daily = [dict(r) for r in conn.execute((ROOT / "sql/daily_report.sql").read_text(encoding="utf-8"))]
        ranking = [dict(r) for r in conn.execute((ROOT / "sql/store_ranking.sql").read_text(encoding="utf-8"))]
    lookup = {(r["store_id"], r["date"]): r["sales_cents"] for r in daily}
    for row in daily:
        day = date.fromisoformat(row["date"])
        history = [lookup.get((row["store_id"], (day - timedelta(days=i)).isoformat()))
                   for i in range(1, 8)]
        baseline = median(history) if all(value is not None for value in history) else None
        row["baseline_cents"] = baseline
        row["baseline_ratio"] = row["sales_cents"] / baseline if baseline else None
        row["is_anomaly"] = baseline is not None and baseline > 0 and row["sales_cents"] < baseline * 0.60
        row["baseline_status"] = "可用" if baseline is not None else "前7个自然日数据不完整"
    return daily, ranking


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(daily, ranking, metrics):
    """内嵌 SVG 和 CSS，不依赖网络资源；页面展示元，CSV 保留分。"""
    target = [r for r in daily if r["store_id"] == INJECTED_STORE]
    max_sales = max(r["sales_cents"] for r in target) * 1.15
    x = lambda i: 50 + i * 830 / (len(target) - 1)
    y = lambda value: 245 - value * 195 / max_sales
    sales_points = " ".join(f'{x(i):.1f},{y(r["sales_cents"]):.1f}' for i, r in enumerate(target))
    base_points = " ".join(f'{x(i):.1f},{y(r["baseline_cents"]):.1f}' for i, r in enumerate(target)
                           if r["baseline_cents"] is not None)
    dots = "".join(f'<circle cx="{x(i):.1f}" cy="{y(r["sales_cents"]):.1f}" r="6" fill="#bf3b33"><title>{r["date"]}：模拟下滑，销售额 {r["sales_cents"]/100:,.2f} 元</title></circle>'
                   for i, r in enumerate(target) if r["is_anomaly"])
    bars = "".join(f'<tr><td>{r["sales_rank"]}</td><td>{html.escape(r["store_id"])}</td>'
                   f'<td><div class="bar" style="width:{r["sales_share"]*420:.1f}%"></div>{r["sales_cents"]/100:,.2f}</td>'
                   f'<td>{r["sales_share"]:.2%}</td></tr>' for r in ranking)
    anomaly_rows = "".join(f'<tr><td>{r["date"]}</td><td>{r["store_id"]}</td><td>{r["sales_cents"]/100:,.2f}</td>'
                           f'<td>{r["baseline_cents"]/100:,.2f}</td><td>{r["baseline_ratio"]:.1%}</td></tr>'
                           for r in daily if r["is_anomaly"])
    return f'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>零售门店销售日报与异常分析</title>
<style>body{{font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;color:#203040;background:#f3f5f8;margin:0}}
main{{max-width:1040px;margin:auto;padding:30px 22px}}h1{{font-size:30px}}h2{{font-size:21px}}.notice{{background:#fff0cc;padding:16px;border-radius:10px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:22px 0}}.card,section{{background:white;border-radius:12px;padding:22px;margin-bottom:20px}}
.card b{{display:block;font-size:25px}}small,.muted{{color:#536477}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px 8px;text-align:left;border-bottom:1px solid #e6ebf1}}
.bar{{height:7px;background:#387cb1;border-radius:5px;max-width:100%}}svg{{width:100%;height:auto}}a{{color:#24689c}}.table-wrap{{overflow-x:auto}}</style>
<main><h1>零售门店销售日报与异常分析</h1><p class="muted">2026-01-01 至 2026-03-01 · 8 家门店 · Python + SQLite</p>
<p class="notice"><strong>模拟数据 / 行业练习。</strong>2026-02-14 的 S03 销量被主动调低，用于验证异常规则。此页面仅展示分析流程，不能作为真实经营结论，也不能证明异常原因。</p>
<div class="cards"><div class="card">期间销售额（元）<b>{metrics["sales_cents"]/100:,.2f}</b></div>
<div class="card">门店日报记录<b>{metrics["daily_rows"]}</b></div><div class="card">可用基线记录<b>{metrics["baseline_available_rows"]}</b></div><div class="card">规则标记异常<b>{metrics["anomaly_count"]}</b></div></div>
<section><h2>S03 每日销售额与过去 7 日中位数</h2><p>蓝线为销售额，虚线为历史基线，红点为规则异常。单位：元。前 7 天不生成基线。</p>
<svg viewBox="0 0 920 300" role="img" aria-label="S03 每日销售走势，2月14日出现主动注入的下滑">
<line x1="50" y1="245" x2="880" y2="245" stroke="#ccd5df"/>
<text x="5" y="58" font-size="13">{max_sales/100:,.0f}</text><text x="20" y="249" font-size="13">0</text>
<polyline points="{sales_points}" fill="none" stroke="#387cb1" stroke-width="2.5"/>
<polyline points="{base_points}" fill="none" stroke="#8395a7" stroke-width="2" stroke-dasharray="6 5"/>{dots}
<text x="50" y="280" font-size="13">01-01</text><text x="445" y="280" font-size="13">01-31</text><text x="845" y="280" font-size="13">03-01</text></svg></section>
<section><h2>期间门店销售排名</h2><div class="table-wrap"><table><thead><tr><th>排名</th><th>门店</th><th>销售额（元）</th><th>期间占比</th></tr></thead><tbody>{bars}</tbody></table></div></section>
<section><h2>异常清单</h2><div class="table-wrap"><table><thead><tr><th>日期</th><th>门店</th><th>销售额（元）</th><th>7日基线（元）</th><th>基线比例</th></tr></thead><tbody>{anomaly_rows}</tbody></table></div>
<p>规则：当天销售额严格低于过去 7 个完整自然日中位数的 60%。历史缺日或基线为 0 时不标记异常。实际使用应先核对数据完整性、营业安排、促销与退货，再评估同星期基线和阈值。</p></section>
<section><h2>口径与追溯</h2><p>销售额 = 数量 × 单价，金额使用整数分存储。日环比 =（当天 − 昨天）/ 昨天；缺少昨天或昨天为 0 时留空。每行流水代表一个门店日期下的 SKU 销售汇总，未模拟订单、折扣、税费和退货。</p>
<p><a href="sales.csv">模拟销售流水</a> · <a href="daily_report.csv">门店日报</a> · <a href="store_ranking.csv">门店排名</a> · <a href="anomalies.csv">异常列表</a> · <a href="metrics.json">核验指标</a></p>
<p>从异常日期与门店筛选流水，逐项计算 qty × unit_price_cents，即可复核当天金额；再对前 7 天每日金额取中位数，可复核基线。</p></section></main></html>'''


def run_pipeline(output=None):
    output = Path(output) if output is not None else ROOT / "reports/retail"
    output.mkdir(parents=True, exist_ok=True)
    rows = generate_sales()
    daily, ranking = analyze(rows)
    anomalies = [r for r in daily if r["is_anomaly"]]
    metrics = {"data_type": "模拟数据，仅用于分析练习", "seed": SEED,
               "start_date": rows[0]["date"], "end_date": rows[-1]["date"],
               "stores": len(ranking), "days": 60, "source_rows": len(rows),
               "daily_rows": len(daily), "sales_cents": sum(r["sales_cents"] for r in daily),
               "source_sales_cents": sum(r["qty"] * r["unit_price_cents"] for r in rows),
               "baseline_available_rows": sum(r["baseline_cents"] is not None for r in daily),
               "anomaly_count": len(anomalies),
               "injected_anomaly": {"date": INJECTED_DATE, "store_id": INJECTED_STORE},
               "rule": "前7个完整自然日销售额中位数；当天严格低于60%标记；正基线才判断"}
    write_csv(output / "sales.csv", rows, SOURCE_FIELDS)
    write_csv(output / "daily_report.csv", daily, list(daily[0]))
    write_csv(output / "store_ranking.csv", ranking, list(ranking[0]))
    write_csv(output / "anomalies.csv", anomalies, list(daily[0]))
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "report.html").write_text(render_report(daily, ranking, metrics), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"报告位置：{ROOT / 'reports/retail/report.html'}")
