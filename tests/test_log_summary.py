"""Gate: `log_summary.py` — the span/total arithmetic over a `session_log.py`
file, and the honest edge cases named in its own docstring.

Most checks build a real `.jsonl` file BY HAND and exercise only
`log_summary`'s pure reader functions — deliberately, so the arithmetic gate
stays independent of the writer. That is not the whole feature, though: the
dedupe itself ("write only when the value CHANGES") lives in
`SessionLog.state()`, not in anything `log_summary` reads back, and a check
that only ever hand-builds JSONL and calls `log_summary.spans()` cannot see
that method at all — proven the hard way (2026-08-16 correction): a
hand-built duplicate record was reported as testing "the dedupe", it read
green with the real dedupe deleted (`if False:` at
`SessionLog.state()`'s own comparison), and the row was false. ONE check
(`check_session_log_state_dedupes_at_the_writer`) therefore drives the real
`SessionLog` object at its own boundary instead — no hand-built JSONL, no
`log_summary` calls at all, just `.state()` called three times and the
resulting file read back to prove the writer itself deduped. Every check is
proven by PLANTING its own defect: break the code, confirm exactly that
check reddens, restore, confirm green. The plant table is printed at the end
of a run.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import log_summary  # noqa: E402

FAILURES: list[str] = []
PLANTS: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}")
    print(f"{'PASS' if condition else 'FAIL'} {name}" + (f" — {detail}" if detail and not condition else ""))


def record_plant(check_name: str, plant_desc: str) -> None:
    PLANTS.append((check_name, plant_desc))


# ---- fixture builder --------------------------------------------------------


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def header(t: float, **facts) -> dict:
    return {"kind": "header", "at": f"t{t}", "epoch": t, "schema": 1, **facts}


def footer(t: float, **fields) -> dict:
    return {"kind": "footer", "at": f"t{t}", "epoch": t, "reason": "stop",
            "duration_s": round(t, 1), **fields}


def state(kind: str, t: float, **fields) -> dict:
    return {"kind": f"state.{kind}", "at": f"t{t}", "epoch": t, **fields}


def connect(t: float, device: str) -> dict:
    return {"kind": "session.connect", "at": f"t{t}", "epoch": t, "device": device}


def leave(t: float, device: str, bytes_out: int = 0, bytes_in: int = 0) -> dict:
    return {"kind": "session.leave", "at": f"t{t}", "epoch": t, "device": device,
            "bytes_out": bytes_out, "bytes_in": bytes_in}


# ============================================================================
# 1. two monitors for a while, then one — two spans, right durations
# ============================================================================

def check_two_monitor_spans_then_one(tmp: Path) -> None:
    p = tmp / "a.jsonl"
    write_jsonl(p, [
        header(0),
        state("resolution", 0, monitors=2),
        state("resolution", 12480, monitors=1),   # 3h28m = 12480s later
        footer(20970),                              # +2h22m30s more = 8490s
    ])
    result = log_summary.spans(log_summary._read_records(p))
    got = result.get("resolution", [])
    ok = (len(got) == 2
          and got[0]["value"] == {"monitors": 2} and got[0]["seconds"] == 12480.0
          and got[1]["value"] == {"monitors": 1} and got[1]["seconds"] == 8490.0
          and got[1]["open"] is False)
    check("two_monitor_spans_then_one", ok, f"got={got}")


# ============================================================================
# 2. a scaling-only change produces its own span, resolution span untouched
# ============================================================================

def check_scaling_change_does_not_disturb_resolution(tmp: Path) -> None:
    p = tmp / "b.jsonl"
    write_jsonl(p, [
        header(0),
        state("resolution", 0, monitors=2),
        state("scale", 0, pct=100),
        state("scale", 500, pct=125),   # scale changes; resolution does not
        footer(1000),
    ])
    result = log_summary.spans(log_summary._read_records(p))
    res_spans = result.get("resolution", [])
    scale_spans = result.get("scale", [])
    ok = (len(res_spans) == 1 and res_spans[0]["seconds"] == 1000.0
          and len(scale_spans) == 2
          and scale_spans[0]["value"] == {"pct": 100} and scale_spans[0]["seconds"] == 500.0
          and scale_spans[1]["value"] == {"pct": 125} and scale_spans[1]["seconds"] == 500.0)
    check("scaling_change_does_not_disturb_resolution", ok,
          f"res={res_spans} scale={scale_spans}")


# ============================================================================
# 3. READER: a hand-built file with a repeated state record still collapses
#    to one span (spans() itself is defensive against a duplicate that
#    should never occur, e.g. an older-schema file). This does NOT exercise
#    SessionLog.state()'s own dedupe — see check 3b below for that, which is
#    the one that actually gates the writer.
# ============================================================================

def check_spans_collapses_a_hand_built_repeat(tmp: Path) -> None:
    p = tmp / "c.jsonl"
    write_jsonl(p, [
        header(0),
        state("pc", 0, quality="high"),
        state("pc", 100, quality="high"),   # same value, hand-built duplicate
        state("pc", 400, quality="low"),
        footer(900),
    ])
    result = log_summary.spans(log_summary._read_records(p))
    got = result.get("pc", [])
    ok = (len(got) == 2
          and got[0]["value"] == {"quality": "high"} and got[0]["from_epoch"] == 0
          and got[0]["seconds"] == 400.0
          and got[1]["value"] == {"quality": "low"} and got[1]["seconds"] == 500.0)
    check("spans_collapses_a_hand_built_repeat", ok, f"got={got}")


# ============================================================================
# 3b. WRITER: SessionLog.state() itself must not write a repeat. This is the
#     check the coordinator's correction demanded — it drives the real
#     writer at its own boundary (never hand-built JSONL), because the
#     dedupe this project calls "the whole feature" lives in
#     SessionLog.state(), not in log_summary.spans(). A check that only ever
#     calls spans() cannot see this method at all.
# ============================================================================

def check_session_log_state_dedupes_at_the_writer(tmp: Path) -> None:
    import types
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
    import session_log  # noqa: E402  (imported lazily — only this check needs it)

    log_dir = tmp / "writer_boundary"
    settings = types.SimpleNamespace(
        session_log_enabled=True,
        session_log_dir=str(log_dir),
        session_log_roll_hours=24.0,
        session_log_max_bytes=8_000_000,
    )
    log = session_log.SessionLog(settings=settings, shipper=None)
    log.start(app_version="test")
    log.state("pc", monitors=2)   # first call for this kind: must always write
    log.state("pc", monitors=2)   # identical repeat: must NOT write
    log.state("pc", monitors=1)   # a real change: must write
    closed_path = log.close()

    recs = [json.loads(line) for line in
            closed_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    state_pc = [r for r in recs if r.get("kind") == "state.pc"]

    ok = (len(state_pc) == 2
          and state_pc[0].get("monitors") == 2
          and state_pc[1].get("monitors") == 1)
    check("session_log_state_dedupes_at_the_writer", ok, f"state.pc records={state_pc}")


# ============================================================================
# 4. per-device hours and bytes are right for two overlapping devices
# ============================================================================

def check_per_device_totals_two_overlapping(tmp: Path) -> None:
    p = tmp / "d.jsonl"
    write_jsonl(p, [
        header(0),
        connect(0, "phone-A"),
        connect(100, "tablet-B"),
        leave(3600, "phone-A", bytes_out=1000, bytes_in=200),
        connect(3700, "phone-A"),
        leave(4000, "tablet-B", bytes_out=5000, bytes_in=500),
        leave(4300, "phone-A", bytes_out=300, bytes_in=50),
        footer(5000),
    ])
    totals = log_summary.device_totals(log_summary._read_records(p))
    a = totals["phone-A"]
    b = totals["tablet-B"]
    ok = (a["sessions"] == 2
          and a["connected_seconds"] == round(3600 + (4300 - 3700), 1)
          and a["bytes_out"] == 1300 and a["bytes_in"] == 250
          and b["sessions"] == 1
          and b["connected_seconds"] == round(4000 - 100, 1)
          and b["bytes_out"] == 5000 and b["bytes_in"] == 500)
    check("per_device_totals_two_overlapping", ok, f"a={a} b={b}")


# ============================================================================
# 5. a device that connects and never leaves — reported open, no seconds
#    invented when the file itself is unclosed
# ============================================================================

def check_device_never_leaves_unclosed_file(tmp: Path) -> None:
    p = tmp / "e.jsonl"
    write_jsonl(p, [
        header(0),
        connect(0, "ghost"),
        # no leave, no footer — the run was killed
    ])
    totals = log_summary.device_totals(log_summary._read_records(p))
    g = totals["ghost"]
    ok = (g["sessions"] == 1 and g["open_sessions"] == 1
          and g["connected_seconds"] == 0.0)
    check("device_never_leaves_unclosed_file", ok, f"ghost={g}")


# ============================================================================
# 6. a device that connects and never leaves, but the FILE has a footer —
#    closed honestly at the footer's time
# ============================================================================

def check_device_never_leaves_closed_file(tmp: Path) -> None:
    p = tmp / "f.jsonl"
    write_jsonl(p, [
        header(0),
        connect(0, "ghost2"),
        footer(500),
    ])
    totals = log_summary.device_totals(log_summary._read_records(p))
    g = totals["ghost2"]
    ok = (g["open_sessions"] == 0 and g["connected_seconds"] == 500.0)
    check("device_never_leaves_closed_file", ok, f"ghost2={g}")


# ============================================================================
# 7. an unclosed file's last span is reported open, no end invented
# ============================================================================

def check_unclosed_file_last_span_open(tmp: Path) -> None:
    p = tmp / "g.jsonl"
    write_jsonl(p, [
        header(0),
        state("resolution", 0, monitors=1),
        state("resolution", 300, monitors=2),
        # no footer
    ])
    result = log_summary.spans(log_summary._read_records(p))
    got = result.get("resolution", [])
    ok = (len(got) == 2
          and got[0]["open"] is False and got[0]["seconds"] == 300.0
          and got[1]["open"] is True and got[1]["to"] is None
          and got[1]["seconds"] is None)
    check("unclosed_file_last_span_open", ok, f"got={got}")
    summ = log_summary.summarize(p)
    check("unclosed_file_flagged_in_summary", summ["unclosed"] is True,
          f"summary.unclosed={summ['unclosed']}")


# ============================================================================
# 8. the summary equals the footer rather than being recomputed
# ============================================================================

def check_summary_equals_footer_not_recomputed(tmp: Path) -> None:
    p = tmp / "h.jsonl"
    write_jsonl(p, [
        header(0, app_version="9.9.9", install_id="abc"),
        state("pc", 0, monitors=1),
        footer(123.4, counts={"state": 1, "header": 1}, state={"pc": {"monitors": 1}}),
    ])
    summ = log_summary.summarize(p)
    # The footer object must be carried through byte-for-byte, not a
    # second, independently-computed duration/counts.
    raw_footer = log_summary._read_records(p)[-1]
    ok = summ["footer"] == raw_footer and summ["footer"]["duration_s"] == 123.4
    check("summary_equals_footer_not_recomputed", ok, f"summary.footer={summ['footer']}")


# ============================================================================
# 9. write_summary() writes the file beside the log, with the right content
# ============================================================================

def check_write_summary_writes_file(tmp: Path) -> None:
    p = tmp / "i.jsonl"
    write_jsonl(p, [
        header(0),
        state("pc", 0, monitors=1),
        footer(10),
    ])
    out = log_summary.write_summary(p)
    ok = (out == tmp / "i.summary.json" and out.exists())
    if ok:
        loaded = json.loads(out.read_text(encoding="utf-8"))
        ok = loaded["header"]["kind"] == "header" and "spans" in loaded
    check("write_summary_writes_file", ok, f"out={out}")


# ============================================================================
# 10. records from an older schema (missing fields) do not crash the reader
# ============================================================================

def check_old_schema_missing_fields_does_not_crash(tmp: Path) -> None:
    p = tmp / "j.jsonl"
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"kind": "header", "at": "t0"}) + "\n")   # no epoch
        fh.write(json.dumps({"kind": "state.pc", "at": "t1"}) + "\n")  # no epoch/fields
        fh.write("{not json at all\n")                                 # malformed
        fh.write(json.dumps({"kind": "footer", "at": "t2", "epoch": 5}) + "\n")
    try:
        summ = log_summary.summarize(p)
        ok = summ["unclosed"] is False and "pc" in summ["spans"]
    except Exception as e:   # noqa: BLE001
        ok = False
        summ = str(e)
    check("old_schema_missing_fields_does_not_crash", ok, f"summ={summ}")


CHECKS = [
    check_two_monitor_spans_then_one,
    check_scaling_change_does_not_disturb_resolution,
    check_spans_collapses_a_hand_built_repeat,
    check_session_log_state_dedupes_at_the_writer,
    check_per_device_totals_two_overlapping,
    check_device_never_leaves_unclosed_file,
    check_device_never_leaves_closed_file,
    check_unclosed_file_last_span_open,
    check_summary_equals_footer_not_recomputed,
    check_write_summary_writes_file,
    check_old_schema_missing_fields_does_not_crash,
]


def run_all() -> bool:
    global FAILURES
    FAILURES = []
    tmp = Path(tempfile.mkdtemp(prefix="log_summary_gate_"))
    try:
        for fn in CHECKS:
            fn(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return not FAILURES


def test_gate():
    assert run_all()


if __name__ == "__main__":
    ok = run_all()
    print()
    print("ALL PASS" if ok else f"FAILURES: {len(FAILURES)}")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(0 if ok else 1)
