"""THE FRAME LAW, measured on the phone — the instrument tasks 156 needed.

Split out of tests/_audit_js.py on 2026-08-10 (THE STRUCTURE LAW), the run
that added it: it is one self-contained instrument with a long written
reason for existing, and _audit_js.py sits on the 1,000-line limit. The
boundary that file's own docstring states is unchanged — this is still HOW a
truth about pixels is measured, not WHICH screen is opened.

Nothing here imports anything: every value is a JavaScript source string the
audit installs into the live page.
"""

# ── THE FRAME LAW, ON THE PHONE (owner 2026-08-09, task 156) ─────────────────
# His rule, in translation: an element may not carry a radius so large that it
# becomes a circle or an egg — a radius is allowed only when the element is wide
# enough — and elements of one kin group must all be the same size, "not like
# here, where Landscape is bigger than Portrait although they belong to the same
# group". And the sentence that matters most: there is a rulebook and a hook for
# NEW gui elements, "ali ne moze da proveri stare jer niko nije prosao"
# (lang-ok: owner quote — it names the mechanism this tooth exists to fix).
#
# WHY NOTHING HAD EVER CHECKED IT HERE, mechanically:
#   * The two rules are ALG-6 RADIUS BY ASPECT RATIO and ALG-5 UNIFORM SIBLINGS
#     (rules/GUI.md -> Zubi v2), and both are implemented ONLY in the Qt
#     template (rules/templates/layout_checks_qt.py): they walk QWidgets and
#     parse QSS. Neither can see a CSS rule or an HTML element, so the whole
#     phone client — the surface he actually photographed — had no radius
#     instrument of any kind.
#   * The machine-wide PreToolUse hook (rules/hooks/layout_guard.py) is a
#     PATTERN SCANNER over the text of an edit. Its banned list is elision,
#     hard sizes, disabled wrapping and forced scrollbars — there is no radius
#     rule and no sibling rule in it at all, and there could not be: both need a
#     LAID-OUT element (a width, a height, a sibling to compare against), which
#     does not exist at the moment a file is written.
#   * The phone's one kin instrument, `__kinRows` above, measures `.lay-item`
#     ROWS and their `.lay-ratio` trailing buttons. The offending elements are
#     `.lay-chip` chips in the creation panel — a different element in a
#     different panel — and that panel's slot-filled state, the one his
#     screenshot shows, is staged by the sweep but never MEASURED for either
#     rule. "Nobody ever went through it" is exact.
#
# So this is the instrument for the surface that had none. It is pointed at a
# ROOT the caller names (a card, a control group), not at the whole document:
# what he reported is about the boxes on his panels, and a tooth that also
# convicted the stream canvas would be noise nobody reads.
#
# THE EXEMPTIONS ARE NAMED, WITH REASONS, IN ONE PLACE — the mechanism ALG-6
# itself prescribes for "true-circle content". Two classes qualify:
#   1. GENUINELY ROUND TARGETS. A wheel item, the wheel's ✕, the Move handle,
#      an aspect handle dot, the Region cancel, the wizard's close and its step
#      numbers are discs by design: round is the SHAPE, not an over-large
#      radius on a box.
#   2. (RETIRED 2026-08-11.) The `.ctl` squircle exemption is GONE because the
#      LAW moved instead: shown both renderings at real size, the owner kept
#      the 16px squircle and ordered the rule corrected — the squarish tier is
#      now 30% (in percent, never absolute px), so the signature buttons pass
#      on the rule's own arithmetic and no exemption exists to go stale.
RADIUS_EXEMPT_JS = """
  const RADIUS_EXEMPT = [
    ['.wheel-item', 'a radial item is a disc by design'],
    ['.wheel-x', 'the wheel cancel is a disc by design'],
    ['.asp-move', 'the Move handle is a disc by design'],
    ['.asp-h', 'an aspect handle is a dot by design'],
    ['.rg-cancel', 'the Region cancel is a disc by design'],
    ['#wiz-close', 'the wizard close is a disc by design'],
    ['.wiz-num', 'a step number is a disc by design'],
  ];
"""

