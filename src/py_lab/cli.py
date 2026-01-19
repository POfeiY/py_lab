from __future__ import annotations

import argparse
import logging

from py_lab.logging_utils import setup_logging

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="py-lab")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--input", type=str, help="Input CSV path")
    parser.add_argument("--out", type=str, default="out", help="Output directory")
    parser.add_argument("--hist", type=str, help="Numeric column to plot histogram for")

    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    logger = logging.getLogger("py_lab")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input:
        from pathlib import Path

        from py_lab.data_pipeline import basic_clean, load_csv, summarize

        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        df = basic_clean(load_csv(args.input))
        summary = summarize(df)

        (out_dir / "summary.json").write_text(summary.to_json(), encoding="utf-8")
        logger.info(f"Wrote: {out_dir / 'summary.json'}")

        if args.hist:
            from py_lab.data_pipeline import save_numeric_hist

            png_path = out_dir / "hist.png"
            save_numeric_hist(df, args.hist, png_path)
            logger.info(f"Wrote: {png_path}")

        return 0

    if args.version:
        logger.info("py-lab 0.1.0")
        return 0

    parser.print_help()
    return 0
