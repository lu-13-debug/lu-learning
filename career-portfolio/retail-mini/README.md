# 零售门店销售日报与异常分析

使用 Python 与 SQLite 将 SKU 销售流水整理为门店日报，计算日环比、销售排名和占比，并以历史中位数识别销售下滑，输出可追溯 CSV 和离线 HTML/SVG 报告。

## 核心功能

- 汇总门店每日销量和销售额，以整数分计算金额。
- 使用 SQL 窗口函数计算日环比和门店期间排名。
- 以同店过去 7 个完整自然日销售中位数为基线，标记当日金额低于正基线 60% 的日期。
- 缺少前一自然日、零分母或历史窗口不完整时保留空值。
- 输出日报、门店排名、异常清单、指标 JSON 以及内嵌 SVG 的报告。

## 技术栈

Python 3.10+ 标准库、SQLite SQL、unittest、CSV/JSON、HTML/SVG，无第三方依赖。

## 数据与结果

固定种子 `20261012` 生成 8 家门店、60 天、12 个 SKU 的 5,760 行流水。每行是一个门店在某日期某 SKU 的销量汇总。生成器在 `2026-02-14 / S03` 注入销量下滑，用于检验异常规则。

| 指标 | 默认结果 |
|---|---:|
| 流水 / 门店日报 | 5,760 / 480 行 |
| 期间销售额 | 1,789,924.75 元 |
| 完整历史基线 | 424 个门店日期 |
| 检出异常 | 2026-02-14 / S03 |
| 异常当日销售 / 基线 | 579.25 / 3,181.75 元 |
| 金额、日期与规则测试 | 9 项 |

## 快速开始

```powershell
git clone https://github.com/lu-13-debug/retail-sales-analysis.git
cd retail-sales-analysis
python run.py
python -m unittest discover -s tests -v
```

下载仓库后，用浏览器打开 [销售分析报告](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/report.html)。HTML 与 CSV 保持在同一目录，报告中的明细链接即可正常使用。

## 文件结构

```text
run.py                       数据生成、分析与导出入口
sql/daily_report.sql         日报与日环比
sql/store_ranking.sql        门店排名与占比
tests/test_retail.py         9 项口径与边界测试
reports/retail/              CSV 明细、metrics.json、report.html
```

## 指标与复核

销售额为 `SUM(qty * unit_price_cents)`。日环比为 `(当天金额 - 昨天金额) / 昨天金额`；`LAG()` 后检查日期相邻性。异常基线不包含当天，历史缺日、前 7 天及零基线不进行异常判断。

[流水](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/sales.csv)、[日报](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/daily_report.csv)、[排名](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/store_ranking.csv)、[异常清单](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/anomalies.csv)、[指标 JSON](https://github.com/lu-13-debug/retail-sales-analysis/blob/main/reports/retail/metrics.json)。筛选异常门店日期的 12 行流水，汇总数量乘单价，再对照前 7 天金额中位数，即可复核标记原因。

测试覆盖整数金额与 SQL 对账、日环比、零分母、缺日窗口、正常及临界阈值、预设异常、可复现性和导出一致性。
