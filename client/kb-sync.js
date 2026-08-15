// Keyboard mirror — how one invisible-field edit turns into PC key
// injections, and whether the field's own caret can still be trusted.
//
// Split out of controls.js's `input` handler (2026-08-13), pure like
// voice.js and grid-icons.js before it, so this gate can run it whole.
//
// HIS REPORT (2026-08-13), after the mic hypothesis was tested live and
// explicitly ruled out — his own words (lang-ok: owner quote), translated:
// "dictating with the mic first changes nothing at all — this only happens
// while I am typing on the keyboard". Typing, MOST on delete. The PC's
// visible caret sits at the FAR RIGHT, yet what he types lands INSERTED
// BEFORE a trailing fragment ("ok") that no amount of typing or deleting
// gets rid of. Only a mouse click outside the field and back frees it.
//
// THE MECHANISM. `kbDiff` below assumes — its own pre-2026-08-13 comment said
// so outright — that the PC caret sits at the END of the mirrored text. That
// is only true while the PHONE's own caret is ALSO at the end of `kbInput`.
// An Android IME can leave it somewhere else without any tap of his (a
// predictive-completion span still "claiming" a trailing word, an autocorrect
// replace that repositions the caret before the word it just fixed) — the
// field is invisible, so he has no way to see this happen. Once the caret
// sits before a trailing fragment, EVERY edit he makes shares a non-empty
// common SUFFIX with what came before (that fragment, unchanged), so the
// mid-string branch fires on every single keystroke: erase the tail off the
// PC, retype it. The mirroring stays internally consistent — but the
// fragment itself was never his edit, so nothing he types or deletes ever
// touches it, and it keeps reappearing on the PC after every character,
// exactly "inserted before a fragment that will not go away". A blur clears
// both `value` and the mirror outright (controls.js), which is exactly his
// working fix (click away, click back) and is the tell.
//
// THE FIX: the field's caret is RE-PINNED to its own end after every edit
// that was not mid-composition (`kbShouldRepin`) — controls.js calls
// `setSelectionRange` accordingly. That cannot rewrite what the IME already
// did to land THIS edit, but it guarantees every edit AFTER this one starts
// from the end again, so the drift cannot compound — a single stray fragment
// is recoverable by one ordinary backspace instead of being permanent until
// a blur. Never a policy of refusing the mid-string dance itself: that dance
// is also what makes autocorrect and double-space-period work at all
// (controls.js's original comment on `kbDiff`), and disabling it outright
// would silently drop those live edits rather than mis-place a rare one.

/** The existing diff arithmetic, unchanged in behaviour: how many trailing
 *  PC characters to erase and what to retype, turning `prevValue` into
 *  `value`. Mid-string edits (removed AND/OR inserted with a shared,
 *  unchanged suffix) erase-and-retype the tail because the PC caret is
 *  assumed to sit at the end of the mirrored text — see the module header
 *  for when that assumption is not actually true. */
function kbDiff(prevValue, value) {
  const minLen = Math.min(prevValue.length, value.length);
  let p = 0;
  while (p < minLen && prevValue[p] === value[p]) p++;
  let s = 0;
  while (s < minLen - p && prevValue[prevValue.length - 1 - s] === value[value.length - 1 - s]) s++;
  const removed = prevValue.length - p - s;
  let inserted = value.slice(p, value.length - s);
  let back = removed;
  if (s > 0 && (removed > 0 || inserted)) {
    back += s;
    inserted += value.slice(value.length - s);
  }
  return { back, inserted };
}

/** True when the field's own caret sits exactly at its own end (a collapsed
 *  selection at `value.length`) — the one state the mid-string dance in
 *  `kbDiff` is honestly allowed to assume. `selectionStart`/`selectionEnd`
 *  are the live DOM properties, read right after the edit landed. */
function kbCaretAtEnd(value, selectionStart, selectionEnd) {
  return selectionStart === value.length && selectionEnd === value.length;
}

// ── GHOST-SUFFIX DIAGNOSTIC (owner report 2026-08-14 — mobile data, high
// latency, and the bug he hit 2026-08-13 came back; unreproducible today). No
// behaviour change here: the re-pin above is the fix and stays as it was.
// This is purely a cheap SIGNAL controls.js can act on — "this edit looks
// like the ghost pattern" — so a `client_log` can reach the server log the
// next time it happens, without waiting for a session he can sit through
// himself.
//
// Two independent tells, either one enough:
//   1. `back > 0 && inserted.length > 1` — the mid-string erase-and-retype
//      branch fired AND retyped more than one character. An ordinary
//      keystroke is a 0-or-1-character edit; a multi-character mid-string
//      retype is what a stray trailing fragment produces once it starts
//      sharing a suffix with every later edit (the module header's
//      mechanism).
//   2. `inserted` ends with a real (≥2 character) run that matches the TAIL
//      of `prevValue` — the fragment reappearing verbatim, unearned by
//      anything he actually typed. One matching character is not a signal
//      (ordinary text ends in spaces and common letters constantly); two or
//      more sharing a common suffix with what was already sent is the
//      ghost's own signature.
function kbGhostSuffixLen(prevValue, inserted) {
  const max = Math.min(prevValue.length, inserted.length);
  let n = 0;
  while (n < max
    && prevValue[prevValue.length - 1 - n] === inserted[inserted.length - 1 - n]) {
    n++;
  }
  return n;
}

/** True when this edit LOOKS like the 2026-08-13 ghost-suffix pattern — a
 *  candidate worth logging, never a certainty. Takes the diff `kbDiff`
 *  already computed rather than recomputing it, so the caller pays for the
 *  arithmetic exactly once. */
function kbGhostCandidate(prevValue, diff) {
  const { back, inserted } = diff;
  if (back > 0 && inserted.length > 1) return true;
  return !!inserted && kbGhostSuffixLen(prevValue, inserted) >= 2;
}

/** Whether controls.js should re-pin the caret to the end after this edit.
 *  Never mid-composition (`isComposing`): forcing a selection while a real
 *  multi-keystroke composition (CJK, emoji picker) is in flight can break
 *  the composing span itself, and it is not what caused his report — GBoard's
 *  own autocorrect-completion drift never sets `isComposing` true. Already
 *  at the end is a no-op either way; the guard exists so a caller can skip
 *  the DOM call entirely on the ordinary path. */
function kbShouldRepin(value, selectionStart, selectionEnd, isComposing) {
  if (isComposing) return false;
  return !kbCaretAtEnd(value, selectionStart, selectionEnd);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    kbDiff, kbCaretAtEnd, kbShouldRepin,
    kbGhostSuffixLen, kbGhostCandidate,
  };
}
