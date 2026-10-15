# 电商用户行为与交易分析

使用 Python、Pandas、NumPy 和 SQLite 构建电商数据分析流程，完成原始数据清洗、交易指标计算、SQL/Pandas 对账、用户漏斗、留存与 RFM 分群，生成可离线打开的图表报告。

## 核心功能

- 校验用户、行为、订单三张表的重复主键、无效时间、用户关联和金额，保存逐项清洗审计。
- 区分已支付、全额退款与未退款订单，采用整数分统一金额口径。
- 分别用 Pandas 和 SQLite SQL 计算 UV、未退款支付订单数及净销售额，逐项核对。
- 构建严格按时间先后发生的浏览→加购→购买跨会话用户漏斗。
- 计算注册 Cohort 月留存、买家复购率和 RFM 规则分群，未完整观察月份保持空值。
- 输出 CSV 明细、JSON 指标及内嵌 SVG 的 HTML 报告。

## 技术栈

Python 3.12、Pandas 3.0.1、NumPy 2.3.5、SQLite、unittest、HTML/SVG。

## 数据与结果

数据由固定随机种子 `20261012` 生成，观察窗口为 2026-01-01 至 2026-06-30。生成器包含重复主键、无效时间、缺失渠道与异常金额，便于复现清洗规则。

| 指标 | 默认结果 |
|---|---:|
| 有效用户 / 行为 / 提交订单 | 1,000 / 33,227 / 4,771 |
| 未退款支付订单 | 3,585 |
| 净销售额 | 922,202.31 元 |
| 浏览→加购→购买用户 | 1,000→998→944 |
| 沉睡买家 / 未购用户 | 144 / 56 |
| SQL/Pandas 对账 | 3 项一致 |
| 指标与边界测试 | 12 项 |

## 快速开始

```powershell
git clone https://github.com/lu-13-debug/ecommerce-user-analytics.git
cd ecommerce-user-analytics
python -m venv .venv
# Windows PowerShell：.venv\Scripts\Activate.ps1
# Linux/macOS：source .venv/bin/activate
python -m pip install -r requirements.txt
python -m analytics.run
python -m unittest analytics.tests.test_analysis -v
```

使用虚拟环境时，先执行注释中的对应激活命令。运行后用浏览器打开 [分析报告](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/report.html)。报告为离线文件，下载仓库后即可查看；GitHub 文件页可直接查看 JSON/CSV。

只重建报告而不保存原始数据：`python -m analytics.run --no-data`。自定义规模：`python -m analytics.run --seed 42 --users 200 --output-dir analytics/outputs-demo`。

## 文件结构

```text
analytics/
  generate.py              固定种子数据生成
  core.py                  清洗、交易指标、漏斗、留存、分群
  sql/key_metrics.sql      SQLite 独立指标计算
  run.py                   一键运行入口
  report.py                HTML/SVG 报告
  METRICS.md               字段与指标口径
  tests/test_analysis.py   手算样本、边界与复现测试
  outputs/                 CSV、JSON 与 HTML 结果
requirements.txt
```

## 输出文件

[指标结果](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/metrics.json)、[指标字典](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/METRICS.md)、[清洗审计](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/cleaning_audit.csv)、[对账结果](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/reconciliation.csv)、[分群明细](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/rfm_segments.csv)、[月留存](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/cohort_retention.csv)、[日销售](https://github.com/lu-13-debug/ecommerce-user-analytics/blob/main/analytics/outputs/daily_sales.csv)。

## 验证设计

以手算真值验证 UV、订单数与净销售额，并测试退款排除、逆序/相等时间、空数据、未购用户、不完整观察月份、清洗计数守恒及固定种子复现。每张表满足输入行数等于输出行数与剔除行数之和；SQL 对账失败会终止运行。
