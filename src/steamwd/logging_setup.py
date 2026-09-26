"""Logging setup with secret redaction."""

import logging
import queue
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

__all__ = ["REDACTED", "QueueTextHandler", "RedactingFilter", "Redactor", "configure_logging"]

REDACTED = "********"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_APP_LOGGER = "steamwd"


class Redactor:
    """Thread-safe registry of secrets that must never appear in logs."""

    def __init__(self) -> None:
        """Create an empty redactor."""
        self._secrets: set[str] = set()
        self._lock = threading.Lock()

    def add(self, secret: str | None) -> None:
        """Register a secret. Very short values are ignored to avoid mangling logs."""
        if secret and len(secret) >= 3:
            with self._lock:
                self._secrets.add(secret)

    def redact(self, text: str) -> str:
        """Replace every registered secret in ``text``."""
        with self._lock:
            secrets = sorted(self._secrets, key=len, reverse=True)
        for secret in secrets:
            text = text.replace(secret, REDACTED)
        return text


class RedactingFilter(logging.Filter):
    """Logging filter that removes secrets from the rendered message."""

    def __init__(self, redactor: Redactor) -> None:
        """Create a filter backed by ``redactor``."""
        super().__init__()
        self._redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place; always lets it through."""
        message = record.getMessage()
        record.msg = self._redactor.redact(message)
        record.args = None
        return True


class QueueTextHandler(logging.Handler):
    """Puts formatted log lines on a queue so the GUI can display them."""

    def __init__(self, target: "queue.Queue[object]", wrap: type) -> None:
        """Create a handler that puts ``wrap(text)`` on ``target``."""
        super().__init__()
        self._target = target
        self._wrap = wrap

    def emit(self, record: logging.LogRecord) -> None:
        """Queue the formatted record."""
        try:
            self._target.put(self._wrap(self.format(record)))
        except Exception:  # noqa: BLE001 - logging must never raise
            self.handleError(record)


def configure_logging(
    log_dir: Path, level: str, redactor: Redactor, extra_handlers: list[logging.Handler] | None = None
) -> None:
    """(Re)configure the ``steamwd`` logger. Safe to call again after settings change."""
    app_logger = logging.getLogger(_APP_LOGGER)
    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)
        if not isinstance(handler, QueueTextHandler):
            handler.close()
    app_logger.setLevel(level)
    app_logger.propagate = False

    handlers: list[logging.Handler] = list(extra_handlers or [])
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_dir / "steamwd.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        )
    except OSError as exc:
        handlers.append(logging.StreamHandler())
        app_logger.warning("Could not open log file in %s: %s", log_dir, exc)

    redacting_filter = RedactingFilter(redactor)
    formatter = logging.Formatter(_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(redacting_filter)
        app_logger.addHandler(handler)
