"""Command line interface for MailAssist."""

from __future__ import annotations

import argparse
import logging
from email.utils import parseaddr
from typing import Optional

from .config import load_app_config
from .email_sender import EmailSender
from .imap_client import ImapClient
from .processor import MailProcessor, extract_plain_text


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MailAssist LLM mail processor")
    parser.add_argument("command", choices=["run", "test"], help="Command to execute")
    parser.add_argument("--config", dest="config", help="Path to configuration file")
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Python logging level (default: INFO)")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")


def run_processor(config_path: Optional[str]) -> None:
    config = load_app_config(config_path)
    processor = MailProcessor(config)
    processor.run()


def run_test_mode(config_path: Optional[str]) -> None:
    config = load_app_config(config_path)
    logger = logging.getLogger(__name__)
    logger.info("Running MailAssist test mode")
    with ImapClient(config.imap, logger=logger) as imap_client:
        envelopes = imap_client.fetch_messages(config.trusted_senders)
    if not envelopes:
        logger.info("No messages from trusted senders found for test mode")
        return
    envelope = envelopes[0]
    sender_address = parseaddr(envelope.message.get("From", ""))[1]
    target_address = sender_address or config.trusted_senders[0]
    subject = envelope.message.get("Subject", "(no subject)")
    body_text = extract_plain_text(envelope.message)
    email_sender = EmailSender(config.smtp, logger=logger)
    email_sender.send_mail(target_address, f"[MailAssist Test] {subject}", body_text)
    logger.info("Forwarded message UID %s to %s for configuration validation", envelope.uid, target_address)


def main(argv: Optional[list[str]] = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    if args.command == "run":
        run_processor(args.config)
    elif args.command == "test":
        run_test_mode(args.config)
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
