-- 金额以整数分聚合；相邻记录必须相差一个自然日，才计算日环比。
WITH daily AS (
    SELECT date, store_id, SUM(qty) AS units,
           SUM(qty * unit_price_cents) AS sales_cents
    FROM sales
    GROUP BY date, store_id
), previous AS (
    SELECT *, LAG(date) OVER (PARTITION BY store_id ORDER BY date) AS previous_date,
           LAG(sales_cents) OVER (PARTITION BY store_id ORDER BY date) AS previous_sales_cents
    FROM daily
)
SELECT date, store_id, units, sales_cents, previous_sales_cents,
       CASE WHEN julianday(date) - julianday(previous_date) = 1
                 AND previous_sales_cents > 0
            THEN 1.0 * (sales_cents - previous_sales_cents) / previous_sales_cents
            ELSE NULL END AS dod_rate
FROM previous
ORDER BY date, store_id;
