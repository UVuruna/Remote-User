// Which sets ride the phone's wheel — the per-device composition rules.
// Split out of controls.js (THE STRUCTURE LAW, 2026-08-06): controls.js owns
// the D-pad groups, the wheel and what a button DOES; this module owns the
// question "which sets exist on this phone right now, and may they all fit".
// Loaded BEFORE controls.js and panels.js — both read the state declared here.
//
// Three sources feed the wheel: the shipped categories, the owner's custom
// sets (both from actions.json) and the app-aware sets, which appear only
// while a layout is focused. THE CAP OF 8 (owner 2026-08-06) is a law over
// all three together.

let categories = [];
let appSets = [];    // app-aware sets from actions.json (owner 2026-08-04)
let customSets = []; // owner-made sets from the desktop editor (owner 2026-08-05)
// Phone-side wheel preferences (the Settings → Sets picker): which custom
// sets this DEVICE hides, and whether app-aware sets appear. Per-phone on
// purpose — the desktop editor sets the defaults, the phone overrides them.
function setsPrefs() {
  try {
    const p = JSON.parse(prefGet("setsPrefs") || "{}");
    return {
      state: p.state && typeof p.state === "object" ? p.state : {},
      // Per-app-set choice (owner 2026-08-05): `apps` is still the master
      // switch, `appState` names the ones hidden inside it — two sets can now
      // match the same process (VSCode + Claude), and hiding one of them is
      // the whole point.
      appState: p.appState && typeof p.appState === "object" ? p.appState : {},
      apps: p.apps !== false,
    };
  } catch {
    return { state: {}, appState: {}, apps: true };
  }
}

// Effective on/off for one toggleable set (an optional shipped category OR a
// custom set — required ones never ask): the phone's explicit choice wins,
// otherwise the desktop editor's default (`enabled` in actions.json).
function setOn(s) {
  const choice = setsPrefs().state[s.name];
  return choice !== undefined ? choice : s.enabled !== false;
}

function saveSetsPrefs(p) {
  prefSet("setsPrefs", JSON.stringify(p));
}

// App-aware sets exist ONLY in layout focus (owner decision 2026-08-04):
// when the focused layout's app matches a set's `process`, that set appears
// as an extra category in the wheel — nothing switches by itself, and the
// category vanishes with the layout focus.
function appSetOn(s) {
  const choice = setsPrefs().appState[s.name];
  return choice !== undefined ? choice : s.enabled !== false;
}

// A set may also demand a TITLE match (owner 2026-08-05): Claude Code runs
// INSIDE VSCode, same process, so the process alone cannot tell the two
// apart. `title` is matched against the layout's ORIGINAL window/tab title —
// never its name, which the owner may have renamed to anything. A set with
// no `title` matches the process as before, which is why VSCode and Claude
// can ride together while only one of them knows it is Claude.
//
// The test is a WORD, not a substring, and a DOCUMENT never matches (owner
// 2026-08-06, shouted): the Claude set may appear for the Claude conversation
// tab and for nothing else — an open `CLAUDE.md`, a transcript, any text file
// is still plain VSCode. Substring matching gave every one of those the
// Claude wheel. `title` may be a list, so one set can name several spellings.
const DOC_TITLE = /\.[a-z0-9]{1,6}(\s*[-—•]\s*.*)?$/i;  // "CLAUDE.md", "notes.txt — Visual Studio Code"

function titleMatches(want, title) {
  const t = String(title || "").toLowerCase().trim();
  if (!t || DOC_TITLE.test(t)) return false;  // a file tab is a document
  const words = (Array.isArray(want) ? want : [want]).map((w) => String(w).toLowerCase());
  return words.some((w) => w && new RegExp(`(^|[^a-z0-9])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z0-9]|$)`).test(t));
}

// Does this app set belong to this layout? The owner's own tick wins over
// every guess (owner 2026-08-06): `lay.app_sets` is the list he ticked when
// he made the layout, and a layout that HAS the list is answered from it
// alone. The probe that forced this is in window_manager.Layout — Claude Code
// names its VSCode tab after the CONVERSATION ("Ispravka UI dizajna meni…"),
// carries the same UIA class as a file tab and exposes nothing else, so no
// string test can ever find it. Only layouts made before this version (list
// = null) still fall through to the process/title guess below.
function appSetMatches(s, lay) {
  // The owner's own ticks still win, wherever he made them — detection is the
  // default, never a cage.
  if (Array.isArray(lay.app_sets)) return lay.app_sets.includes(s.name);
  const proc = String(lay.process || "").toLowerCase();
  if (!proc.includes(String(s.process || "").toLowerCase())) return false;
  // An AGENT set asks the PC, not the window text (owner 2026-08-06, after
  // the manual ticking he called what it was). The server reads the process
  // table — a running claude.exe carries its session id, the session id names
  // its project, and this window's title names the same project — and sends
  // the answer as `agents`. A title guess could never have done this: Claude
  // Code names its tab after the CONVERSATION and VS Code hides webview
  // content from accessibility. `title` stays underneath as the fallback for
  // a server too old to send `agents`.
  if (s.agent) {
    if (Array.isArray(lay.agents)) return lay.agents.includes(s.agent);
    return s.title ? titleMatches(s.title, lay.title) : false;
  }
  // No title test = the whole app. VSCode therefore rides ALONGSIDE Claude on
  // a Claude tab — the owner's rule of 2026-08-06: this is the one case where
  // two app sets appear at once, and both are wanted (the editor's own
  // shortcuts stay reachable while Claude's commands are there).
  if (!s.title) return true;
  return titleMatches(s.title, lay.title);
}

