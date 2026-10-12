-- 期间销售额排名，排名相同时使用 RANK 保留并列名次。
WITH stores AS (
    SELECT store_id, SUM(qty * unit_price_cents) AS sales_cents
    FROM sales
    GROUP BY store_id
)
SELECT store_id, sales_cents,
       RANK() OVER (ORDER BY sales_cents DESC) AS sales_rank,
       CASE WHEN SUM(sales_cents) OVER () > 0
            THEN 1.0 * sales_cents / SUM(sales_cents) OVER ()
            ELSE NULL END AS sales_share
FROM stores
ORDER BY sales_cents DESC, store_id;
