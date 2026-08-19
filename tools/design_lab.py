"""THE DESIGN LAB — a local page where every look of every control is on
screen at once, every value behind them is a knob, and Save writes the knob
back into the source file it came from.

    python tools/design_lab.py               serve on 8781 and open the browser
    python tools/design_lab.py --no-browser  serve only (what the tooth drives)
    python tools/design_lab.py --print       the tunables and their values, no browser

WHY IT EXISTS. Eight renderings of every control (dark/light x plain/coloured
x outlined/filled) are settled today by rendering a ballot, looking at it, and
editing a CSS file by hand — which is how a number ends up tuned against the
one look that happened to be open. This page shows all eight beside each other
over a backdrop you choose, because a control floats over the PC's own screen
and that screen can be any colour.

WHAT YOU SEE IS THE PRODUCT. The specimens are drawn in an iframe that loads
the REAL client/theme.css, client/style.css and client/theme.js — the same
cascade, the same per-set ink arithmetic, the same shadow rule. This tool owns
no copy of a colour and no copy of a rule; if it looks right here it is right
there, and if the product changes tomorrow this page changes with it.

THE PC ONLY. This is a workshop tool, never part of the phone product and
never shipped: nothing under client/, server/ or android/ imports it, the
installer does not carry it, and it serves on the loopback address alone.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_tokens as tokens  # noqa: E402


# ═══════════════════════════ CONFIG ═══════════════════════════
PROJECT = tokens.PROJECT
HOST = "127.0.0.1"
PORT = 8781

# The only folders a request can reach. A design tool has no business reading
# server code, the owner's UV/ inbox or anything else on the disk, and an
# allowlist says which two it does have business with rather than trusting a
# path check to catch every way of spelling "..".
SERVE_DIRS = ("tools", "client")

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


# ═══════════════════════════ SAVING ═══════════════════════════
def apply_save(payload: dict) -> dict:
    """One save, in the order the sources are least surprising to read back:
    colour, shape, palette, and the two JS alphas last so a half-written pair
    can never outlive the CSS it belongs to.

    A refusal from the registry stops the whole save and is reported as it
    was raised — a partial save that says "ok" is the one outcome a tool like
    this must never have."""
    changed: list = []
    touched: dict = {}

    for source_id in ("dark", "light", "shape", "sets"):
        values = payload.get(source_id) or {}
        if values:
            touched[source_id] = values
            changed += tokens.write_source(source_id, values)

    # A shadow's STRENGTH lives in three places at once — the token on each
    # theme and the constant client/theme.js computes the coloured looks with.
    # One knob, three writes, in one save.
    for token, alpha in (payload.get("alphas") or {}).items():
        const = tokens.JS_ALPHAS.get(token)
        for theme in ("dark", "light"):
            current = tokens.read_source(theme).get(token)
            if current is None:
                continue
            changed += tokens.write_source(
                theme, {token: tokens.with_alpha(current, float(alpha))})
        touched.setdefault("dark", {})[token] = alpha
        if const:
            changed += tokens.write_js_alpha(const, float(alpha))

    return {"ok": True, "changed": changed, "pins": tokens.pins_touched(touched)}


# ═══════════════════════════ THE SERVER ═══════════════════════════
class Handler(BaseHTTPRequestHandler):
    server_version = "VibeCoderDesignLab"

    def log_message(self, fmt, *args):
        pass  # a tuning session should not narrate every slider drag

    # --- plumbing ---
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Never cached: the whole point is that an edit to client/style.css
        # shows up on the next reload, including one made by this tool itself.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data).encode("utf-8"), TYPES[".json"])

    def _file(self, relative: str) -> None:
        path = (PROJECT / relative).resolve()
        inside = any(path.is_relative_to((PROJECT / d).resolve()) for d in SERVE_DIRS)
        if not inside or not path.is_file():
            self._send(404, b"not here", "text/plain; charset=utf-8")
            return
        self._send(200, path.read_bytes(),
                   TYPES.get(path.suffix.lower(), "application/octet-stream"))

    # --- routes ---
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/":
            self._file("tools/design_lab.html")
        elif route == "/preview":
            self._file("tools/preview.html")
        elif route == "/tokens":
            self._json(200, tokens.snapshot())
        else:
            self._file(route.lstrip("/"))

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/save":
            self._send(404, b"not here", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, apply_save(payload))
        except Exception as error:                      # noqa: BLE001
            # The message is the registry's own sentence — it names the token
            # it refused and why, which is the only useful thing to say here.
            self._json(400, {"ok": False, "error": str(error)})


# ═══════════════════════════ ENTRY ═══════════════════════════
def print_tokens() -> None:
    snapshot = tokens.snapshot()
    for group in snapshot["groups"]:
        print("\n== " + group["title"] + " ==")
        for row in group["rows"]:
            if row["kind"] == "sets":
                for name, value in snapshot["values"]["sets"].items():
                    print("   %-16s %s" % (name, value))
                continue
            token = row["token"]
            if row["kind"] == "shape":
                value = snapshot["values"]["shape"].get(token, "?")
            elif row["kind"] == "derived":
                value = "(computed)"
            else:
                value = "%s | %s" % (snapshot["values"]["dark"].get(token, "-"),
                                     snapshot["values"]["light"].get(token, "-"))
            pin = "   << " + snapshot["pinned"][token] if token in snapshot["pinned"] else ""
            print("   %-22s %-34s %s%s" % (token, value, row.get("label", ""), pin))


def main() -> int:
    if "--print" in sys.argv:
        print_tokens()
        return 0
    url = "http://%s:%d/" % (HOST, PORT)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Design lab: " + url + "   (ctrl-c to stop)", flush=True)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
