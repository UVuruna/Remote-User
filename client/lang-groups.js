// LANGUAGE FIRST, VARIANT SECOND — the grouping both language lists wear,
// pure by design (no DOM, no socket, no state of its own) so its gate can run
// it whole (the client/grid-icons.js / view-anchor.js / cursor-shapes.js
// pattern).
//
// Owner report 2026-08-13: *"za VOICE koji prica i za MIC kome pricamo ne
// treba kao sada da bude nagomilano 100 njih u ogromnoj listi vec po jezicimo
// ... npr Engleski pa kad otvorimo ponudi se Voice 1,2,3... koji mozemo da
// poslusamo"*, and of the dictation list: *"tu isto se ponavljaju bez potrebe
// pa imamo vise puta iste odabire"*.  // lang-ok: owner quote
//
// TWO LISTS, ONE GRAMMAR. The notification-voice card (client/notify.js) and
// the dictation card (client/panels.js) had each grown their own flat list —
// one printing whatever the TTS engine returned in engine order, the other
// printing every system locale and keyboard subtype. Both are now language
// rows that OPEN into their variants, and the grouping lives here once because
// two copies of a rule is how the two cards would drift apart.
//
// WHY NOTHING IS DELETED. The first plan was to DEDUPE the dictation list by
// language — his own answer overruled it: *"da ali sa podgrupama jer korisnik
// treba da bira da li ce output da ide cirilica ili latinica isto kao sto
// engleski ima vise odabira"*.  // lang-ok: owner quote
// So `sr-Latn` and `sr-Cyrl` are not two spellings of one row to be collapsed;
// they are the CHOICE OF SCRIPT HIS DICTATED TEXT COMES OUT IN, exactly as
// en-US and en-GB are a real choice. Grouping alone removes what he called
// repetition (one "Srpski" row instead of several), and it removes it without
// taking a decision away — which a merge would have done, silently.
//
// What IS collapsed is only ever the SAME variant written twice. Android hands
// one locale to us in more than one spelling: `LocaleList.getAdjustedDefault()`
// gives "sr-RS" while an IME subtype gives "sr-Latn-RS" or even "sr_RS"
// (VoiceInput.kt `candidateTags` normalizes the underscore but not the script),
// so a canonical key — language + script + region, with the script FILLED IN
// when the tag left it out — is what makes two spellings one row while keeping
// two real scripts apart.
//
// THE TAG IS NEVER REWRITTEN. A group keeps the FIRST tag seen for each
// canonical key and hands that exact string back, because it is what goes to
// `Android.voiceSetLang()` / `Android.speakAs()` — a canonical key is for
// deciding sameness, never for talking to the recognizer, which may well not
// accept a spelling we invented.

// Scripts a bare language tag really means, for the languages this app's own
// sample table covers. Only a language whose default script is NOT the one a
// reader would guess from the tag needs an entry — the point is that "sr" and
// "sr-Cyrl" must land on ONE row while "sr-Latn" stands apart.
//
// `Intl.Locale.maximize()` answers this properly and is used when the WebView
// has it (Chrome 74+, so every device that can run this app). This table is
// the fallback and deliberately SMALL: a wrong guess here would split one
// language into two rows, which is the very defect being fixed, so a language
// not listed gets NO assumed script rather than a plausible one.
const LANG_DEFAULT_SCRIPT = {
  sr: "Cyrl", ru: "Cyrl", uk: "Cyrl", bg: "Cyrl", mk: "Cyrl", be: "Cyrl",
  el: "Grek", he: "Hebr", ar: "Arab", fa: "Arab", ur: "Arab",
  hi: "Deva", th: "Thai", ko: "Kore", ja: "Jpan", zh: "Hans",
  hy: "Armn", ka: "Geor", am: "Ethi",
};

/** A tag split into its parts, lowercased and underscore-normalized.
 *  Android spells one locale several ways and every rule below reads this. */
function langParts(tag) {
  const parts = String(tag == null ? "" : tag)
    .replace(/_/g, "-").trim().toLowerCase().split("-").filter(Boolean);
  const out = { lang: parts[0] || "", script: "", region: "" };
  for (const p of parts.slice(1)) {
    // A script subtag is four letters, a region is two letters or three
    // digits (BCP-47). Anything else — a variant, a private-use tail such as
    // the "x-sfg" in a Samsung voice name — is not part of identity here.
    if (!out.script && /^[a-z]{4}$/.test(p)) out.script = p;
    else if (!out.region && /^([a-z]{2}|[0-9]{3})$/.test(p)) out.region = p;
  }
  return out;
}

/** The language subtag alone — the GROUP a row belongs to. */
function langKey(tag) {
  return langParts(tag).lang;
}

