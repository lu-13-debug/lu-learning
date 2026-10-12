"""用已知结果核验日报口径；运行目录固定在本项目中。"""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RetailTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / "run.py"
        self.assertTrue(source.exists(), "日报实现尚不存在，先记录红灯测试")
        spec = importlib.util.spec_from_file_location("retail_run", source)
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)

    @staticmethod
    def sale(day, cents=10000, store="S01", qty=1):
        return {"date": day, "store_id": store, "sku": "SKU01",
                "qty": qty, "unit_price_cents": cents}

    def test_integer_money_and_sql_total(self):
        daily, ranking = self.app.analyze([
            self.sale("2026-01-01", 1999, qty=3),
            self.sale("2026-01-01", 1001, store="S02", qty=2)])
        self.assertEqual(sum(r["sales_cents"] for r in daily), 7999)
        self.assertEqual(ranking[0]["sales_cents"], 5997)
        self.assertAlmostEqual(sum(r["sales_share"] for r in ranking), 1.0)

    def test_sql_day_over_day(self):
        daily, _ = self.app.analyze([self.sale("2026-01-01", 10000),
                                     self.sale("2026-01-02", 12500)])
        self.assertEqual(daily[1]["dod_rate"], 0.25)
        self.assertIsNone(daily[0]["dod_rate"])

    def test_zero_denominator_is_unavailable(self):
        daily, _ = self.app.analyze([self.sale("2026-01-01", 0),
                                     self.sale("2026-01-02", 10000)])
        self.assertIsNone(daily[1]["dod_rate"])

    def test_missing_date_baseline_and_dod_unavailable(self):
        rows = [self.sale(f"2026-01-{i:02d}") for i in [1, 2, 3, 4, 5, 6, 8, 9]]
        daily, _ = self.app.analyze(rows)
        self.assertIsNone(daily[-1]["baseline_cents"])
        self.assertIsNone(daily[-2]["dod_rate"])
        self.assertFalse(daily[-1]["is_anomaly"])

    def test_first_seven_dates_have_no_baseline(self):
        daily, _ = self.app.analyze([self.sale(f"2026-01-{i:02d}") for i in range(1, 8)])
        self.assertTrue(all(r["baseline_cents"] is None for r in daily))
        self.assertFalse(any(r["is_anomaly"] for r in daily))

    def test_normal_sample_no_false_alarm_and_strict_threshold(self):
        rows = [self.sale(f"2026-01-{i:02d}") for i in range(1, 8)]
        rows.append(self.sale("2026-01-08", 6000))
        daily, _ = self.app.analyze(rows)
        self.assertEqual(daily[-1]["baseline_cents"], 10000)
        self.assertFalse(any(r["is_anomaly"] for r in daily))

    def test_injected_drop_is_detected(self):
        daily, _ = self.app.analyze(self.app.generate_sales())
        hits = [(r["date"], r["store_id"]) for r in daily if r["is_anomaly"]]
        self.assertEqual(hits, [("2026-02-14", "S03")])

    def test_generation_is_reproducible_and_covers_480_store_dates(self):
        rows = self.app.generate_sales()
        self.assertEqual(rows, self.app.generate_sales())
        self.assertEqual(len({(r["date"], r["store_id"]) for r in rows}), 480)
        self.assertTrue(all(isinstance(r["unit_price_cents"], int) for r in rows))

    def test_export_reconciles_source_and_outputs(self):
        folder = ROOT / "_tests_runtime"
        self.app.run_pipeline(folder)
        metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["sales_cents"], metrics["source_sales_cents"])
        self.assertEqual(metrics["daily_rows"], 480)
        self.assertEqual(metrics["anomaly_count"], 1)
        self.assertIn("模拟数据", (folder / "report.html").read_text(encoding="utf-8"))
        for filename in ["sales.csv", "daily_report.csv", "store_ranking.csv",
                         "anomalies.csv", "metrics.json", "report.html"]:
            self.assertTrue((folder / filename).is_file())
            (folder / filename).unlink()
        folder.rmdir()


if __name__ == "__main__":
    unittest.main()
