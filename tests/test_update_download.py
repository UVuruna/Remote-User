"""Gate: the update download retries ITSELF, resumes, and names its failure.

HIS REPORT (2026-08-12, with the screenshot of the main window showing
"Update download failed — retry"): *"ovo mi se u zadnje vreme dešava pa treba
par puta da se klikne button"* (lang-ok: owner quote). Two defects sat behind
that one sentence, and only one of them is the network's fault:

  1. THE APP MADE HIM DO ITS RETRYING. `download()` opened one connection and
     let any exception through to the button. The installer is ~113 MB from a
     CDN; a single hiccup anywhere in it failed the whole thing.
  2. AND IT THREW AWAY EVERY BYTE. Each of his clicks re-opened the transfer
     with `open(dest, "wb")` — truncating whatever had already landed — so a
     failure at 90% cost 100 MB and the next attempt took as long as the
     first. That is why "a few clicks" was the shape of the workaround.

So: four attempts with a backoff that RESETS when an attempt actually moved
bytes (a stalled-but-alive link is not a dead host), an HTTP `Range` resume
from what is already on disk, and — for the failure that survives all four —
a sentence naming the cause instead of the generic text.

The three rules that are easy to get subtly wrong, and are checked here:
  * a server that IGNORES the Range (answers 200, not 206) is sending the
    whole file again, so the bytes on disk must be REPLACED and never counted
    twice — otherwise the progress bar reports more than the file weighs and
    the handover's size check rejects a perfectly good installer;
  * a 416 to our own resume request means the file is ALREADY COMPLETE, not
    that anything failed;
  * `total` must stay None when no Content-Length was given (task 207, the
    indeterminate bar) and must be the WHOLE size on a resume, not the
    remainder — a resumed download that reports 13 MB of 13 MB while 100 MB
    are already on disk is a bar that lies.

Run standalone or from build.py (fail-closed).

Each check is proven by planting its own defect:
  * DOWNLOAD_ATTEMPTS = 1              -> "gave up after 1 attempt"
  * open(dest, "wb") unconditionally   -> "restarted from 0, losing 40 bytes"
  * drop the 416 arm                   -> "a complete file reported a failure"
  * total = remaining                  -> "reported a total of 30, file is 100"
"""

import sys
import urllib.error
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import updates  # noqa: E402

# A real URL shape: urllib.request.Request rejects a string with no scheme
# before any of our code runs, so the fake origin must still be addressed
# the way the real one is.
URL = "https://example.invalid/VibeCoder_Setup.exe"


class FakeResponse:
    """One HTTP response: status, headers, and a body read in chunks."""

    def __init__(self, body: bytes, status: int = 200, length=True,
                 announced: int | None = None):
        # `announced` exists because the real failure mode is a response that
        # PROMISES the whole file and then stops — Content-Length says one
        # thing and the socket delivers less. A fake that always announces
        # exactly what it sends can never reproduce the bug.
        self.body = body
        self.status = status
        size = len(body) if announced is None else announced
        self.headers = {"Content-Length": str(size)} if length else {}
        self._at = 0

    def read(self, n: int) -> bytes:
        chunk = self.body[self._at:self._at + n]
        self._at += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class Server:
    """A scripted origin. `plan` is one entry per request: an exception to
    raise, or (status, body-slice-behaviour). Records every Range asked for."""

    def __init__(self, asset: bytes, plan):
        self.asset = asset
        self.plan = list(plan)
        self.ranges: list[int] = []
        self.requests = 0

    def __call__(self, request, timeout=None):
        self.requests += 1
        header = request.get_header("Range") or ""
        start = int(header.replace("bytes=", "").rstrip("-")) if header else 0
        self.ranges.append(start)
        # The LAST entry REPEATS instead of the plan falling through to
        # success. Found by planting: with a one-entry 416 plan, a fall-through
        # to "full" let the retry loop succeed on request two, so removing the
        # 416 arm from the product still passed. A real origin does not start
        # behaving differently because we asked again.
        step = self.plan.pop(0) if len(self.plan) > 1 else (
            self.plan[0] if self.plan else ("full", None))
        kind, argument = step
        if kind == "raise":
            raise argument
        if kind == "416":
            raise urllib.error.HTTPError(
                "u", 416, "Range Not Satisfiable", {}, None)
        if kind == "partial":       # honours the Range, sends `argument` bytes
            body = self.asset[start:start + argument] if argument else self.asset[start:]
            return FakeResponse(body, status=206)
        if kind == "short":         # announces the rest, delivers `argument`
            return FakeResponse(self.asset[start:start + argument], status=206,
                                announced=len(self.asset) - start)
        if kind == "ignores-range":  # answers 200 with the WHOLE asset
            return FakeResponse(self.asset, status=200)
        if kind == "no-length":
            return FakeResponse(self.asset[start:], status=206 if start else 200,
                                length=False)
        body = self.asset[start:] if start else self.asset
        return FakeResponse(body, status=206 if start else 200)


