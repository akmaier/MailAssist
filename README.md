# MailAssist LLM Mail Processor

MailAssist is a cron-friendly command line job that processes emails from a trusted sender, forwards their body and textual attachments to an OpenAI GPT-5 model, and replies with structured responses. After a successful round-trip the original message is deleted, allowing the mailbox to act as a queue of pending work.

## Features

- Secure IMAP retrieval with trusted sender filtering.
- Text extraction for `.pdf` and `.docx` attachments with configurable limits.
- Single prompt submission to GPT-5 containing body and attachment summaries.
- Plain-text reply composition via SMTP.
- Conditional deletion of processed messages and local audit logging.

## Project Layout

```
mailassist/
    attachment_processor.py  # Attachment parsing and filtering
    cli.py                   # Command line entrypoint
    config.py                # Configuration loading and validation
    email_sender.py          # SMTP wrapper for replies
    imap_client.py           # IMAP utilities and abstractions
    llm_client.py            # OpenAI GPT-5 API integration
    processor.py             # Orchestrates the workflow
    state.py                 # Durable job state helpers
```

Tests live in `tests/` and cover attachment handling and the mailbox queue behaviour.

## Quick start

1. Install dependencies (ideally in a virtual environment):

   ```bash
   pip install -e .[dev]
   ```

2. Create a configuration file (see example below) and export its path:

   ```bash
   export MAILASSIST_CONFIG=./config.yaml
   ```

3. Run the processor:

   ```bash
   python -m mailassist.cli run
   ```

4. Validate your mailbox configuration without invoking the LLM by using test mode:

   ```bash
   python -m mailassist.cli test
   ```

   Test mode downloads the most recent message from a trusted sender (if available) and sends it back to the originating
   address with a `[MailAssist Test]` subject prefix. This end-to-end loop verifies IMAP and SMTP credentials before enabling the
   full LLM-backed workflow.

## Configuration

The job loads configuration from a YAML or JSON file referenced by the `MAILASSIST_CONFIG` environment variable. Configuration values are parsed into lightweight dataclasses. Below is a minimal example:

```yaml
imap:
  host: imap.example.com
  port: 993
  username: job@example.com
  password: ${IMAP_PASSWORD}
  folder: INBOX
smtp:
  host: smtp.example.com
  port: 587
  username: job@example.com
  password: ${SMTP_PASSWORD}
trusted_senders:
  - andreas.maier@fau.de
llm:
  api_key: ${OPENAI_API_KEY}
  model: gpt-5.0
  temperature: 0.2
  max_tokens: 1500
attachment_policy:
  include_pdf_docx: true
  max_attachment_size_mb: 10
  text_extraction_timeout: 30
queue_policy:
  delete_after_success: true
  archive_before_delete: null
state:
  deleted_record_path: ./deleted_uids.log
  failed_record_path: ./failed_uids.log
```

Environment variable placeholders wrapped in `${...}` are expanded when the configuration file is loaded.

## Logging and audit trail

The processor emits structured log lines detailing each step (fetch, LLM submission, reply, deletion). Deleted message UIDs are appended to the configured `deleted_record_path` file for audit purposes, while processing failures are written to the
`failed_record_path` log together with the captured error reason.

## Running tests

```
pytest
```

## Notes

- Attachment extraction uses `pypdf` and a minimal DOCX XML parser. If extraction fails, the processor logs a warning but still continues using the email body.
- Set `queue_policy.delete_after_success` to `false` to disable automatic deletion (useful for dry runs and debugging).
- Optional archiving before deletion is surfaced as a configuration hook for future enhancements.
