-- 独立于 Pandas 的原表聚合；金额为整数分。
-- paid 表示支付且未退款，refunded 表示曾支付后全额退款。
SELECT
    (SELECT COUNT(DISTINCT user_id) FROM events) AS uv,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) AS paid_orders,
    COALESCE(SUM(CASE WHEN status = 'paid' THEN amount_cents ELSE 0 END), 0) AS net_sales_cents
FROM orders;
