from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from board_pack_agent.metrics import analyze_metrics, load_metrics, load_risk_rules
from board_pack_agent.models import MetricRow


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

    def test_custom_risk_rule_changes_runway_warning(self) -> None:
        rows = [
            MetricRow(
                month="2026-05",
                mrr=100000,
                churn_rate=2.5,
                cac=100,
                burn=50000,
                runway_months=16,
                activation_rate=60,
                pipeline=400000,
            ),
            MetricRow(
                month="2026-06",
                mrr=110000,
                churn_rate=2.5,
                cac=95,
                burn=51000,
                runway_months=14,
                activation_rate=60,
                pipeline=400000,
            ),
        ]

        default_snapshot = analyze_metrics(rows)
        custom_snapshot = analyze_metrics(rows, {"low_runway_months": 15})

        self.assertFalse(any("below 15 months" in risk for risk in default_snapshot.risks))
        self.assertTrue(any("below 15 months" in risk for risk in custom_snapshot.risks))

    def test_load_risk_rules_merges_seed_stage_config(self) -> None:
        rules = load_risk_rules(ROOT / "configs" / "seed-stage-risk-rules.json")

        self.assertEqual(rules["low_runway_months"], 9)
        self.assertEqual(rules["activation_decision_rate"], 55)


if __name__ == "__main__":
    unittest.main()

