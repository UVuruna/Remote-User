"""Language Gate: both language lists are LANGUAGE FIRST, and grouping never
costs him a choice.

Owner report 2026-08-13: *"Sto se tice jezika i za VOICE koji prica i za MIC
kome pricamo ne treba kao sada da bude nagomilano 100 njih u ogromnoj listi vec
po jezicimo ... npr Engleski pa kad otvorimo ponudi se Voice 1,2,3... koji
mozemo da poslusamo"*, and of the dictation list: *"sto se tice MIC tu isto se
ponavljaju bez potrebe pa imamo vise puta iste odabire"*.

WHAT THIS GATE EXISTS TO PREVENT, and it is not "the list looks tidy".

The first plan for the MIC half was a DEDUPE BY LANGUAGE, and his own answer
overruled it: *"da ali sa podgrupama jer korisnik treba da bira da li ce output
da ide cirilica ili latinica isto kao sto engleski ima vise odabira"*. A merge
would have made the card look exactly as he asked while quietly removing the
choice of script his dictated text comes out in. So the rule this gate holds is
two-sided: one row per language, AND every real variant still reachable. A
check that only counted rows would pass the very defect the round rejected.

The voice half carries the same double edge, and running the module before
wiring it caught both halves of it live:

  * Voices were first keyed by LOCALE, like dictation rows. Several voices
    share one locale, so his American "male 1" was silently dropped and the
    card looked tidier while offering less. A voice is its NAME.
  * An engine name with no "#" ("sr-rs-x-sfg") has no variant at all, and it
    sailed through the readability test as the words "sr rs x sfg" — precisely
    the "glupi karakteri" case his ruling forbids, because it happens to be
    letters and digits.

His ruling on naming, in his two cases: keep the variant when it reads like
"female 1" / "male 1"; fall back to "Voice 1, 2, 3" when it is nonsense.

WHY THE RULES LIVE ON THE PAGE. This repo has no JVM test runner
(tests/test_voice_dedup.py's own header records what that cost once: a Kotlin
-only fix shipped half-done). So the grouping is in `client/lang-groups.js`,
pure — no DOM, no socket, no state — and this gate runs it WHOLE in node, one
fresh interpreter per scenario. Kotlin is deliberately UNCHANGED by this round:
nothing is deleted on the phone, so nothing had to be.

Requires: node on PATH — a HARD requirement, this gate being registered in
build.py (test_voice_dedup.py's node-is-mandatory precedent). Never skip it
silently.
"""
# lang-ok: the owner's own words, quoted as evidence of what was asked

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "lang-groups.js"
NOTIFY = PROJECT / "client" / "notify.js"
DICT_CARD = PROJECT / "client" / "dictation-card.js"
INDEX = PROJECT / "client" / "index.html"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/lang-groups.js rules) — install Node.js.")
    return node


def _module() -> str:
    text = MODULE.read_text(encoding="utf-8")
    for needed in ("function langParts", "function langKey",
                   "function langScript", "function langVariantKey",
                   "function langVariantLabel", "function groupByLanguage",
                   "function voiceVariant", "function voiceVariantReadable",
                   "function voiceGroupLabels",
                   "function groupVoicesByLanguage"):
        if needed not in text:
            fail(f"{needed!r} left client/lang-groups.js — the gate cannot "
                 "find what it must test")
    return text


def _run(body: str) -> dict:
    """Runs the WHOLE module plus `body` (which prints one JSON line) in a
    fresh node process."""
    script = f"{_module()}\n{body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.js"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                             text=True, timeout=30)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


# --- MIC: one row per language, every real variant still reachable ---------

