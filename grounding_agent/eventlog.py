"""JSON-Lines event log for forensic traceability.

One event per line, written to results/logs/<run_id>/<variant>.jsonl.
The output is intentionally minimal and machine-readable: each record
is `{ts, run_id, variant, event, ...payload}`. No log levels, no
filters, no rotation — these are scoped per run and per variant.

Construction:

    elog = EventLog(run_id, variant, log_dir=Path("results/logs/<run>/"))
    elog.emit("task_start", task_index=0)
    ...
    elog.close()

Or as a context manager:

    with EventLog(run_id, variant, log_dir) as elog:
        elog.emit(...)

If `log_dir` is None the log is a no-op (every emit returns silently,
file handle is None, close is a no-op). This keeps the call sites in
runner/judges identical whether logging is enabled or not.

Crash safety: every emit calls flush(). At process death you may lose
the last event-in-flight (between emit and flush) but every event the
caller saw return has been pushed to the OS buffer.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, IO


def new_run_id() -> str:
    """Generate a run id like '20260512-211530-abcd12'."""
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


class EventLog:
    def __init__(
        self,
        run_id: str,
        variant: str,
        log_dir: Path | None = None,
    ) -> None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(variant, str) or not variant.strip():
            raise ValueError("variant must be a non-empty string")
        self.run_id = run_id
        self.variant = variant
        self.log_dir: Path | None = log_dir
        self.path: Path | None = None
        self._fh: IO[str] | None = None
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            self.path = log_dir / f"{variant}.jsonl"
            self._fh = open(self.path, "a", encoding="utf-8")

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @property
    def enabled(self) -> bool:
        return self._fh is not None

    def emit(self, event: str, **payload: Any) -> None:
        if not isinstance(event, str) or not event.strip():
            raise ValueError("event name must be a non-empty string")
        if self._fh is None:
            return
        record: dict[str, Any] = {
            "ts": time.time(),
            "run_id": self.run_id,
            "variant": self.variant,
            "event": event,
        }
        # framing fields cannot be overridden by payload. ("event" is a
        # named param of emit() so Python itself prevents that case;
        # we still guard against ts/run_id/variant going through **kw.)
        for k, v in payload.items():
            if k in ("ts", "run_id", "variant"):
                raise ValueError(
                    f"payload key {k!r} would clobber a framing field"
                )
            record[k] = v
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
            finally:
                self._fh.close()
                self._fh = None