/** The script a tag really means, filled in when the tag left it out.
 *
 *  This is the whole reason "sr-RS" and "sr-Cyrl-RS" are one row while
 *  "sr-Latn-RS" is its own: without resolution the first two look as
 *  different as the third, and his Serbian appeared twice. */
function langScript(tag) {
  const p = langParts(tag);
  if (!p.lang) return "";
  if (p.script) return p.script;
  try {
    // The authority when the platform has it. Wrapped because a WebView
    // without `Intl.Locale` throws rather than returning undefined, and a
    // language list is not worth a broken card.
    if (typeof Intl !== "undefined" && Intl.Locale) {
      const max = new Intl.Locale(p.region ? `${p.lang}-${p.region}` : p.lang)
        .maximize();
      if (max && max.script) return String(max.script).toLowerCase();
    }
  } catch { /* fall through to the table */ }
  return (LANG_DEFAULT_SCRIPT[p.lang] || "").toLowerCase();
}

/** The identity of one VARIANT inside its language: language + resolved
 *  script + region. Two tags with the same key are the same choice written
 *  twice; two tags that differ anywhere here are two choices. */
function langVariantKey(tag) {
  const p = langParts(tag);
  if (!p.lang) return "";
  return [p.lang, langScript(tag), p.region].join("|");
}

/** The platform's own name for a language with its region dropped: "Srpski
 *  (Srbija)" becomes "Srpski", "English (United States)" becomes "English".
 *
 *  A group heading is built by SHORTENING his own wording rather than looking a
 *  new one up, and that is deliberate. `Intl.DisplayNames` answers "sr" with
 *  the Cyrillic endonym "Српски" while every row of his card is written in
 *  Latin — so a lookup would have replaced a familiar word with a correct one
 *  he does not read, in the very list whose whole point is that he recognises
 *  his language in it. Dropping a parenthesis keeps his spelling and removes
 *  only the part that was false of the group.
 *
 *  Returns "" when there is nothing to shorten, which sends the caller to the
 *  lookup — a name with no region in it was never the problem. */
function langBareName(given) {
  const s = String(given == null ? "" : given).trim();
  if (!s) return "";
  const cut = s.indexOf(" (");
  const bare = cut > 0 ? s.slice(0, cut).trim() : s;
  return bare;
}

/** The endonym-ish name of a language, for a GROUP heading.
 *
 *  Preference order is deliberate: a name the platform gave us (the dictation
 *  card's rows already carry `Locale.getDisplayName(locale)` from Kotlin, the
 *  language in ITS OWN words) beats one we look up, and a lookup beats the
 *  bare subtag. The subtag is the last resort and is upper-cased so it reads
 *  as a code rather than as a misspelt word. */
function langGroupName(tag, given) {
  const supplied = String(given == null ? "" : given).trim();
  if (supplied) return supplied;
  const lang = langKey(tag);
  if (!lang) return "";
  try {
    if (typeof Intl !== "undefined" && Intl.DisplayNames) {
      // In the language's own words where the platform can, which is what the
      // dictation card has always done (`getDisplayName(locale)`).
      const dn = new Intl.DisplayNames([lang, "en"], { type: "language" });
      const name = dn.of(lang);
      if (name && name.toLowerCase() !== lang) {
        return name.charAt(0).toUpperCase() + name.slice(1);
      }
    }
  } catch { /* the subtag below */ }
  return lang.toUpperCase();
}

/** What tells two variants of ONE language apart, in words.
 *
 *  Only the axes that actually DIFFER inside this group are named, which is
 *  the difference between "Latin" and "Serbian (Latin, Serbia)" on a row whose
 *  heading already says Serbian. When a group's variants differ in script, the
 *  script names them; when they differ only in region, the region does; when
 *  both, both. A group of one needs no distinguishing word at all and gets an
 *  empty string — the heading has already said everything.
 *
 *  `scripts`/`regions` are the sets seen across the group, so this function
 *  cannot be called per row without them: the same tag is labelled "Latin"
 *  beside a Cyrillic sibling and labelled nothing at all when it is alone,
 *  and that is correct in both cases. */
function langVariantLabel(tag, scripts, regions) {
  const p = langParts(tag);
  const bits = [];
  if (scripts && scripts.size > 1) {
    const s = langScript(tag);
    bits.push(scriptName(s) || (s ? s.toUpperCase() : ""));
  }
  if (regions && regions.size > 1) {
    bits.push(regionName(p.region) || (p.region ? p.region.toUpperCase() : ""));
  }
  return bits.filter(Boolean).join(" — ");
}

function scriptName(script) {
  const s = String(script || "");
  if (!s) return "";
  const code = s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  try {
    if (typeof Intl !== "undefined" && Intl.DisplayNames) {
      const dn = new Intl.DisplayNames(["en"], { type: "script" });
      const name = dn.of(code);
      if (name && name !== code) return name;
    }
  } catch { /* the code below */ }
  return code;
}

