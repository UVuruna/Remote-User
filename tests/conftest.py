"""ONE TEST MAY NOT POISON THE NEXT ONE.

WHY THIS FILE EXISTS (2026-08-18, task VC-T). Running the suite whole produced
about forty failures that every one of those files passed alone, and the cause
was not forty causes — it was one line, twice:

    h264_streamer.subprocess.Popen = FakeFfmpeg     # tests/test_stream_lifecycle.py
    h264_streamer.subprocess.Popen = ScriptedFfmpeg # tests/test_quality_reset.py

`h264_streamer.subprocess` is not a copy of anything. It IS the interpreter's
one `subprocess` module, so those assignments replace `subprocess.Popen` for
the WHOLE process, permanently, and nothing ever put it back. Every later test
that shells out then got a fake ffmpeg instead of a real process:

    node  (every client-side JS gate)  -> TypeError: 'FakeFfmpeg' object does
                                          not support the context manager
                                          protocol
    playwright / adb / anything else   -> the same, or SystemExit(3) where the
                                          harness reads a missing tool out of it

The two other leaks from the same helper are smaller and just as real:
`h264_streamer.RawFrameSource` stayed a `FakeSource` (the capture-recovery
guard then hit `'FakeSource' object has no attribute 'frame_age'`),
`config_api.pairing.get_tailscale_ip` stayed a stub, and four frozen `SETTINGS`
fields kept a test's tuned values for the rest of the run.

THE FIX IS IN THE TESTS, NOT THE PRODUCT. Nothing here is a product defect:
`h264_streamer` is entitled to call `subprocess.Popen`, and a test is entitled
to fake it — what it is not entitled to do is leave it faked. So
`test_stream_lifecycle.install_fakes()` now records what it replaced and
`remove_fakes()` puts every one of them back, and this fixture guarantees the
second half runs after EVERY test, whether the test remembered or not, and
whether it passed or failed.

The fixture is deliberately blind to which test it is wrapping: a fake that
outlives its own test is a defect no matter who installed it, and a guard that
only fires for the files we already know about would have to be edited by the
next person to make the same mistake.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SERVER_DIR = TESTS_DIR.parent / "server"
for path in (str(TESTS_DIR), str(SERVER_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

# The real one, read ONCE at collection time — before any test module has had
# the chance to replace it.
REAL_POPEN = subprocess.Popen

# The gate harness's own declared port, read from its source rather than
# imported: importing it here would start pulling fastapi into every run.
DEFAULT_GATE_PORT = 8898

# THE ENVIRONMENT AS THE SUITE FOUND IT (task VC-T). `tests/test_layout_history.py`
# points `LOCALAPPDATA` at a temp directory AT IMPORT TIME so it can never write
# into the owner's real folder — correct, and it never put it back. On Windows
# that is also where PLAYWRIGHT keeps its browsers (LOCALAPPDATA/ms-playwright),
# so from that import on, every browser gate in the run died with
#
#     BrowserType.launch: Executable doesn't exist at
#     .../ru_layout_history_xxxxxxxx/ms-playwright/chromium_headless_shell-.../
#
# — six gates reporting a missing browser that is installed, because of one line
# in a seventh that has nothing to do with browsers.
REAL_ENVIRON = dict(os.environ)


@pytest.fixture(autouse=True)
def restore_process_wide_fakes():
    """After every test: put the interpreter back the way it was found.

    `subprocess.Popen` is restored unconditionally and cheaply (an identity
    check on the happy path). The module-level fakes are handed back to the
    helper that installed them, so the list of what is faked keeps ONE owner —
    the module that fakes it — instead of being copied into this file where it
    would drift the first time that helper grows a fifth fake.
    """
    snapshot = _snapshot_server_modules()
    yield
    if subprocess.Popen is not REAL_POPEN:
        subprocess.Popen = REAL_POPEN
    lifecycle = sys.modules.get("test_stream_lifecycle")
    if lifecycle is not None and hasattr(lifecycle, "remove_fakes"):
        lifecycle.remove_fakes()
    _reset_gate_harness()
    _restore_environ()
    _restore_server_modules(snapshot)


def _reset_gate_harness() -> None:
    """THE SECOND LEAK OF THE SAME SHAPE (task VC-T).

    `tests/test_input_pipeline.py` is the browser harness half a dozen gates
    share, and three of its module globals are process-wide state no gate ever
    put back:

    - `PORT` — a gate that needs its own state sets it (8895 / 8896 / 8897) and
      leaves it there, so the NEXT gate, which never asked for a private port,
      started its server on somebody else's;
    - `server_ready` — an Event that stays SET, so a later gate's
      `server_ready.wait(15)` returned instantly for a server that had not
      started;
    - `server_error` — a LIST that only grows, so one gate's bind failure was
      raised by every gate after it. That is the `SystemExit: 3` cascade: five
      gates reporting a failure that happened once, in a sixth.

    Restoring the three costs nothing and is exactly the state a fresh process
    would have had.
    """
    gate = sys.modules.get("test_input_pipeline")
    if gate is None:
        return
    if getattr(gate, "PORT", None) != DEFAULT_GATE_PORT:
        gate.PORT = DEFAULT_GATE_PORT
    if getattr(gate, "server_error", None):
        gate.server_error.clear()
    ready = getattr(gate, "server_ready", None)
    if ready is not None and ready.is_set():
        ready.clear()


def _restore_environ() -> None:
    """Put back every variable a test changed, added or deleted.

    Whole-environment and not a named list, for the same reason the fixture
    itself is blind to which test it wraps: the next variable somebody points
    at a temp directory will not be one this file already knows about.
    """
    if os.environ == REAL_ENVIRON:
        return
    # PYTEST_* belongs to the RUNNER, which sets `PYTEST_CURRENT_TEST` for the
    # duration of a test and removes it itself afterwards. Deleting it here
    # made pytest's own teardown raise KeyError on every test in the suite.
    for key in [k for k in os.environ
                if k not in REAL_ENVIRON and not k.startswith("PYTEST_")]:
        del os.environ[key]
    for key, value in REAL_ENVIRON.items():
        if os.environ.get(key) != value:
            os.environ[key] = value


def _server_modules():
    """Every module of OUR OWN that is currently imported."""
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and path.startswith(str(SERVER_DIR)):
            yield name, module


def _snapshot_server_modules() -> dict:
    """The product's module globals, as this test found them."""
    return {name: dict(vars(module)) for name, module in _server_modules()}


def _restore_server_modules(snapshot: dict) -> None:
    """THE THIRD LEAK OF THE SAME SHAPE, and the widest (task VC-T).

    The gates fake the DESK by assignment, straight onto the product's module
    globals — `window_manager.user32`, `window_manager.list_windows`,
    `desk_facts.top_level_hwnds`, `lost_windows.sweep`,
    `notice_channel._page`, `layout_popup._DESK` — and none of them ever put
    the real one back. Each is correct on its own (a gate must never touch the
    owner's real desktop); together, in one process, they are a desk assembled
    out of six different tests' fakes, and the gate that runs into it fails
    describing a defect that is not there.

    So: what a test changed in one of OUR modules is changed back, and what it
    added is removed. Whole-module and not a named list, for the same reason
    the fixture is blind to which test it wraps — the next fake will not be one
    this file already knows about. Modules imported DURING the test are left
    alone: they were not there to change.
    """
    for name, module in _server_modules():
        before = snapshot.get(name)
        if before is None:
            continue
        current = vars(module)
        for key in [k for k in current if k not in before]:
            del current[key]
        for key, value in before.items():
            if current.get(key, _MISSING) is not value:
                current[key] = value


_MISSING = object()
