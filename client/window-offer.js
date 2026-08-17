// A window opened on the PC while he is watching a layout — HE decides where
// it goes (owner amendment to task 202, 2026-08-11).
//
// The failure this answers: an agent opened its HTML report outside the
// layout's region, under the members' always-on-top band, and the only way to
// it — choosing Desktop — minimizes the layout and loses his place of work.
// The server can now bring such a window into the picture, but his rule is
// that it must ASK first: "when something new opens, ask me whether to open it
// in the layout or normally on the desktop".
//
// The prompt is HERE, on the phone, and never on the PC: a PC-side dialog
// would itself be a window he cannot reach, which is the disease.
//
// The reply goes over HTTP (`POST /window_offer`) and not over the socket,
// exactly like the uploads next door — one small route, no new protocol on a
// dispatcher owned by another round.
//
// IGNORING IT IS AN ANSWER, and the answer is the desktop: the chip fades by
// itself, nothing on the PC moves, and the window stays exactly where Windows
// put it. Only a tap on "Move it in" moves anything.

const winOffer = document.getElementById("window-offer");
const winOfferText = document.getElementById("window-offer-text");
const winOfferIn = document.getElementById("window-offer-in");
const winOfferOut = document.getElementById("window-offer-out");
// The third answer, hidden unless the server says this window can become a
// layout of its own (owner report 2026-08-17 — see WIN_OFFER_WORDS below).
const winOfferNew = document.getElementById("window-offer-new");

let winOfferId = null;
let winOfferTimer = null;
// THE SECOND QUESTION THIS CHIP ASKS (owner request 2026-08-09, task 185): he
// double-clicks an .xlsx through the stream, Excel opens, and the phone asks
// "layout with it?". It is the SAME chip — one strip of screen, one dismissal
// rule, one auto-dismiss — because the two questions are the same shape and a
// second floating prompt would be a second thing to notice, a second thing to
// ignore and a second thing to get in the way of the controls. Only the words
// and the answer differ, so only the words and the answer are variables.
let winOfferAct = "layout";        // "layout" (task 202) | "layout_new" (185)
let winOfferWindow = null;         // the window a `layout_new` chip is about

// THE WORDING MUST NAME THE ACT, not just the event (owner report 2026-08-13,
// defect 2): "X opened" read as an offer to CREATE a layout with the window —
// it is not; the yes MOVES the window into the layout he is already watching.
// "layout_new"'s yes is the one that creates something, and its own words say
// so ("Make a layout"). The two chips must never read alike again.
const WIN_OFFER_WORDS = {
  layout: { text: (n) => `${n} opened outside this layout`,
            yes: "Move it in", no: "Leave on desktop" },
  layout_new: { text: (n) => `${n} opened — a layout with it?`,
                yes: "Make a layout", no: "No" },
  // THE THIRD QUESTION, and the one that is a way OUT rather than a way in
  // (owner report 2026-08-12, his fifth on one failure): a window is off
  // every screen and there is no taskbar on a phone, so without this chip
  // there is no path to it from here at all. The words say WHERE it is and
  // not what opened it — the PC does not know what opened it, and pretending
  // otherwise is what four earlier rounds did.
  rescue: { text: (n) => `${n} is off the screen`,
            yes: "Bring it back", no: "Leave it" },
};

// How long the chip stands. Long enough to notice while he is reading the PC
// screen through the stream, short enough that it is never in the way of the
// controls under it.
const WINDOW_OFFER_MS = 30000;

function hideWindowOffer() {
  clearTimeout(winOfferTimer);
  winOfferTimer = null;
  winOfferId = null;
  winOfferWindow = null;
  winOffer.hidden = true;
}

// The server names the window (title + process). The title is what he
// recognises, so it gets an element of its own that WRAPS rather than being
// cut — a title he cannot read makes the two buttons a guess.
// A CHIP MAY NOT CHANGE ITS QUESTION UNDER HIS FINGER (owner report
// 2026-08-12, and his own server log dated it: FIVE offers arrived in 400 ms,
// each one silently replacing the last, so the tap he made answered a question
// he had never read — and that question's yes MOVED a window). The server no
// longer asks two things about one window, but several windows can still open
// at once, and one strip can only ask about one of them.
//
// So a chip that has been standing for less than this is not replaced: the
// newcomer WAITS, and goes up when the current one is answered or fades. A
// queue and not a second strip, because a second floating prompt is a second
// thing to notice and a second thing in the way of the controls.
const WIN_OFFER_SETTLE_MS = 2500;