def check_two_spellings_of_one_locale_become_one_row() -> None:
    """His "vise puta iste odabire": Android hands the same locale to us more
    than once — `LocaleList.getAdjustedDefault()` says "sr-RS" while an IME
    subtype says "sr_RS". That is ONE choice written twice."""
    out = _run("""
const groups = groupByLanguage(
  [{tag:"sr-RS"}, {tag:"sr_RS"}, {tag:"sr-RS"}], (r) => r.tag, () => "");
console.log(JSON.stringify({
  groups: groups.length,
  variants: groups.map((g) => g.variants.map((v) => v.tag)),
}));
""")
    if out["groups"] != 1:
        fail(f"three spellings of one Serbian made {out['groups']} groups — "
             "the pile he reported")
    if out["variants"][0] != ["sr-RS"]:
        fail("the same locale written twice must collapse to ONE variant, and "
             f"keep the FIRST spelling seen; got {out['variants'][0]}")


def check_the_two_scripts_stay_two_choices() -> None:
    """THE HALF A ROW-COUNTING CHECK WOULD MISS. His ruling: the script is a
    real choice, because it decides what his dictated text comes out AS. So
    sr-RS (Cyrillic by resolution) and sr-Latn-RS are one GROUP and two
    VARIANTS — never one variant."""
    out = _run("""
const groups = groupByLanguage(
  [{tag:"sr-RS"}, {tag:"sr-Latn-RS"}, {tag:"sr_RS"}],
  (r) => r.tag, () => "");
console.log(JSON.stringify({
  groups: groups.length,
  tags: groups[0] ? groups[0].variants.map((v) => v.tag) : [],
  labels: groups[0] ? groups[0].variants.map((v) => v.label) : [],
}));
""")
    if out["groups"] != 1:
        fail("Serbian must be ONE row on the card")
    if len(out["tags"]) != 2:
        fail("the two SCRIPTS are two real choices (owner 2026-08-13) — "
             f"grouping collapsed them to {out['tags']}, which is the merge "
             "he overruled")
    if not any("Latin" in (l or "") for l in out["labels"]):
        fail("a script that distinguishes two variants must be NAMED on the "
             f"row; labels were {out['labels']}")
    if not any("Cyril" in (l or "") for l in out["labels"]):
        fail("the bare tag 'sr-RS' must RESOLVE to Cyrillic and say so — "
             f"labels were {out['labels']}. Without resolution it looks as "
             "different from sr-Cyrl as from sr-Latn, which is the original "
             f"duplicate.")


def check_regions_of_one_language_stay_two_choices() -> None:
    """His own comparison: *"isto kao sto engleski ima vise odabira"*."""
    out = _run("""
const groups = groupByLanguage(
  [{tag:"en-US"}, {tag:"en-GB"}], (r) => r.tag, () => "");
console.log(JSON.stringify({
  groups: groups.length,
  labels: groups[0].variants.map((v) => v.label),
}));
""")
    if out["groups"] != 1 or len(out["labels"]) != 2:
        fail("English must be one row holding both regions; got "
             f"{out['groups']} group(s), labels {out['labels']}")
    if not all(out["labels"]):
        fail("two variants of one language must each be NAMED — an empty "
             f"label is an unlabelled choice; got {out['labels']}")


def check_a_lone_variant_is_not_labelled() -> None:
    """A group of one has nothing to distinguish. Labelling it "Germany"
    beside a heading already saying German is noise, and this is the axis a
    per-row (rather than per-group) label rule would get wrong."""
    out = _run("""
const g = groupByLanguage([{tag:"de-DE"}], (r) => r.tag, () => "")[0];
console.log(JSON.stringify({ label: g.variants[0].label }));
""")
    if out["label"]:
        fail("a language with ONE variant needs no distinguishing word; got "
             f"{out['label']!r}")


