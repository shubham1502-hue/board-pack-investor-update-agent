from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from board_pack_agent.metrics import analyze_metrics, load_metrics


class MetricsTests(unittest.TestCase):
    def test_load_metrics_and_analyze_latest_month(self) -> None:
        rows = load_metrics(ROOT / "examples" / "startup_metrics.csv")
        snapshot = analyze_metrics(rows)

        self.assertEqual(len(rows), 6)
        self.assertEqual(snapshot.latest.month, "2026-04")
        self.assertGreater(snapshot.mrr_growth_pct, 10)
        self.assertLess(snapshot.latest.churn_rate, 3.5)
        self.assertTrue(snapshot.risks)
        self.assertTrue(snapshot.decisions)

    def test_requires_at_least_two_months(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.csv"
            path.write_text(
                "month,mrr,churn_rate,cac,burn,runway_months,activation_rate,pipeline\n"
                "2026-04,100,3,10,50,12,45,500\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_metrics(path)


if __name__ == "__main__":
    unittest.main()

