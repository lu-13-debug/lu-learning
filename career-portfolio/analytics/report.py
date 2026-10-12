"""无外部依赖的 HTML + SVG 报告，可断网打开。"""
from html import escape

import pandas as pd


def _money(cents):
    return f'¥{cents / 100:,.2f}'


def _bars(items, color='#2563eb'):
    width, row = 720, 44
    maximum = max((value for _, value in items), default=1) or 1
    marks = []
    for index, (label, value) in enumerate(items):
        y = index * row + 12
        marks.append(f'<text x="0" y="{y+19}" font-size="13" fill="#475569">{escape(label)}</text><rect x="154" y="{y}" width="{value / maximum * 450:.2f}" height="27" rx="4" fill="{color}"/><text x="{164+value / maximum*450:.2f}" y="{y+19}" font-size="13" fill="#0f172a">{value:,}</text>')
    return f'<svg role="img" aria-label="用户数量条形图" viewBox="0 0 {width} {len(items)*row+12}">' + ''.join(marks) + '</svg>'


def _line(daily):
    values = daily['net_sales_cents'].tolist()
    maximum = max(values, default=1) or 1
    left, top, w, h = 58, 20, 830, 190
    points = ' '.join(f'{left+i*w/max(len(values)-1,1):.2f},{top+h-v/maximum*h:.2f}' for i, v in enumerate(values))
    guides = ''.join(f'<line x1="{left}" x2="{left+w}" y1="{top+h*i/4}" y2="{top+h*i/4}" stroke="#e2e8f0"/><text x="48" y="{top+h*i/4+4}" text-anchor="end" font-size="11" fill="#64748b">{maximum*(1-i/4)/100:,.0f}</text>' for i in range(5))
    labels = ''.join(f'<text x="{left+i*w/max(len(values)-1,1):.2f}" y="235" text-anchor="middle" font-size="11" fill="#64748b">{date[5:]}</text>' for i, date in enumerate(daily['date']) if date.endswith('-01') or i == len(daily)-1)
    return f'<svg role="img" aria-label="每日净销售额，单位元" viewBox="0 0 930 250">{guides}<polyline fill="none" stroke="#2563eb" stroke-width="2" points="{points}"/>{labels}</svg>'