def check_every_heading_is_english_whatever_the_platform_supplied() -> None:
    """The owner's decision of 2026-08-13, and it is the fix for a defect no
    ASSERTION found — an independent grader OPENED the two screenshots and read
    the same language spelled two ways two screens apart.

    The two cards have different name sources: Android hands the dictation card
    an endonym (`Locale.getDisplayName`), the voice card gets none and must look
    one up. Two sources cannot agree by accident, so there is one source now and
    it answers in English. The check therefore SUPPLIES an endonym and demands it
    be ignored — a heading that merely happens to read "Serbian" because nothing
    was supplied would prove nothing.

    Both group sizes are asserted deliberately: the shipped code took the
    platform's wording for a group of ONE and looked the name up only for a group
    of several, which on his phone means the exception was the common case. A
    rule that holds for the rare shape only is what let the divergence ship."""
    out = _run("""
const lone = groupByLanguage(
  [{tag:"sr-Latn-RS", nm:"Srpski (Srbija)"}],
  (r) => r.tag, (r) => r.nm);
const many = groupByLanguage(
  [{tag:"sr-RS", nm:"Srpski (Srbija)"}, {tag:"sr-Latn-RS", nm:"Srpski"}],
  (r) => r.tag, (r) => r.nm);
const en = groupByLanguage(
  [{tag:"is-IS", nm:""}], (r) => r.tag, (r) => r.nm);
console.log(JSON.stringify({
  lone: lone[0].name, many: many[0].name, is: en[0].name,
  labels: many[0].variants.map((v) => v.label),
}));
""")
    for where, name in (("a group of ONE", out["lone"]),
                        ("a group of SEVERAL", out["many"])):
        if name != "Serbian":
            fail(f"{where} must be headed by the ENGLISH language name "
                 f"(owner 2026-08-13); got {name!r}. A supplied endonym was "
                 "offered on purpose — preferring it is exactly how one card "
                 "came to write Serbian in Latin and the other in Cyrillic")
    if out["is"] != "Icelandic":
        fail("a language the platform supplied NO name for must still be "
             f"headed in English; got {out['is']!r}")
    if not any("Latin" in (l or "") for l in out["labels"]):
        fail("the heading going English must NOT reach the rows INSIDE a "
             "group: those decide what his dictated text comes out AS, and "
             f"the script must still be named; labels were {out['labels']}")


def check_the_tag_handed_back_is_never_rewritten() -> None:
    """A canonical key decides SAMENESS and must never reach the recognizer:
    `Android.voiceSetLang` is given the exact string the platform offered."""
    out = _run("""
const g = groupByLanguage([{tag:"sr-Latn-RS"}], (r) => r.tag, () => "")[0];
console.log(JSON.stringify({ tag: g.variants[0].tag }));
""")
    if out["tag"] != "sr-Latn-RS":
        fail("the tag must be handed back EXACTLY as the platform gave it — "
             f"got {out['tag']!r}; a spelling we invented may simply not be "
             "accepted by the recognizer")


# --- VOICE: naming, and never losing a voice ------------------------------

def check_several_voices_of_one_locale_all_survive() -> None:
    """The defect running the module caught before it shipped: keyed by
    locale, "male 1" vanished and the card looked tidier while offering
    less."""
    out = _run("""
const groups = groupVoicesByLanguage([
  {name:"en-us-x-tpf#female_1", locale:"en-US"},
  {name:"en-us-x-tpd#male_1",   locale:"en-US"},
  {name:"en-us-x-tpc#male_2",   locale:"en-US"},
]);
console.log(JSON.stringify({
  groups: groups.length,
  labels: groups[0] ? groups[0].variants.map((v) => v.label) : [],
}));
""")
    if out["groups"] != 1:
        fail("three American voices are one language row")
    if len(out["labels"]) != 3:
        fail("EVERY voice must survive grouping — a voice is its NAME, not "
             f"its locale; got {out['labels']}. Keying a voice by locale is "
             "how his 'male 1' disappeared.")


