import logging

from steamwd.logging_setup import REDACTED, RedactingFilter, Redactor


def test_redactor_replaces_secrets() -> None:
    redactor = Redactor()
    redactor.add("hunter2")
    redactor.add("ab")  # too short, ignored
    redactor.add(None)
    assert redactor.redact("+login bob hunter2 ab") == f"+login bob {REDACTED} ab"


def test_filter_redacts_formatted_args() -> None:
    redactor = Redactor()
    redactor.add("s3cret!")
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "Running %s", ("+login bob s3cret!",), None)
    assert RedactingFilter(redactor).filter(record)
    assert record.getMessage() == f"Running +login bob {REDACTED}"
