"""Readable application logs with request correlation and UTC timestamps."""

import logging
import sys
import time
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id.get()
        return super().format(record)


def configure_logging() -> None:
    logger = logging.getLogger("app")
    if any(getattr(handler, "_margo_handler", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler._margo_handler = True
    handler.setFormatter(RequestFormatter(
        fmt="%(asctime)s.%(msecs)03dZ | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