def check_one_speaker_shipped_twice_is_one_row() -> None:
    """His report of 2026-08-13: sixteen English rows, and he asked outright
    whether they are all different. Half of them were not — Android engines
    ship most speakers as a `-local` and a `-network` copy of one voice, two
    `Voice` objects with two distinct names, so nothing treated them as one.
    Playing both is comparing a voice with itself."""
    out = _run("""
const groups = groupVoicesByLanguage([
  {name:"en-us-x-tpf-local",   locale:"en-US"},
  {name:"en-us-x-tpf-network", locale:"en-US"},
  {name:"en-us-x-tpd-local",   locale:"en-US"},
  {name:"en-us-x-tpd-network", locale:"en-US"},
]);
console.log(JSON.stringify({
  names: groups[0] ? groups[0].variants.map((v) => v.row.name) : [],
}));
""")
    names = out["names"]
    if len(names) != 2:
        fail("two speakers shipped local+network are TWO rows, not "
             f"{len(names)} — got {names}")
    if any("network" in n for n in names):
        fail("the ON-DEVICE copy must be the one kept: a network voice needs "
             "a connection at the moment a notice arrives, which is exactly "
             f"when he is away from Wi-Fi. Got {names}")


def check_a_network_only_voice_is_still_offered() -> None:
    """Deduping must never cost him a voice. A speaker with no on-device copy
    is still the only way to hear that speaker — dropping it because it is
    not local would remove a choice rather than a repetition, which is the
    exact failure his script ruling of 2026-08-13 forbids."""
    out = _run("""
const groups = groupVoicesByLanguage([
  {name:"en-gb-x-gba-network", locale:"en-GB"},
]);
console.log(JSON.stringify({
  names: groups[0] ? groups[0].variants.map((v) => v.row.name) : [],
}));
""")
    if out["names"] != ["en-gb-x-gba-network"]:
        fail("a speaker that exists ONLY in the cloud must still be offered; "
             f"got {out['names']}")


def check_dedupe_does_not_reshuffle_the_numbering() -> None:
    """The kept copy takes the place the FIRST copy already held. Otherwise
    the "Voice 1, 2, 3" numbering would depend on which copy the engine
    happened to list first, and the row he chose yesterday would wear a
    different number today."""
    out = _run("""
const kept = dedupeVoices([
  {name:"en-us-x-aaa-network"},
  {name:"en-us-x-bbb-local"},
  {name:"en-us-x-aaa-local"},
]);
console.log(JSON.stringify({names: kept.map((v) => v.name)}));
""")
    if out["names"] != ["en-us-x-aaa-local", "en-us-x-bbb-local"]:
        fail("the on-device copy must replace its network twin IN PLACE — "
             f"order is the engine's, not the dedupe's; got {out['names']}")


def check_readable_variants_are_kept() -> None:
    """His ruling: *"ako je to female 1 male 1 i tako dalje onda ok"*."""
    out = _run("""
const g = groupVoicesByLanguage([
  {name:"sr-rs-x-sfg#female_1", locale:"sr-RS"},
  {name:"sr-rs-x-sfg#male_1",   locale:"sr-RS"},
])[0];
console.log(JSON.stringify({ labels: g.variants.map((v) => v.label) }));
""")
    if out["labels"] != ["female 1", "male 1"]:
        fail("a variant that reads like a word is KEPT as his ruling says; "
             f"got {out['labels']}")


