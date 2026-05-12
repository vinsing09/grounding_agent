"""Tests for grounding_agent.eventlog.

Each test exercises one invariant of the emitter:
  - on-disk format is parseable JSON, one event per line
  - framing fields (ts, run_id, variant, event) are always present
  - payload keys cannot collide with framing keys
  - log_dir=None makes every operation a no-op
  - close is idempotent and safe after error
  - context-manager path closes the handle on exit
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from grounding_agent.eventlog import EventLog, new_run_id


def test_new_run_id_is_unique_and_nonempty():
    a = new_run_id()
    b = new_run_id()
    assert isinstance(a, str) and a.strip()
    assert a != b


def test_construction_validates_run_id_and_variant():
    with pytest.raises(ValueError, match="run_id"):
        EventLog("", "v0")
    with pytest.raises(ValueError, match="variant"):
        EventLog("r", "")


def test_emit_appends_jsonl(tmp_path: Path):
    log_dir = tmp_path / "logs"
    elog = EventLog("r-1", "v0", log_dir=log_dir)
    try:
        elog.emit("task_start", task_index=0)
        elog.emit("task_end", task_index=0, reward=1.0)
    finally:
        elog.close()

    f = log_dir / "v0.jsonl"
    assert f.exists()
    lines = f.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    events = [json.loads(l) for l in lines]
    assert {e["event"] for e in events} == {"task_start", "task_end"}
    for e in events:
        assert e["run_id"] == "r-1"
        assert e["variant"] == "v0"
        assert isinstance(e["ts"], float)
        assert e["ts"] > 0


def test_emit_includes_payload(tmp_path: Path):
    log_dir = tmp_path / "logs"
    with EventLog("r-2", "v0", log_dir=log_dir) as elog:
        elog.emit("custom", a=1, b="hello", c=[1, 2, 3], d={"nested": True})
    line = (log_dir / "v0.jsonl").read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["a"] == 1
    assert rec["b"] == "hello"
    assert rec["c"] == [1, 2, 3]
    assert rec["d"] == {"nested": True}


def test_emit_rejects_payload_collision_on_framing_fields(tmp_path: Path):
    """Payload keys cannot shadow ts/run_id/variant. ('event' is a named
    parameter of emit, so Python itself blocks the collision before we
    can.)"""
    log_dir = tmp_path / "logs"
    with EventLog("r-3", "v0", log_dir=log_dir) as elog:
        for k in ("ts", "run_id", "variant"):
            with pytest.raises(ValueError, match="clobber"):
                elog.emit("x", **{k: "boom"})


def test_emit_requires_event_name(tmp_path: Path):
    with EventLog("r-4", "v0", log_dir=tmp_path) as elog:
        with pytest.raises(ValueError, match="event"):
            elog.emit("")


def test_log_dir_none_is_noop(tmp_path: Path):
    elog = EventLog("r-5", "v0", log_dir=None)
    assert elog.enabled is False
    assert elog.path is None
    elog.emit("task_start", task_index=0)  # must not raise
    elog.close()
    # tmp_path should be untouched
    assert not any(tmp_path.iterdir())


def test_separate_variants_write_separate_files(tmp_path: Path):
    log_dir = tmp_path / "logs"
    with EventLog("r-6", "v0", log_dir=log_dir) as e0:
        e0.emit("task_start", task_index=0)
    with EventLog("r-6", "v2", log_dir=log_dir) as e2:
        e2.emit("task_start", task_index=0)
    assert (log_dir / "v0.jsonl").exists()
    assert (log_dir / "v2.jsonl").exists()


def test_close_is_idempotent(tmp_path: Path):
    elog = EventLog("r-7", "v0", log_dir=tmp_path)
    elog.emit("x")
    elog.close()
    elog.close()  # second close must not raise
    assert not elog.enabled


def test_emit_after_close_is_silent(tmp_path: Path):
    elog = EventLog("r-8", "v0", log_dir=tmp_path)
    elog.emit("a")
    elog.close()
    # After close, emit becomes a no-op (matches log_dir=None semantics)
    elog.emit("b")
    lines = (tmp_path / "v0.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "a"


def test_context_manager_closes_handle(tmp_path: Path):
    with EventLog("r-9", "v0", log_dir=tmp_path) as elog:
        elog.emit("x")
        assert elog.enabled
    assert not elog.enabled


def test_appends_to_existing_file(tmp_path: Path):
    """Multiple EventLog instances against the same path append, do not truncate."""
    with EventLog("r-10", "v0", log_dir=tmp_path) as e:
        e.emit("first")
    with EventLog("r-10", "v0", log_dir=tmp_path) as e:
        e.emit("second")
    lines = (tmp_path / "v0.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first"
    assert json.loads(lines[1])["event"] == "second"


def test_event_ts_is_recent(tmp_path: Path):
    t0 = time.time()
    with EventLog("r-11", "v0", log_dir=tmp_path) as e:
        e.emit("now")
    rec = json.loads((tmp_path / "v0.jsonl").read_text())
    assert t0 <= rec["ts"] <= time.time() + 0.1