class Stage:
    """Runs the REAL updates.download with urlopen and sleep faked out."""

    def __init__(self, server: Server):
        self.server = server
        self.sleeps: list[float] = []

    def __enter__(self):
        self._saved = (updates.urllib.request.urlopen, updates.time.sleep)
        updates.urllib.request.urlopen = self.server
        updates.time.sleep = self.sleeps.append
        return self

    def __exit__(self, *_exc):
        updates.urllib.request.urlopen, updates.time.sleep = self._saved
        return False


def _tmp(name: str) -> Path:
    path = PROJECT / "tests" / f"_tmp_{name}"
    if path.exists():
        path.unlink()
    return path


def check_a_transient_failure_is_retried_without_him(problems: list[str]) -> None:
    asset = bytes(range(100)) * 2
    dest = _tmp("retry.bin")
    server = Server(asset, [("raise", urllib.error.URLError("reset")),
                            ("raise", TimeoutError("stalled")),
                            ("full", None)])
    try:
        with Stage(server):
            updates.download(URL, dest)
    except Exception as e:  # noqa: BLE001
        problems.append(f"gave up after {server.requests} attempt(s): {e!r}")
        return
    finally:
        pass
    if dest.read_bytes() != asset:
        problems.append("the file that landed is not the asset")
    dest.unlink(missing_ok=True)


def check_a_resume_keeps_the_bytes_already_on_disk(problems: list[str]) -> None:
    asset = bytes(range(100))
    dest = _tmp("resume.bin")
    # First attempt delivers 40 bytes then the link dies mid-stream; the
    # second must ask for byte 40, not byte 0.
    server = Server(asset, [("short", 40), ("partial", None)])
    seen: list[tuple[int, int | None]] = []
    try:
        with Stage(server):
            # Attempt 1 announces the full length and delivers only 40
            # bytes — the ordinary shape of a CDN dropping the connection.
            # It must be recognised as a failure (a short stream ends
            # CLEANLY), attempt 2 must ask for byte 40, and the file must
            # come out whole without him touching anything.
            updates.download(URL, dest, on_progress=lambda r, t: seen.append((r, t)))
            got = dest.read_bytes()
    except Exception as e:  # noqa: BLE001
        problems.append(f"resume run raised: {e!r}")
        return
    if server.ranges[:1] != [0]:
        problems.append(f"the first request asked for byte {server.ranges[0]}, not 0")
    resumes = [r for r in server.ranges[1:] if r]
    if not resumes:
        problems.append(
            f"restarted from 0, losing {len(asset[:40])} bytes already on disk "
            f"(ranges asked for: {server.ranges})")
    if got != asset:
        problems.append(f"the resumed file is {len(got)} bytes, asset is {len(asset)}")
    dest.unlink(missing_ok=True)


def check_a_server_that_ignores_the_range_never_double_counts(problems) -> None:
    asset = bytes(range(100))
    dest = _tmp("ignored.bin")
    dest.write_bytes(asset[:40])          # a partial from a previous attempt
    server = Server(asset, [("ignores-range", None)])
    seen: list[tuple[int, int | None]] = []
    with Stage(server):
        updates.download(URL, dest, on_progress=lambda r, t: seen.append((r, t)))
    got = dest.read_bytes()
    if got != asset:
        problems.append(
            f"a 200 answer left {len(got)} bytes on disk, asset is {len(asset)} "
            f"— the old partial was appended to instead of replaced")
    if seen and seen[-1][0] > len(asset):
        problems.append(
            f"progress reported {seen[-1][0]} of {len(asset)} — the bytes on "
            f"disk were counted twice")
    dest.unlink(missing_ok=True)