# `root` is the element to judge. Returns [] when the frame law holds.
RADIUS_KIN_JS = RADIUS_EXEMPT_JS + """
  window.__radiusAndKin = (root) => {
    const bad = [];
    const px = (v) => parseFloat(v) || 0;
    // An SVG element's `className` is an SVGAnimatedString, not a string —
    // asking it for `.replace` throws, and this tooth walks EVERY element,
    // drawings included. The attribute is the one form both kinds answer.
    const cls = (el) => el.getAttribute('class') || '';
    const seen = [...root.querySelectorAll('*')].filter((el) => {
      const b = el.getBoundingClientRect();
      return b.width > 0 && b.height > 0;
    });
    // ── ALG-6, measured on the box the element really draws ────────────────
    for (const el of seen) {
      if (RADIUS_EXEMPT.some(([sel]) => el.matches(sel))) continue;
      const s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      // CLAMPED TO WHAT THE BROWSER ACTUALLY PAINTS. A declared `999px` is the
      // ordinary way to spell "pill" in CSS, and on a WIDE box it renders as
      // exactly half the height — a legitimate pill, not an egg. The law is
      // about the SHAPE the owner sees, so the number judged is the one that
      // reaches the screen; on a squarish box the same declaration clamps to
      // half the shorter side, which IS a circle, and is convicted.
      const raw = Math.max(px(s.borderTopLeftRadius), px(s.borderTopRightRadius),
                           px(s.borderBottomLeftRadius),
                           px(s.borderBottomRightRadius));
      const r = Math.min(raw, Math.min(b.width, b.height) / 2);
      if (r <= 0) continue;
      const ar = b.width / b.height;
      const allowed = ar >= 2 ? 0.5 * b.height
                    : ar >= 1.4 ? 0.3 * b.height
                    : 0.30 * Math.min(b.width, b.height);
      // ABSOLUTE CEILING ON LARGE SURFACES (owner screenshot v0.0.107, the
      // notify toast). The percent tiers exist for CHIPS — the owner's own
      // 58px/16px buttons that set the 30% squarish figure — and a percent
      // that is correct at chip size becomes a full circle's worth of pixels
      // once the same rule is applied to a box grown by dynamic content
      // (wrapped multi-line text, a long toast). "Larger than ~2x the
      // tier's design size" is measured directly against the chip reference
      // (58px corner button = the largest signature control the tier was
      // tuned against): past ~116px on its SHORTER side, the percent tier is
      // additionally capped at an absolute ceiling so growth alone can never
      // walk a surface into circle territory. Chips stay governed by percent
      // alone — the cap only ever tightens a LARGE element's allowance, never
      // a chip's.
      const LARGE_SIDE = 116;
      const ABS_CEILING = 28;
      const cap = Math.min(b.width, b.height) > LARGE_SIDE
                ? Math.min(allowed, ABS_CEILING) : allowed;
      if (r > cap + 0.5) {
        bad.push('radius ' + Math.round(r) + 'px on ' +
                 (cls(el) || el.tagName) + ' ' + Math.round(b.width) + 'x' +
                 Math.round(b.height) + ' (AR ' + ar.toFixed(2) + ') — the law ' +
                 'allows ' + Math.round(cap) + 'px at that shape: it is a ' +
                 'circle or an egg, not a rounded box');
      }
      // CLIP TOOTH (owner screenshot v0.0.107): even a radius the tier and
      // ceiling allow must not reach far enough into a corner to intersect
      // the element's OWN TEXT — that is what a rounded corner geometrically
      // eats (rules/GUI.md ALG-6's own words), checked directly against what
      // is actually rendered rather than assumed from padding. Every text
      // node's client rects must clear a 0.3*r inset from every edge the
      // radius rounds; this fires independently of whether the radius
      // itself was already convicted above, because a radius that passes
      // the tier can still clip content that sits too close to the edge.
      if (r > 0) {
        const inset = 0.3 * r;
        const lim = { l: b.left + inset, t: b.top + inset,
                      right: b.right - inset, bot: b.bottom - inset };
        for (const node of el.childNodes) {
          if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) continue;
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const tr of range.getClientRects()) {
            if (tr.width === 0 || tr.height === 0) continue;
            if (tr.left < lim.l - 0.5 || tr.right > lim.right + 0.5 ||
                tr.top < lim.t - 0.5 || tr.bottom > lim.bot + 0.5) {
              bad.push('text clips the rounded corner of ' +
                       (cls(el) || el.tagName) + ' — radius ' + Math.round(r) +
                       'px needs a ' + Math.round(inset) + 'px content inset ' +
                       'that this text does not have');
              break;
            }
          }
        }
      }
    }
    // ── ALG-5: kin are the SAME KIND under the SAME PARENT ─────────────────
    // Grouped by exact class signature with the state classes stripped: `sel`,
    // `active` and `sl` say WHICH one is chosen, and a chosen chip is still kin
    // to its unchosen sibling — that is the whole point of the rule. Without
    // stripping them the group of the moment would be a group of one and the
    // law would never fire, which is a check that cannot fail.
    const STATE = /\b(sel|active|held|dl|lay-drag|lay-drop|lay-gap|lay-full)\b/g;
    //
    // AND ONLY OVER CONTROLS. ALG-5's own subject is same-kind CONTROLS
    // (`UNIFORM_ROLES` in the Qt template is buttons and radio buttons); a
    // PARAGRAPH legitimately has the length it has, and convicting two
    // sentences of being different heights would be noise that trains everyone
    // to ignore this instrument.
    //
    // `.lay-item-main` is excluded by name: a list ROW's main button is
    // governed by `__kinRows` above, which knows the one legitimate reason two
    // of them differ — a row with no trailing buttons (the Desktop row, a
    // monitor row) spends the whole width on its name, which is correct.
    const CONTROLS = 'button, input, select, textarea, a[href]';
    const groups = new Map();
    for (const el of seen) {
      if (!el.parentElement) continue;
      if (!el.matches(CONTROLS) || el.matches('.lay-item-main')) continue;
      const kind = cls(el).replace(STATE, '').trim().replace(/\s+/g, ' ');
      if (!kind) continue;
      const key = kind + '@' + (cls(el.parentElement) || el.parentElement.tagName);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(el);
    }
    for (const [key, kin] of groups) {
      if (kin.length < 2) continue;
      const w = kin.map((e) => Math.round(e.getBoundingClientRect().width));
      const h = kin.map((e) => Math.round(e.getBoundingClientRect().height));
      if (Math.max(...w) - Math.min(...w) > 1) {
        bad.push('kin "' + key + '" differ in WIDTH: ' + w.join(' / ') +
                 ' — a control may never be sized by the length of its own text');
      }
      if (Math.max(...h) - Math.min(...h) > 1) {
        bad.push('kin "' + key + '" differ in HEIGHT: ' + h.join(' / '));
      }
    }
    return bad;
  };
"""
