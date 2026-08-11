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
// put it. Only a tap on "Show in layout" moves anything.

const winOffer = document.getElementById("window-offer");
const winOfferText = document.getElementById("window-offer-text");
const winOfferIn = document.getElementById("window-offer-in");
const winOfferOut = document.getElementById("window-offer-out");

let winOfferId = null;
let winOfferTimer = null;

// How long the chip stands. Long enough to notice while he is reading the PC
// screen through the stream, short enough that it is never in the way of the
// controls under it.
const WINDOW_OFFER_MS = 30000;

function hideWindowOffer() {
  clearTimeout(winOfferTimer);
  winOfferTimer = null;
  winOfferId = null;
  winOffer.hidden = true;
}

// The server names the window (title + process). The title is what he
// recognises, so it gets an element of its own that WRAPS rather than being
// cut — a title he cannot read makes the two buttons a guess.
function showWindowOffer(msg) {
  if (!msg || !msg.id) return;
  winOfferId = msg.id;
  const name = (msg.title || msg.process || "A window").trim();
  winOfferText.textContent = `${name} opened`;
  winOfferText.title = name;
  winOffer.hidden = false;
  clearTimeout(winOfferTimer);
  // No answer is the desktop answer — the chip simply goes.
  winOfferTimer = setTimeout(hideWindowOffer, WINDOW_OFFER_MS);
}

async function answerWindowOffer(act) {
  const id = winOfferId;
  hideWindowOffer();
  if (!id) return;
  try {
    await fetch(`/window_offer?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, act }),
    });
  } catch (err) {
    showToast(`Could not answer: ${err.message}`);
  }
}

winOfferIn.addEventListener("click", () => answerWindowOffer("layout"));
winOfferOut.addEventListener("click", () => answerWindowOffer("desktop"));
