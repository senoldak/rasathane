# src/opsi/logging.py
"""Structured logging: scan_id on every line, single format."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any


class ScanAdapter(logging.LoggerAdapter[logging.Logger]):
    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra: dict[str, Any] = dict(self.extra or {})
        extra.update(kwargs.pop("extra", {}))
        kwargs["extra"] = extra
        return msg, kwargs


class _VarsayilanScan(logging.Filter):
    """scan_id taşımayan kayıtlar (kanal, ETF) "-" ile yazılır; biçim hatası vermez."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "scan_id"):
            record.scan_id = "-"
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Attaches the root logger to a single scan_id format (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_VarsayilanScan())
    handler.setFormatter(
        logging.Formatter("%(asctime)s scan=%(scan_id)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger("opsi")
    root.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)


def get_scan_logger(scan_id: int | str) -> ScanAdapter:
    """Returns a logger bound to the given scan."""
    setup_logging()
    return ScanAdapter(logging.getLogger("opsi.scan"), {"scan_id": str(scan_id)})