let winOfferShownAt = 0;
const winOfferQueue = [];

function nextWindowOffer() {
  const msg = winOfferQueue.shift();
  if (msg) showWindowOffer(msg, true);
}

function showWindowOffer(msg, dequeued) {
  if (!msg || !msg.id) return;
  if (!dequeued && winOfferId && !winOffer.hidden
      && Date.now() - winOfferShownAt < WIN_OFFER_SETTLE_MS) {
    // Bounded: he cannot be asked about a hundred windows, and an offer that
    // waited past the server's own TTL would be a question about a window he
    // walked past long ago.
    if (winOfferQueue.length < 4) winOfferQueue.push(msg);
    return;
  }
  winOfferShownAt = Date.now();
  winOfferId = msg.id;
  // An `act` this page does not know falls back to the one that was here
  // first — a chip whose buttons say nothing is worse than a chip that asks
  // the older question, and a PC newer than the page is a real state.
  winOfferAct = WIN_OFFER_WORDS[msg.act] ? msg.act : "layout";
  const words = WIN_OFFER_WORDS[winOfferAct];
  // THE WINDOW'S IDENTITY IS KEPT WHENEVER A CREATE ANSWER IS ON THE CHIP —
  // task 185's own chip, and now the sweep's `new_ok` one too (owner report
  // 2026-08-17). Both seed the SAME creation panel with the SAME slot, which
  // is the whole point of his report: the mechanics after the tap must be the
  // ones Tap / List / New already use.
  const canNew = winOfferAct === "layout_new" || !!msg.new_ok;
  winOfferWindow = canNew && msg.hwnd
    ? { hwnd: msg.hwnd, title: msg.title, process: msg.process, icon: msg.icon }
    : null;
  // A `layout` chip that carries the create answer shows it as its own row;
  // a `layout_new` chip's create answer IS its yes, so it never doubles.
  const showNew = canNew && winOfferAct === "layout" && !!winOfferWindow;
  winOfferNew.hidden = !showNew;
  winOffer.classList.toggle("has-new", showNew);
  const name = (msg.title || msg.process || "A window").trim();
  winOfferText.textContent = words.text(name);
  winOfferIn.textContent = words.yes;
  winOfferOut.textContent = words.no;
  winOfferText.title = name;
  winOffer.hidden = false;
  clearTimeout(winOfferTimer);
  // No answer is the desktop answer — the chip simply goes, and whatever was
  // waiting behind it gets its turn.
  winOfferTimer = setTimeout(() => {
    hideWindowOffer();
    nextWindowOffer();
  }, WINDOW_OFFER_MS);
}

async function answerWindowOffer(act) {
  const id = winOfferId;
  const win = winOfferWindow;
  hideWindowOffer();
  if (!id) return;
  // TASK 185's YES LEADS INTO THE PANEL HE ALREADY KNOWS, and it does so
  // BEFORE the POST rather than after it: the panel is entirely phone-side
  // (the PC moves nothing either way here), and making him watch a round trip
  // to open a card would be a wait for nothing. The POST still goes, because
  // it is what stops the PC asking about this window again.
  if (act === "layout_new") {
    // The sweep's own create answer (owner report 2026-08-17). Same two lines
    // as task 185's yes below and deliberately so: one seeding path, so the
    // two chips can never drift into two different creation flows.
    startFromWindow(win);
  } else if (act === "layout" && winOfferAct === "layout_new") {
    startFromWindow(win);
    act = "layout_new";
  } else if (act === "layout" && winOfferAct === "rescue") {
    // The yes of a rescue chip is the rescue itself — nothing opens here, the
    // PC moves the window. The server treats any act it does not recognise as
    // "leave it", so the word has to be the exact one it is waiting for.
    act = "rescue";
  }
  try {
    await fetch(`/window_offer?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, act }),
    });
  } catch (err) {
    showToast(`Could not answer: ${err.message}`);
  }
  nextWindowOffer();
}

winOfferNew.addEventListener("click", () => answerWindowOffer("layout_new"));
winOfferIn.addEventListener("click", () => answerWindowOffer("layout"));
winOfferOut.addEventListener("click", () => answerWindowOffer("desktop"));