function regionName(region) {
  const r = String(region || "").toUpperCase();
  if (!r) return "";
  try {
    if (typeof Intl !== "undefined" && Intl.DisplayNames) {
      const dn = new Intl.DisplayNames(["en"], { type: "region" });
      const name = dn.of(r);
      if (name && name !== r) return name;
    }
  } catch { /* the code below */ }
  return r;
}

/** Group rows by language, collapsing only rows that are the SAME THING
 *  written twice.
 *
 *  `rows` is any array; `tagOf(row)` and `nameOf(row)` say where its tag and
 *  its platform-given name live, so both cards use this with their own row
 *  shapes and neither has to pretend to be the other.
 *
 *  `idOf(row)` is WHAT MAKES TWO ROWS THE SAME, and the two cards answer it
 *  differently — running this module before wiring it proved they must. A
 *  dictation row IS its locale, so two spellings of one locale are one row
 *  (the whole repetition he reported). A VOICE is its own name: several voices
 *  share one locale, so keying a voice by its locale silently threw away every
 *  voice of a language but the first — his American "male 1" would simply have
 *  vanished, and the card would have looked tidy while offering less than
 *  before. Defaults to the canonical locale key, which is the dictation rule.
 *
 *  Returns `[{ key, name, variants: [{ tag, row, label }], … }]` — groups in
 *  first-seen order (the platform's own preference order: his system locale
 *  first, which is the one he most likely wants), variants likewise. A group
 *  of one still comes back as a group, so the caller has ONE shape to render
 *  and decides for itself whether a single variant is worth a drill-down. */
function groupByLanguage(rows, tagOf, nameOf, idOf) {
  const order = [];
  const byLang = new Map();
  for (const row of (rows || [])) {
    const tag = tagOf ? tagOf(row) : (row && row.tag);
    const lang = langKey(tag);
    if (!lang) continue;                 // a row we cannot place is not shown
    let g = byLang.get(lang);
    if (!g) {
      g = { key: lang, name: "", variants: [], seen: new Set() };
      byLang.set(lang, g);
      order.push(g);
    }
    const vk = idOf ? String(idOf(row)) : langVariantKey(tag);
    // FIRST SPELLING WINS. The platform's preference order put it first, and
    // it is the tag the recognizer was offered, so it is the one to keep.
    if (g.seen.has(vk)) continue;
    g.seen.add(vk);
    g.variants.push({ tag: String(tag), row });
    // The platform's own name for the FIRST row, kept only as a candidate:
    // whether it may be used as the group's heading cannot be known yet — see
    // the naming pass below.
    if (!g.given) g.given = nameOf ? String(nameOf(row) || "") : "";
  }
  for (const g of order) {
    // The distinguishing words can only be chosen once the whole group is
    // known — see langVariantLabel.
    const scripts = new Set(g.variants.map((v) => langScript(v.tag)));
    const regions = new Set(g.variants.map((v) => langParts(v.tag).region));
    for (const v of g.variants) {
      v.label = langVariantLabel(v.tag, scripts, regions);
    }
    // THE HEADING MUST BE TRUE OF THE WHOLE GROUP, and that is only knowable
    // here. The platform hands each row a full endonym including its region —
    // "English (United States)", "Srpski (Srbija)" — which is exactly right on
    // a row standing for itself and a LIE over a group that also holds the
    // United Kingdom, or the other script. Photographing the card is what
    // caught it: the list read "English (United States)  2", naming one of the
    // two things behind it.
    //
    // So a group of SEVERAL variants is named by its language alone, looked up
    // rather than taken from any one row; a group of ONE keeps the platform's
    // own wording, which is the name this card has always shown.
    g.name = g.variants.length === 1
      ? langGroupName(g.variants[0].tag, g.given)
      : langGroupName(g.variants[0].tag, langBareName(g.given));
    if (!g.name) g.name = g.key.toUpperCase();
    delete g.seen;
    delete g.given;
  }
  return order;
}

// --- Voices ---------------------------------------------------------------
//
// A voice's variant is the tail of its engine name: "sr-rs-x-sfg#female_1"
// is female_1, "en-us-x-tpf#network" is network. Kotlin already builds a
// label as "<language> <variant>" (Notifier.kt `voices`), and INSIDE a
// language group that language word is the heading — repeated on every row it
// is exactly the pile the owner is complaining about — so the variant is
// derived here from the NAME rather than by trying to subtract a word from a
// label whose language spelling this page cannot know.

