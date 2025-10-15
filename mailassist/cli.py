"""Command line interface for MailAssist."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from .config import load_app_config
from .processor import MailProcessor


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MailAssist LLM mail processor")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--config", dest="config", help="Path to configuration file")
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Python logging level (default: INFO)")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")


def run_processor(config_path: Optional[str]) -> None:
    config = load_app_config(config_path)
    processor = MailProcessor(config)
    processor.run()


def main(argv: Optional[list[str]] = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    if args.command == "run":
        run_processor(args.config)
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
