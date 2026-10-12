# 电商用户行为与交易分析

**个人实战项目，全部为固定种子生成的合成数据。** 项目实现于 2026.10，观察窗口为 2026.01—2026.06，不对应任何真实平台或企业，不声称带来业务提升。

围绕“数据是否可信、用户是否完成购买、买家是否复购、注册用户是否回访”，实现数据生成、清洗审计、SQL/Pandas 独立对账、顺序漏斗、RFM 规则分群和注册 cohort 月留存。输出可离线展示的 HTML 图表报告和可复核的 CSV/JSON。

## 快速开始

本项目已在 Python 3.12、Pandas 3.0.1 和 NumPy 2.3.5 下验证，推荐使用同一环境。无需 matplotlib、pytest、数据库服务或网络数据源。依赖版本见根目录 requirements.txt；SQLite、unittest 和 HTML/SVG 输出均使用标准库。

在 `career-portfolio` 根目录执行：

```powershell
python -m analytics.run
python -m unittest analytics.tests.test_analysis -v
```

默认种子 `20261012`，生成 1,000 位用户。首次运行会创建 `analytics/data/`，保存三份原始 CSV 和清洗后 SQLite 数据库；该目录不进入版本控制。

```powershell
# 只重建展示产物，不保存明细数据
python -m analytics.run --no-data
# 自定义规模、种子及输出目录
python -m analytics.run --seed 42 --users 200 --output-dir analytics/outputs-demo
```

打开 `analytics/outputs/report.html` 即可离线查看，无 CDN、外部字体或图片。输出目录可重建，会覆盖本项目同名产物。演示时优先使用默认参数与已发布结果保持一致。

## 默认运行的真实输出

下列数值来自脚本实际运行，完整机器可读记录见 [metrics.json](outputs/metrics.json)。

| 项目 | 结果 |
|---|---:|
| 清洗后用户 / 事件 / 提交订单 | 1,000 / 33,227 / 4,771 |
| 行为活跃 UV | 1,000 |
| 未退款支付订单 | 3,585 |
| 支付总额（含后续全额退款） | ¥1,025,446.41 |
| 全额退款金额 | ¥103,244.10 |
| 净销售额 | ¥922,202.31 |
| 提交订单支付率（含后续退款） | 83.57% |
| 买家复购率 | 815 / 944 = 86.33% |
| 顺序用户漏斗：浏览 → 加购 → 购买 | 1,000 → 998 → 944 |
| SQL/Pandas 独立核对 | UV、支付订单数、净销售额，3 项 PASS |

此模拟样本为半年累计观察，且生成器会为每位用户生成多次访问，因此 UV 接近总注册用户、累计漏斗转化和复购比例较高。**这些比例体现生成设定，不应作为行业基准或单次会话表现。** 项目能力在于口径、审计与可复现计算，而非制造增长结果。

## 数据结构

| 表 | 粒度与关键字段 |
|---|---|
| users | 一行一位用户：user_id、registered_at、channel |
| events | 一行一个行为：event_id、user_id、event_type、event_time、product_id |
| orders | 一行一笔订单：order_id、user_id、created_at、paid_at、status、amount_cents |

行为类型为 `browse / cart / purchase`。订单状态为 `paid / refunded / cancelled / pending`，仅演示全额退款，不含优惠、运费、税额、部分退款及退款时间。金额为整数分，时间为上海本地无时区时间，精度至秒。

生成器会确定性注入重复主键、缺失渠道、缺失/非法/未来时间、无效外键、负金额和超阈值金额。清洗规则按顺序应用，剔除原因互斥计数；每张表均满足 `输入行数 = 输出行数 + 各剔除原因行数之和`。渠道填补单独计数，不算剔除。详见 [指标字典](METRICS.md)。

## 分析和验证

- **独立对账**：Pandas 直接聚合清洗明细；SQLite 实际执行 [key_metrics.sql](sql/key_metrics.sql)，再次从明细聚合，金额以分严格比较；不从 Pandas 结果表反算 SQL。对账失败立即抛出异常。
- **顺序用户漏斗**：找到每位用户首次浏览，再找严格晚于浏览的加购，再找严格晚于该加购的未退款支付。跨会话、跨商品，用户每层只计一次；不是同商品转化或广告归因模型。
- **注册 cohort 留存**：以全部注册用户为分母，目标月有任一有效事件为活跃；M0 不强制为 100%；未完整观察月份保持空值，报告显示“—”。
- **RFM 规则分群**：未退款支付订单计算最近购买距截止日天数、次数和累计金额。包含未购用户；固定规则便于解释，未进行真实营销效果实验。
- **测试**：手算真值验证 `UV=3、支付订单=3、净销售额=35,000 分`，另覆盖退款排除、时间逆序与相等、空数据、未购买用户、部分月份和月末未结束、脏数据审计守恒、固定种子复现，以及完整报告输出。

SQL 与 Pandas 一致只能证明两条实现一致，因此额外使用独立手算样本防止两条路径出现同样口径错误。

## 文件导航

```text
analytics/
  generate.py             # 固定种子合成数据与异常注入
  core.py                 # 清洗、指标、漏斗、cohort、RFM
  sql/key_metrics.sql     # SQLite 独立关键指标聚合
  report.py               # 内联 SVG 离线报告
  run.py                  # 一键入口
  tests/test_analysis.py  # 12 个 unittest
  METRICS.md              # 指标、字段与限制
  outputs/
    report.html           # 演示首选入口
    metrics.json          # 指标、种子、观察窗、审计和对账
    daily_sales.csv       # 补齐自然日的金额及订单序列
    cohort_retention.csv  # 注册 cohort 留存，未观察值为空
    rfm_segments.csv      # 用户级 R/F/M 与分群
    cleaning_audit.csv    # 按规则清洗、填补计数
    reconciliation.csv    # SQL/Pandas 三项对账
  data/                   # 运行时生成，不发布
```

## 三分钟演示与简历表述

1. 打开报告，说明“这是合成数据个人项目”，展示观察窗和四张指标卡。
2. 展示清洗审计和 SQL/Pandas 对账，解释为什么需要手算样本；代码中指出订单退款口径。
3. 展示顺序漏斗及 cohort，说明跨会话累计、M0 与观察窗外空值；运行测试及一键入口。

可用于简历的事实表述：

> 基于 Python/Pandas 与 SQLite 构建电商合成数据分析流程，生成 1,000 位用户、3.32 万条有效行为和 4,771 笔订单；实现清洗审计、顺序漏斗、复购、RFM 分群与 cohort 留存，完成 UV、支付订单数及净销售额 3 项独立对账，输出离线 HTML 报告，12 项测试覆盖指标边界与可复现性。

暂未覆盖：真实业务接入、部分退款、退款现金流、会话级归因、统计显著性、A/B 实验与自动调度。需要这些数据与验证后才可讨论真实经营决策。