def check_nonsense_numbers_the_whole_group() -> None:
    """*"ako su neki glupi karakteri onda ne onda cemo voice 1..."* — and the
    GROUP is the unit: half a group named and half numbered would not even be
    a sequence he can read. Includes the no-"#" name that caught this gate's
    own author out: it is letters and digits, so a naive readability test
    passes it."""
    out = _run("""
const plain = groupVoicesByLanguage([
  {name:"sr-rs-x-sfg",    locale:"sr-RS"},
  {name:"sr-rs-x-a1b2c3", locale:"sr-RS"},
])[0];
const mixed = groupVoicesByLanguage([
  {name:"de-de-x-nfh#female_1", locale:"de-DE"},
  {name:"de-de-x-nfh#7f3a2b1c",  locale:"de-DE"},
])[0];
console.log(JSON.stringify({
  plain: plain.variants.map((v) => v.label),
  mixed: mixed.variants.map((v) => v.label),
  variantOfNameWithoutHash: voiceVariant("sr-rs-x-sfg"),
}));
""")
    if out["variantOfNameWithoutHash"] != "":
        fail("an engine name with NO '#' carries no variant at all — it is a "
             "locale and a private-use id, nothing about the speaker; got "
             f"{out['variantOfNameWithoutHash']!r}, which would be shown to "
             "him as a name")
    if out["plain"] != ["Voice 1", "Voice 2"]:
        fail("nonsense names must become the numbering he asked for; got "
             f"{out['plain']}")
    if out["mixed"] != ["Voice 1", "Voice 2"]:
        fail("ONE unreadable variant numbers the WHOLE group — a group half "
             "named and half numbered has no readable sequence; got "
             f"{out['mixed']}")


def check_a_bare_number_is_not_a_name() -> None:
    """"3" as a row reads as a broken card; "Voice 3" is what he asked for."""
    out = _run("""
console.log(JSON.stringify({
  bare: voiceVariantReadable("3"),
  word: voiceVariantReadable("female 1"),
  junk: voiceVariantReadable("x-sfg"),
}));
""")
    if out["bare"]:
        fail("a bare number is not a name he can choose by")
    if not out["word"]:
        fail("'female 1' is exactly the case his ruling keeps")
    if out["junk"]:
        fail("'x-sfg' is the nonsense case and must not pass as a name")


def check_region_named_only_when_the_group_spans_regions() -> None:
    """Inside one language "female 1" and "female 1 (United Kingdom)" is the
    distinction he needs; "(United States)" on every row of an American-only
    group is noise."""
    out = _run("""
const spans = groupVoicesByLanguage([
  {name:"en-us-x-tpf#female_1", locale:"en-US"},
  {name:"en-gb-x-gba#female_1", locale:"en-GB"},
])[0];
const one = groupVoicesByLanguage([
  {name:"en-us-x-tpf#female_1", locale:"en-US"},
  {name:"en-us-x-tpd#male_1",   locale:"en-US"},
])[0];
console.log(JSON.stringify({
  spans: spans.variants.map((v) => v.label),
  one: one.variants.map((v) => v.label),
}));
""")
    if not all("(" in l for l in out["spans"]):
        fail("two regions in one language must be told apart — otherwise two "
             f"rows read 'female 1' and 'female 1'; got {out['spans']}")
    if any("(" in l for l in out["one"]):
        fail("a single-region group must not repeat its region on every row; "
             f"got {out['one']}")


# --- The cards really USE it ----------------------------------------------

def check_both_cards_drive_the_module() -> None:
    """A pure module nobody calls is a feature that does not exist — the
    actions.json lesson of 2026-08-07, and the grid-icons one. BOTH lists must
    be grouped, since he reported both."""
    notify = NOTIFY.read_text(encoding="utf-8")
    card = DICT_CARD.read_text(encoding="utf-8")
    if "groupVoicesByLanguage(" not in notify:
        fail("Settings → Voice (client/notify.js) does not call "
             "groupVoicesByLanguage — his VOICE half is unfixed")
    if "groupByLanguage(" not in card:
        fail("the dictation card does not call groupByLanguage — his MIC half "
             "is unfixed")
    for name, text, where in (("notify.js", notify, "voiceOpenLang"),
                              ("dictation-card.js", card, "dictOpenLang")):
        if where not in text:
            fail(f"{name} has no {where} — without a remembered open group "
                 "there is no drill-down, only a flatter flat list")
        if "langBackRow(" not in text:
            fail(f"{name} opens a language with no way BACK out of it")


