from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from board_pack_agent.llm import MockProvider, extract_json_object
from board_pack_agent.pipeline import run_analysis
from board_pack_agent.reporting import write_outputs


class PipelineTests(unittest.TestCase):
    def test_extract_json_from_markdown_fence(self) -> None:
        parsed = extract_json_object('```json\n{"executive_summary": "Good month"}\n```')
        self.assertEqual(parsed["executive_summary"], "Good month")

    def test_run_analysis_and_write_outputs(self) -> None:
        rows, snapshot, narrative, context = run_analysis(
            metrics_path=ROOT / "examples" / "startup_metrics.csv",
            context_path=ROOT / "examples" / "company_context.md",
            provider=MockProvider(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_outputs(rows, snapshot, narrative, context, out_dir)
            self.assertTrue((out_dir / "board_pack.md").exists())
            self.assertTrue((out_dir / "investor_update.md").exists())
            self.assertTrue((out_dir / "board_report.html").exists())
            self.assertTrue((out_dir / "charts" / "mrr.svg").exists())


if __name__ == "__main__":
    unittest.main()

