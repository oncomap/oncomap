#!/usr/bin/env python3
"""Structured run logging for pipeline and extract runs.

Each build/extract/monitor run appends one JSON line to logs/runs.jsonl and
echoes it to stderr, carrying a traceable run id, the tool name, a UTC
timestamp, a duration, a status, and tool-specific metrics (record counts,
validation failures, dead links, extraction confidence, ...). One run id is
shared across a pipeline when ONCOMAP_RUN_ID is set in the environment, so a
validate -> compile -> check sequence in one CI job is correlatable.

Kept dependency-free (stdlib only) so it runs anywhere the pipeline runs. In
GitHub Actions the same record is appended to the job summary for at-a-glance
visibility; logs/runs.jsonl is uploaded as a build artifact (the "lightweight
store" the spec's gap note calls for).

Usage:
    import runlog
    with runlog.run("validate") as log:
        log.metrics(records=79, invalid=0)
        # ... status defaults to "ok"; set log.status = "fail" on error
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
RUNS = LOG_DIR / "runs.jsonl"


def run_id() -> str:
    """A traceable run id, shared across a pipeline via ONCOMAP_RUN_ID."""
    env = os.environ.get("ONCOMAP_RUN_ID")
    if env:
        return env
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6]


class _Run:
    def __init__(self, tool: str, rid: str):
        self.tool = tool
        self.run_id = rid
        self.status = "ok"
        self._start = time.perf_counter()
        self._metrics: dict = {}

    def metrics(self, **kw) -> "_Run":
        self._metrics.update(kw)
        return self

    def record(self) -> dict:
        entry = {
            "run_id": self.run_id,
            "tool": self.tool,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "duration_ms": round((time.perf_counter() - self._start) * 1000),
            "status": self.status,
            **self._metrics,
        }
        try:
            LOG_DIR.mkdir(exist_ok=True)
            with RUNS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # logging must never break the run
        print("[runlog] " + json.dumps(entry, ensure_ascii=False), file=sys.stderr)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with contextlib.suppress(OSError):
                with open(summary, "a", encoding="utf-8") as fh:
                    kv = " · ".join(f"{k}={v}" for k, v in self._metrics.items())
                    fh.write(f"- `{self.tool}` [{self.status}] {kv}\n")
        return entry


def log(tool: str, status: str = "ok", **metrics) -> dict:
    """One-shot: record a single run summary line (for wiring at a return point)."""
    r = _Run(tool, run_id())
    r.status = status
    r.metrics(**metrics)
    return r.record()


@contextlib.contextmanager
def run(tool: str):
    """Context manager: yields a _Run, records one summary line on exit.

    Marks the run "fail" if it exits via an exception, then re-raises.
    """
    r = _Run(tool, run_id())
    try:
        yield r
    except BaseException:
        r.status = "fail"
        r.record()
        raise
    else:
        r.record()