// Which app sets a new layout starts out carrying. Two fixes on 2026-08-06:
// EVERY slot is considered, not just the first (a 2x2 with Chrome in cell two
// never pre-ticked Chrome — the owner's "we went backwards" was wrong about
// VSCode, which was always pre-ticked, and right that something was missing),
// and an AGENT set is included when the server says that agent is live in the
// window's project, so Claude needs no tap either.
function autoAppSets(slots) {
  const procs = slots.map((s) => String(s.process || "").toLowerCase());
  const agents = slots.flatMap((s) => (Array.isArray(s.agents) ? s.agents : []));
  return appSets
    .filter((s) => {
      const proc = String(s.process || "").toLowerCase();
      if (!procs.some((p) => p.includes(proc))) return false;
      if (s.agent) return agents.includes(s.agent);
      return !s.title;
    })
    .map((s) => s.name);
}

function visibleAppSets() {
  if (!setsPrefs().apps) return [];
  if (layoutActive === null || !layouts[layoutActive]) return [];
  const lay = layouts[layoutActive];
  return appSets.filter((s) => appSetMatches(s, lay) && appSetOn(s));
}

// How many wheel slots the ticked app sets RESERVE (owner 2026-08-06). Not
// simply "how many are ticked": Chrome, Explorer and VSCode can never appear
// together, so ticking all of them costs one slot, not three. What costs two
// is VSCode + Claude — the one case where two sets share a process and both
// are meant to ride. The charge is therefore the largest group of ticked sets
// that CAN match at the same time, which is the group per process.
function appSetReserve() {
  if (!setsPrefs().apps) return 0;
  const perProcess = {};
  for (const s of appSets) {
    if (!appSetOn(s)) continue;
    const key = String(s.process || "").toLowerCase();
    perProcess[key] = (perProcess[key] || 0) + 1;
  }
  return Math.max(0, ...Object.values(perProcess));
}

// The wheel's composition (owner 2026-08-05, revised same day): Mouse, Input
// and Settings are REQUIRED (`required` in actions.json — never hidden); the
// other shipped sets (Edit, Attach, Navigate, Cursor, Media, Windows) and
// the custom sets are toggleable; the app set rides along in layout focus.
// Hard cap WHEEL_MAX total — over the cap, non-required sets are bumped from
// the END (they come back when the app set goes away).
const WHEEL_MAX = 8;

function visibleCount() {
  // What the picker charges against the cap. App sets are NOT free (owner
  // 2026-08-06): a Claude tab puts BOTH VSCode and Claude on the wheel, so
  // ticking both leaves room for six others, not seven. Counting them as
  // free let the picker promise eight while the wheel silently dropped two.
  return categories.filter((c) => c.required || setOn(c)).length +
    customSets.filter(setOn).length +
    appSetReserve();
}

// THE CAP IS A LAW, NOT A HINT (owner 2026-08-06, after finding NINE sets
// ticked by default on his own phone). Until now the cap was tested only at
// the moment of a tap, so any state that arrived another way — prefs saved
// before app sets started charging (v0.0.213), or desktop `enabled` defaults
// — sailed straight past it: the picker printed "9 of 8 used" while allCats()
// silently dropped the last two off the wheel. The stored state is now
// normalized to the cap, so what the picker shows IS what the wheel holds.
//
// WHICH set gives way is the owner's own rule: "ako samo 7 osnovnih onda mora
// jedan od claude i vscode da bude iskljucen" — the app-aware set goes first,
// because his 7 chosen basics are the ones he ticked on purpose. Only a set
// in the CHARGING group can free a slot: unticking Chrome while VSCode and
// Claude hold two slots between them changes nothing at all.
function capVictim() {
  if (setsPrefs().apps) {
    const groups = {};
    for (const s of appSets) {
      if (!appSetOn(s)) continue;
      const k = String(s.process || "").toLowerCase();
      (groups[k] = groups[k] || []).push(s);
    }
    let charging = null;
    for (const g of Object.values(groups))
      if (!charging || g.length > charging.length) charging = g;
    if (charging && charging.length > 1)
      return { name: charging[charging.length - 1].name, app: true };
  }
  const optional = categories.filter((c) => !c.required && setOn(c))
    .concat(customSets.filter(setOn));
  if (optional.length) return { name: optional[optional.length - 1].name, app: false };
  // Nothing optional left: the last app set still charging its one slot.
  const lastApp = appSets.filter(appSetOn).pop();
  return lastApp ? { name: lastApp.name, app: true } : null;
}

// Bring the stored state down to the cap. Returns the sets it had to switch
// off so the caller can SAY so — a set disappearing without a word is what
// "the picker rotates" felt like.
function enforceWheelCap() {
  const dropped = [];
  for (let guard = 0; guard < 64 && visibleCount() > WHEEL_MAX; guard++) {
    const victim = capVictim();
    if (!victim) break;
    const p = setsPrefs();
    if (victim.app) p.appState[victim.name] = false;
    else p.state[victim.name] = false;
    saveSetsPrefs(p);
    dropped.push(victim.name);
  }
  return dropped;
}

function allCats() {
  const list = categories.filter((c) => c.required || setOn(c))
    .concat(visibleAppSets())
    .concat(customSets.filter(setOn));
  for (let i = list.length - 1; list.length > WHEEL_MAX && i >= 0; i--) {
    if (!list[i].required) list.splice(i, 1);
  }
  return list;
}
