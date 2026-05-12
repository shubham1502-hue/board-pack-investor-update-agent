from __future__ import annotations

import argparse
import os
from pathlib import Path

from .llm import LLMError, get_provider
from .pipeline import run_analysis
from .reporting import write_outputs
from .utils import utc_run_id


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="board-pack-agent",
        description="Turn startup metrics CSVs into board packs and investor updates.",
    )
    parser.add_argument("run", nargs="?", default="run", help="Command to run. Currently only 'run' is supported.")
    parser.add_argument("--metrics", required=True, type=Path, help="Metrics CSV.")
    parser.add_argument("--context", type=Path, help="Company context Markdown file.")
    parser.add_argument("--out", type=Path, help="Output directory. Defaults to outputs/<timestamp>.")
    parser.add_argument("--provider", default="mock", choices=["mock", "gemini", "groq"], help="Narrative provider.")
    parser.add_argument("--risk-config", type=Path, help="Optional JSON file with founder-customized risk thresholds.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Optional env file path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.run != "run":
        parser.error("Only the 'run' command is supported.")

    load_env(args.env_file)
    out_dir = args.out or Path("outputs") / utc_run_id()
    try:
        provider = get_provider(args.provider)
        rows, snapshot, narrative, context = run_analysis(args.metrics, args.context, provider, args.risk_config)
        write_outputs(rows, snapshot, narrative, context, out_dir)
    except (OSError, ValueError, LLMError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Processed {len(rows)} months.")
    print(f"Board pack: {out_dir / 'board_pack.md'}")
    print(f"Investor update: {out_dir / 'investor_update.md'}")
    print(f"HTML report: {out_dir / 'board_report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