/** The variant tail of an engine voice name, in plain words, or "".
 *
 *  NO `#`, NO VARIANT. An engine name like "sr-rs-x-sfg" carries a locale and
 *  a private-use id and nothing about the speaker, so there is nothing here to
 *  show him — running this module before wiring it caught exactly that name
 *  being offered as the words "sr rs x sfg", which is the nonsense case his
 *  ruling exists to forbid, sailing through the readability test because it
 *  happens to be letters and digits. An empty answer sends the whole group to
 *  "Voice 1, 2, 3", which is the correct outcome for it. */
function voiceVariant(name) {
  let s = String(name == null ? "" : name);
  const hash = s.lastIndexOf("#");
  if (hash < 0) return "";
  s = s.slice(hash + 1);
  // Engine-side qualifiers that say where the voice RUNS, not who it sounds
  // like. They are not a name and they are not his choice to make.
  s = s.replace(/[-_](local|network|compact|embedded)$/i, "");
  return s.replace(/[-_]+/g, " ").trim();
}

/** Is this variant a WORD he can choose by, or engine machinery?
 *
 *  His ruling, in his own two cases: keep the variant when it reads like
 *  "female 1" or "male 1", and fall back to "Voice 1, 2, 3" when it is
 *  "glupi karakteri" — nonsense characters.  // lang-ok: owner's own term
 *  So the test is readability, and it is STRICTER than it first looks — its
 *  own gate caught the loose version. Every word must be a WORD, optionally
 *  carrying a trailing number ("female", "female1", "1"), and at least one
 *  must have letters. "letters and digits and spaces" was not enough: a hex
 *  id like "7f3a2b1c" is letters and digits, and it went out under his own
 *  ruling as a name. A token that STARTS with a digit and then has letters, or
 *  interleaves them, is machinery — and machinery numbers the whole group.
 *
 *  A bare number is refused too: "3" as a name reads as a broken row, while
 *  "Voice 3" is the numbering he asked for. */
function voiceVariantReadable(variant) {
  const s = String(variant || "").trim();
  if (!s || s.length > 24) return false;
  const words = s.split(" ");
  if (words.some((w) => !/^([a-z]+[0-9]*|[0-9]+)$/i.test(w))) return false;
  return words.some((w) => /^[a-z]/i.test(w));
}

/** Name every voice of ONE language group — variants when they are words,
 *  "Voice 1, 2, 3" when they are not.
 *
 *  THE GROUP IS THE UNIT, never the row. Half a group wearing "female 1" and
 *  the other half "Voice 2" is worse than either alone: the numbers would not
 *  even be a sequence he could read. So one unreadable or duplicated variant
 *  numbers the whole group. Duplicates count as unreadable for the same
 *  reason — two rows called "female 1" are not a choice, and their order is
 *  the engine's, so numbering at least tells them apart honestly.
 *
 *  `voices` is that group's voices in order; returns their labels in the same
 *  order. The region is appended only when the group SPANS regions, the same
 *  rule langVariantLabel follows: inside one language, "female 1" and
 *  "female 1 (United Kingdom)" is the distinction he needs, and "(United
 *  States)" on every row of an American-only group is noise. */
function voiceGroupLabels(voices) {
  const list = Array.isArray(voices) ? voices : [];
  const variants = list.map((v) => voiceVariant(v && v.name));
  const regions = new Set(list.map((v) => langParts(v && v.locale).region));
  const unique = new Set(variants);
  const readable = variants.length > 0
    && variants.every(voiceVariantReadable)
    && unique.size === variants.length;
  return list.map((v, i) => {
    const base = readable ? variants[i] : `Voice ${i + 1}`;
    if (regions.size > 1) {
      const r = regionName(langParts(v && v.locale).region);
      if (r) return `${base} (${r})`;
    }
    return base;
  });
}

/** Both halves at once, for the voice card: groups by language, then names
 *  the voices inside each group by the rule above. Same shape as
 *  groupByLanguage, with `label` filled from voiceGroupLabels instead of the
 *  script/region words — a voice's variants differ by SPEAKER, and calling
 *  them all "United States" would name none of them. */
function groupVoicesByLanguage(voices) {
  const groups = groupByLanguage(
    (voices || []).filter((v) => v && v.name),
    (v) => v.locale || v.name,     // a voice with no locale still has a name
    () => "",                       // the engine's label carries the language
    (v) => v.name,                  // A VOICE IS ITS NAME — see groupByLanguage
  );
  for (const g of groups) {
    const labels = voiceGroupLabels(g.variants.map((v) => v.row));
    g.variants.forEach((v, i) => { v.label = labels[i]; });
  }
  return groups;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    LANG_DEFAULT_SCRIPT, langParts, langKey, langScript, langVariantKey,
    langGroupName, langBareName, langVariantLabel, scriptName, regionName,
    groupByLanguage, voiceVariant, voiceVariantReadable, voiceGroupLabels,
    groupVoicesByLanguage,
  };
}
