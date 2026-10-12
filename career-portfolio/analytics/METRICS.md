# 字段、指标与清洗口径

数据类型：**合成数据**。观察窗 `[2026-01-01 00:00:00, 2026-06-30 23:59:59]`，含两端。所有日期为上海本地时间，不做跨时区换算。金额用整数分，不依赖浮点近似。

## 三张明细表

| 字段 | 类型 / 定义 | 规则 |
|---|---|---|
| users.user_id | 正整数用户主键 | 缺失、非正整数剔除；重复键保留首条 |
| users.registered_at | 注册时间 | 解析失败、窗前或窗后剔除 |
| users.channel | 注册来源标签 | 缺失填“未知”，只作演示，不进行渠道归因 |
| events.event_id | 行为主键 | 缺失剔除，重复键保留首条 |
| events.user_id | 用户外键 | 不在清洗后 users 中则剔除 |
| events.event_time | 行为时间 | 解析失败、早于注册或晚于截止剔除 |
| events.event_type | browse / cart / purchase | 其他值剔除 |
| events.product_id | 模拟商品 ID | 缺失剔除；没有商品维表 |
| orders.order_id | 订单主键 | 缺失剔除，重复键保留首条 |
| orders.user_id | 用户外键 | 不在清洗后 users 中则剔除 |
| orders.created_at | 提交时间 | 解析失败、早于注册或晚于截止剔除 |
| orders.paid_at | 支付时间 | paid/refunded 必须有效且 created_at ≤ paid_at ≤ 截止；其他状态置空 |
| orders.status | paid / refunded / cancelled / pending | paid=已付未退，refunded=曾付后全额退款；非法值剔除 |
| orders.amount_cents | 整数分订单金额 | 缺失、非有限数、非整数、≤0 或 >1,000,000 分剔除 |

异常金额上限 ¥10,000 是模拟商品范围的规则，实际业务需结合商品与风控规则设置。重复键保留首条只适用于本演示注入的重复记录；真实多版本订单需按更新时间、状态迁移和权威源处理。

## 交易与用户指标

| 输出键 | 中文定义 | 计算口径 |
|---|---|---|
| uv | 行为活跃用户数 | events 所有有效事件 user_id 去重数；不等于注册人数或仅浏览 UV |
| paid_orders | 未退款支付订单数 | orders.status = paid 的行数 |
| net_sales_cents | 净销售额（分） | paid 的 amount_cents 之和；全额退款整单排除 |
| gross_paid_cents | 曾支付总额（分） | paid + refunded 的 amount_cents 之和 |
| refunded_cents | 全额退款额（分） | refunded 的 amount_cents 之和 |
| submitted_orders | 有效提交订单数 | 清洗后所有 orders 行数 |
| transacted_orders | 曾支付订单数 | paid + refunded 行数 |
| payment_rate | 提交订单支付率 | transacted_orders / submitted_orders；分母为 0 返回 0 |
| net_buyers | 未退款买家数 | 至少一笔 paid 订单的用户数 |
| repeat_buyers | 复购买家数 | paid 订单数 ≥2 的用户数 |
| repeat_purchase_rate | 买家复购率 | repeat_buyers / net_buyers；分母为 0 返回 0 |

`gross_paid_cents - refunded_cents = net_sales_cents`。报告每日净销售额按 `paid_at` 的自然日聚合，只包含最终状态为 paid 的订单，缺少成交日期补 0。退款时间不可用，因此不是当天退款现金流报表；历史日数值按最终状态回溯。

默认数据生成器的退款为全额退款。不把支付事件 `purchase` 数量当作支付订单数，交易指标以订单明细为准。

## 漏斗

用户级，跨会话、跨商品，在整个观察窗累计：

1. browse：至少一个有效 browse 事件的用户。
2. cart：该用户至少一个 cart 事件，严格晚于其首次 browse。
3. purchase：该用户至少一笔 paid 订单，其 paid_at 严格晚于第 2 步最早满足条件的 cart。

相同时刻不算“之后”；加购在浏览前不算下一层；退款订单不算完成购买。同一用户同一层只计一次。没有会话限制、商品一致限制或转化时限，所以不能当作会话转化率或广告转化归因。

## Cohort 月留存

- cohort：用户注册自然月，格式 `YYYY-MM`。
- month_index：目标自然月减注册自然月，M0 为注册当月，M1 为次月。
- cohort_users：该注册月所有有效注册用户，包含未活跃用户。
- active_users：目标月有任一有效事件的去重 cohort 用户数。
- retention：active_users / cohort_users；观察到完整目标自然月才展示。
- 未观察或当前不完整月份：CSV 空白、JSON 不承载单元值、HTML “—”。已完整观察但无人活跃：明确为 0。
- M0 可低于 100%，因为注册不是活跃事件；不是“首次活跃 cohort”。

留存不是购买留存，也不是精确注册后第 30 天留存。截止数据精度为秒，目标月最后一天到 `23:59:59` 才算完整观察。

## RFM 与分群

仅统计 paid 订单，用户级输出，全体有效 users 左连接，包含未购用户。

| 字段 | 定义 |
|---|---|
| recency_days / R | 截止日自然日 − 最近一次未退款支付自然日；未购为空 |
| frequency / F | 观察窗内未退款支付订单数；未购为 0 |
| monetary_cents / M | 观察窗内净销售额，整数分；未购为 0 |

按以下优先级互斥分群：

1. F=0 → 未购用户。
2. R>60 → 沉睡买家。
3. R≤60 且 F≥3 且 M≥50,000 分 → 高价值活跃买家。
4. R≤60 且 F≥2 → 活跃复购买家。
5. 其余有购买者 → 活跃首购买家。

这些是可解释的演示阈值，不是训练所得模型，也未验证营销收益。因为只有半年观察，频次和金额受注册时间影响，真实应用应控制 tenure / 生命周期。

## 审计与对账

清洗阶段对每张表按顺序剔除，计数互斥。用户：缺失 ID→非法 ID→重复 ID→非法时间；行为/订单：缺失 ID→重复 ID→无效用户→非法时间→类型/状态→缺失商品/非法金额。跨表先清洗 users，再校验事件和订单外键。

每张表记录 input_rows、output_rows、removed 各原因计数；填补记录在 imputed，不混入剔除数。对账将清洗后的三张原始粒度明细送入内存 SQLite，再执行实际 `.sql` 文件。对 uv、paid_orders、net_sales_cents 与 Pandas 结果逐项整数相等校验，失败时终止。

测试中的独立手算样本不是随机生成器输出，能防止“SQL 与 Pandas 一致但两者同错”。默认合成规模用于展示，边界样本用于证明口径。