def check_an_already_complete_file_is_not_a_failure(problems: list[str]) -> None:
    asset = bytes(range(100))
    dest = _tmp("complete.bin")
    dest.write_bytes(asset)
    server = Server(asset, [("416", None)])
    seen: list[tuple[int, int | None]] = []
    try:
        with Stage(server):
            updates.download(URL, dest, on_progress=lambda r, t: seen.append((r, t)))
    except Exception as e:  # noqa: BLE001
        problems.append(f"a complete file reported a failure: {e!r}")
        dest.unlink(missing_ok=True)
        return
    if seen[-1] != (len(asset), len(asset)):
        problems.append(f"a complete file reported progress {seen[-1]}")
    dest.unlink(missing_ok=True)


def check_the_total_is_the_whole_size_and_none_stays_none(problems) -> None:
    asset = bytes(range(100))
    # A resume must report the WHOLE size, not the remainder.
    dest = _tmp("total.bin")
    dest.write_bytes(asset[:70])
    server = Server(asset, [("partial", None)])
    seen: list[tuple[int, int | None]] = []
    with Stage(server):
        updates.download(URL, dest, on_progress=lambda r, t: seen.append((r, t)))
    totals = {t for _, t in seen}
    if totals != {len(asset)}:
        problems.append(
            f"reported a total of {sorted(totals)}, file is {len(asset)} — a "
            f"resumed bar that quotes the remainder lies about the size")
    dest.unlink(missing_ok=True)

    # And no Content-Length must still mean None, never a guess (task 207).
    dest = _tmp("nolen.bin")
    server = Server(asset, [("no-length", None)])
    seen = []
    with Stage(server):
        updates.download(URL, dest, on_progress=lambda r, t: seen.append((r, t)))
    if {t for _, t in seen} != {None}:
        problems.append("a response with no Content-Length was given a total anyway")
    dest.unlink(missing_ok=True)


def check_the_failure_that_survives_is_named(problems: list[str]) -> None:
    """The button is the retry, so the sentence must end in one."""
    cases = [
        (urllib.error.HTTPError(URL, 503, "busy", {}, None), "503"),
        (urllib.error.URLError("no route"), "connection"),
        (TimeoutError("slow"), "timed out"),
        (OSError("disk full"), "disk"),
    ]
    for error, expected in cases:
        text = updates.failure_reason(error)
        if expected.lower() not in text.lower():
            problems.append(
                f"{type(error).__name__} is named {text!r} — it says nothing "
                f"about {expected!r}")
        if "retry" not in text.lower():
            problems.append(f"{text!r} names no next step")
    generic = updates.failure_reason(ValueError("something odd"))
    if not generic:
        problems.append("an unknown failure produced no message at all")


def main() -> int:
    print("=== UPDATE DOWNLOAD GATE ===")
    checks = [
        ("a transient failure is retried without him",
         check_a_transient_failure_is_retried_without_him),
        ("a resume keeps the bytes already on disk",
         check_a_resume_keeps_the_bytes_already_on_disk),
        ("a server that ignores the Range never double-counts",
         check_a_server_that_ignores_the_range_never_double_counts),
        ("an already complete file is not a failure",
         check_an_already_complete_file_is_not_a_failure),
        ("the total is the whole size, and None stays None",
         check_the_total_is_the_whole_size_and_none_stays_none),
        ("the failure that survives four attempts is named",
         check_the_failure_that_survives_is_named),
    ]
    failed = 0
    for name, fn in checks:
        problems: list[str] = []
        try:
            fn(problems)
        except Exception as e:  # noqa: BLE001 — a crashing check is a failing one
            problems.append(f"{type(e).__name__}: {e}")
        print(f"  {'PASS' if not problems else 'FAIL'}  {name}")
        for problem in problems:
            print(f"        {problem}")
        failed += bool(problems)
    print()
    if failed:
        print(f"UPDATE DOWNLOAD GATE FAILED — {failed} check(s). A download "
              f"that makes the owner click four times is a download that "
              f"refused to try four times.")
        return 1
    print("UPDATE DOWNLOAD GATE PASSED — it retries itself, resumes what it "
          "has, and says why when it truly cannot.")
    return 0


def test_update_download():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