def check_a_lone_variant_is_not_hidden_behind_a_door() -> None:
    """A drill-down into a list of one shows him nothing he could not already
    see, and it would put his only Serbian behind a tap."""
    for path in (NOTIFY, DICT_CARD):
        text = path.read_text(encoding="utf-8")
        if "variants.length === 1" not in text:
            fail(f"{path.name} does not special-case a language with ONE "
                 "variant — a door into a list of one is a tap that shows "
                 "nothing")


def check_the_module_is_pure_and_loaded_before_its_readers() -> None:
    """This gate can only run the module whole while it stays pure, and the
    page can only use it if it is loaded first (classic scripts, no modules)."""
    text = MODULE.read_text(encoding="utf-8")
    for forbidden in ("document.", "window.Android", "addEventListener",
                      "getElementById", "localStorage"):
        if forbidden in text:
            fail(f"client/lang-groups.js touches {forbidden!r} — it must stay "
                 "pure so this gate can run it whole (the grid-icons.js / "
                 "voice.js pattern)")
    html = INDEX.read_text(encoding="utf-8")
    order = [m for m in re.findall(r'/static/([A-Za-z0-9_.-]+\.js)', html)]
    for reader in ("panels.js", "dictation-card.js", "notify.js"):
        if reader not in order:
            fail(f"{reader} is not loaded by client/index.html")
    if "lang-groups.js" not in order:
        fail("client/lang-groups.js is never loaded by the page — a module the "
             "page does not load is a feature that does not exist")
    first = order.index("lang-groups.js")
    for reader in ("dictation-card.js", "notify.js"):
        if order.index(reader) < first:
            fail(f"{reader} loads BEFORE lang-groups.js — its functions would "
                 "be undefined when the card renders")
    if order.index("dictation-card.js") > order.index("notify.js"):
        fail("dictation-card.js must load BEFORE notify.js: notify.js uses its "
             "langGroupRow/langBackRow and dictVoices")


CHECKS = [
    ("two spellings of one locale become one row (his repetition)",
     check_two_spellings_of_one_locale_become_one_row),
    ("the two SCRIPTS stay two choices (the merge he overruled)",
     check_the_two_scripts_stay_two_choices),
    ("two regions of one language stay two choices",
     check_regions_of_one_language_stay_two_choices),
    ("a lone variant wears no distinguishing word",
     check_a_lone_variant_is_not_labelled),
    ("the tag handed back is never rewritten",
     check_the_tag_handed_back_is_never_rewritten),
    ("several voices of one locale ALL survive",
     check_several_voices_of_one_locale_all_survive),
    ("one speaker shipped local+network is ONE row",
     check_one_speaker_shipped_twice_is_one_row),
    ("a network-only speaker is still offered",
     check_a_network_only_voice_is_still_offered),
    ("deduping never reshuffles the numbering",
     check_dedupe_does_not_reshuffle_the_numbering),
    ("a readable variant is kept (his 'female 1 male 1')",
     check_readable_variants_are_kept),
    ("every heading is English, whatever the platform supplied",
     check_every_heading_is_english_whatever_the_platform_supplied),
    ("nonsense numbers the WHOLE group (incl. a name with no '#')",
     check_nonsense_numbers_the_whole_group),
    ("a bare number is not a name",
     check_a_bare_number_is_not_a_name),
    ("the region is named only when the group spans regions",
     check_region_named_only_when_the_group_spans_regions),
    ("both cards really drive the module",
     check_both_cards_drive_the_module),
    ("a lone variant is not hidden behind a door",
     check_a_lone_variant_is_not_hidden_behind_a_door),
    ("the module stays pure and loads before its readers",
     check_the_module_is_pure_and_loaded_before_its_readers),
]


def main() -> int:
    print("\n=== LANGUAGE GATE ===")
    if shutil.which("node") is None:
        print("LANGUAGE GATE FAILED — node is required (it runs the REAL "
              "client/lang-groups.js rules) and is not on PATH.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nLANGUAGE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nLANGUAGE GATE PASSED — language first, and no variant lost.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