def build_report(result, daily, cohort, rfm):
    metrics, funnel = result['metrics'], result['funnel']
    cards = [('行为活跃 UV', f"{metrics['uv']:,}", '有效事件去重用户'),
             ('未退款支付订单', f"{metrics['paid_orders']:,}", 'status = paid'),
             ('净销售额', _money(metrics['net_sales_cents']), '全额退款订单排除'),
             ('买家复购率', f"{metrics['repeat_purchase_rate']:.1%}", f"{metrics['repeat_buyers']} / {metrics['net_buyers']} 位买家")]
    card_html = ''.join(f'<div class="card"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>' for label, value, note in cards)
    cohort_rows = []
    for month, group in cohort.groupby('cohort'):
        cells = []
        for _, entry in group.iterrows():
            if pd.isna(entry['retention']):
                cells.append('<td class="na">—</td>')
            else:
                rate = entry['retention']
                cells.append(f'<td style="background:rgba(37,99,235,{.04+.65*rate:.3f});color:{"white" if rate > .65 else "#0f172a"}">{rate:.1%}<small>{int(entry["active_users"])} 人</small></td>')
        cohort_rows.append(f'<tr><th>{month}</th><td>{int(group.iloc[0]["cohort_users"])}</td>{"".join(cells)}</tr>')
    audit_rows = []
    for name, entry in result['cleaning_audit'].items():
        removed = ', '.join(f'{reason}: {count}' for reason, count in entry['removed'].items() if count)
        audit_rows.append(f'<tr><th>{name}</th><td>{entry["input_rows"]:,}</td><td>{entry["output_rows"]:,}</td><td>{entry["input_rows"]-entry["output_rows"]}</td><td class="notes">{escape(removed) or "无"}</td></tr>')
    checks = ''.join(f'<tr><th>{escape(check["metric"])}</th><td>{check["pandas"]:,}</td><td>{check["sql"]:,}</td><td class="pass">PASS</td></tr>' for check in result['reconciliation']['checks'])
    segment_items = list(rfm['segment'].value_counts().items())
    browse, cart, purchase = funnel['browse'], funnel['cart'], funnel['purchase']
    cart_rate = cart / browse if browse else 0
    purchase_rate = purchase / cart if cart else 0
    max_month = int(cohort['month_index'].max())
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>电商用户行为与交易分析｜个人实战</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f5f9;color:#0f172a;font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.65}}main{{max-width:1120px;margin:auto;padding:32px 24px 54px}}header{{padding:32px;border-radius:18px;background:#102747;color:white}}header p{{color:#d1e0f3;margin:8px 0}}h1{{font-size:29px;margin:8px 0}}h2{{font-size:21px;margin:0 0 8px}}h3{{font-size:16px}}.tag{{display:inline-block;padding:3px 10px;border:1px solid #6e94c4;border-radius:5px;font-size:12px;letter-spacing:1px}}.meta{{font-size:13px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0}}.card,section{{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:23px}}.card span,.card small{{display:block;color:#64748b;font-size:12px}}.card strong{{display:block;font-size:26px;margin:8px 0;letter-spacing:-.5px}}section{{margin-top:18px}}.caption{{font-size:13px;color:#64748b;margin:0 0 14px}}.grid{{display:grid;grid-template-columns:1.15fr 1fr;gap:18px}}svg{{display:block;width:100%;height:auto;margin-top:12px}}.insight{{border-left:3px solid #2563eb;padding:12px 16px;background:#eff6ff;font-size:14px}}table{{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}}th,td{{padding:12px 10px;text-align:right;border-bottom:1px solid #e2e8f0}}th:first-child,td:first-child{{text-align:left}}thead th{{color:#475569;background:#f8fafc}}td small{{display:block;font-size:10px;opacity:.8}}.na{{background:#f1f5f9;color:#94a3b8}}.notes{{text-align:left;max-width:360px;overflow-wrap:anywhere;font-family:monospace;font-size:11px}}.pass{{color:#047857;font-weight:bold}}.scroll{{overflow:auto}}footer{{padding-top:20px;color:#64748b;font-size:12px}}a{{color:#2563eb}}li{{margin:6px 0}}@media(max-width:760px){{main{{padding:14px}}header{{padding:22px}}h1{{font-size:23px}}.cards{{grid-template-columns:repeat(2,1fr)}}.grid{{display:block}}.card strong{{font-size:21px}}section{{padding:18px}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}section,.card{{break-inside:avoid}}}}
</style></head><body><main>
<header><span class="tag">个人实战 · 合成数据 · 可复现</span><h1>电商用户行为与交易分析</h1><p>从数据质量、购买转化到用户留存，建立可审计的分析链路。</p><p class="meta">观察窗口：2026-01-01 — 2026-06-30 ｜ 种子 {result['seed']} ｜ Python · Pandas · SQLite SQL</p></header>
<div class="cards">{card_html}</div>
<section><h2>01 · 数据与结论边界</h2><p>本报告使用生成器构造的虚构用户、行为和订单，演示从清洗到指标验证的个人项目。活跃差异、购买倾向及退款比例由生成规则设定；报告不代表任何企业的经营数据，不据此声称业务提升或营销因果效果。</p><p class="caption">清洗后：{result['rows']['users']:,} 位注册用户 · {result['rows']['events']:,} 条事件 · {result['rows']['orders']:,} 笔提交订单。所有金额均以整数分计算，展示时转换为元。</p></section>
<div class="grid"><section><h2>02 · 顺序用户漏斗</h2><p class="caption">同一用户、跨会话；浏览时间 &lt; 加购时间 &lt; 未退款支付时间。每层用户只计一次，不要求同一商品。</p>{_bars([('浏览用户', browse), ('后续加购用户', cart), ('后续购买用户', purchase)])}<div class="insight">浏览→加购 {cart_rate:.1%}；加购→购买 {purchase_rate:.1%}。这是整个观察窗累计转化，不能替代同次会话转化或广告归因。</div></section>
<section><h2>03 · 用户分群</h2><p class="caption">以最后未退款支付计算 R、F、M；固定规则分群，包含未购用户。</p>{_bars(segment_items, '#0f766e')}<p class="caption">沉睡：R &gt; 60 天；高价值活跃：R ≤ 60、F ≥ 3 且 M ≥ ¥500；其余活跃买家按复购区分。阈值用于演示，尚未经业务验证。</p></section></div>
<section><h2>04 · 每日净销售额</h2><p class="caption">单位：元。按支付日统计当前状态为 paid 的订单，填补无成交日期为 0。退款订单按原支付日排除；该序列属于最终状态回溯口径。</p>{_line(daily)}<div class="insight">累计支付总额 {_money(metrics['gross_paid_cents'])}，全额退款 {_money(metrics['refunded_cents'])}，净销售额 {_money(metrics['net_sales_cents'])}。提交订单支付率 {metrics['payment_rate']:.1%}（曾支付订单含退款 / 所有有效提交订单）。</div></section>
<section><h2>05 · 注册 Cohort 月留存</h2><p class="caption">分母：当月全部注册用户。分子：目标自然月产生任一有效事件的去重用户。M0 为注册月活跃比例，不强制为 100%；灰色“—”表示目标月份尚未完整观察。</p><div class="scroll"><table><thead><tr><th>注册月</th><th>注册人数</th>{''.join(f'<th>M{i}</th>' for i in range(max_month+1))}</tr></thead><tbody>{''.join(cohort_rows)}</tbody></table></div><p class="caption">月份比较需控制注册时间和观察长度；靠后的 cohort 仍存在右删失，不能把未观察月份记为零或直接下结论。</p></section>
<section><h2>06 · 清洗审计</h2><p class="caption">按主键缺失→重复→外键→时间→状态/金额顺序剔除；各原因互斥计数，输入 = 输出 + 剔除。用户渠道缺失填“未知”，单列记录。</p><div class="scroll"><table><thead><tr><th>表</th><th>输入行</th><th>有效行</th><th>剔除行</th><th>剔除原因及数量</th></tr></thead><tbody>{''.join(audit_rows)}</tbody></table></div><p class="caption">渠道缺失填补 {result['cleaning_audit']['users']['imputed']['missing_channel']} 行。异常金额规则：非数值、非整数、≤ 0 或 &gt; ¥10,000；该上限为本模拟商品范围的演示约束。</p></section>
<section><h2>07 · SQL × Pandas 独立对账</h2><p class="caption">两条路径分别从清洗后的三张明细表直接聚合。SQL 源文件：sql/key_metrics.sql。分单位整数严格相等，不使用误差容限。</p><table><thead><tr><th>指标（金额为分）</th><th>Pandas</th><th>SQLite SQL</th><th>校验</th></tr></thead><tbody>{checks}</tbody></table><p class="caption">另用手算样本验证 UV=3、未退款支付订单=3、净销售额=35,000 分，防止两条路径出现相同口径错误；边界覆盖退款、逆序、相同时刻、空订单与观察窗外留存。</p></section>
<section><h2>08 · 可继续验证的问题</h2><ul><li>把跨会话累计漏斗拆为会话漏斗，检验是否因重复访问高估短期购买转化。</li><li>在真实业务中补充退款时间、部分退款金额与支付事件，以分别构建现金流口径和订单最终状态口径。</li><li>用未来窗口或真实实验验证分群阈值，避免把生成器内置的行为差异当作业务发现。</li></ul><p>复现：<code>python -m analytics.run</code>；测试：<code>python -m unittest analytics.tests.test_analysis -v</code>。</p><p class="caption">交付：metrics.json、daily_sales.csv、cohort_retention.csv、rfm_segments.csv、cleaning_audit.csv、reconciliation.csv。代码和指标字典见项目 analytics 目录。</p></section>
<footer>个人学习与求职展示项目 ｜ 本页面无外部脚本、字体或图片依赖，可离线打开 ｜ 数据观察截至 2026-06-30，项目实现于 2026-10</footer>
</main></body></html>'''
