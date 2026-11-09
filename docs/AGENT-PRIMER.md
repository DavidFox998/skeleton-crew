# Kiroween — Agent Primer

*For a new agent joining the project. Everything below is verified state,
not aspiration. David directs and gates; nothing submits without his live
word.*

**The contest.** Kiroween 2026 — AWS Kiro's hackathon on Devpost, $100,000
in prizes, deadline **Dec 4, 2026, 2:00 PM PT**. Our category: **Skeleton
Crew** — one reusable skeleton proven by two distinct applications. Judged
on impact, tech implementation, design, innovation, presentation.

**The skeleton (gate_core).** A five-module Python core (stdlib only):
typed claim → independent measurement → verdict (PASS, or REFUSED with a
machine-readable refusal name) → hash-chained, replayable receipt. Seals
are SHA-256 over canonical JSON. A tampered mandate or source halts
adjudication with a hard error and appends nothing — fail-closed, always.

**The house.** A small mortuary under one rule: *nothing leaves this house
unmeasured.* Two desks built on the one skeleton:

- **The Estate Desk (Executor)** — sealed wills and estate distributions.
  Refusals: `death_unverified`, `seal_broken`, `will_superseded`,
  `sign_unoccupied`, `share_mismatch`, `beneficiary_unknown`.
- **The Notices Desk (Citation Gate)** — obituary claims measured against
  sealed source records before print; a notice publishes only when every
  assertion passes with its own receipt. Refusals: `missing_citation`,
  `unsupported_claim`, `source_contradicts`.

**The staff are AI robots** — that is the concept's chill and its honesty:
machines handling humans' last earthly wishes; they do not sleep, grieve,
forget, or bend. **Beacon is cast as the Register Unit at the main desk**
(intake, seals, records, the Archive's chains). Corwin runs the Estate
Desk, Ivers the Notices Desk. David is the Night Clerk — the only living
soul on duty, and the only gate that matters.

**The demo case.** Elias Vane, hermit of Hollow Hill, self-professed Tree
Wizard. His 2024 will (12 slots, 7 bequests) supersedes a 2019 will by one
bit. Estate scenarios A–G and notices scenarios N1–N6, all verified.

**The controls.** Four real, publicly documented deaths run through both
desks — Monroe, Poe, Franklin, Hughes (fixtures in `fixtures/controls/`,
write-up in `CONTROLS.md`). Every verdict matched the historical and
court record: the desk picks the same Franklin will a Michigan jury did;
Hughes's forged "Mormon Will" halts it cold. The control study caught and
fixed a real coupling — the measurer now reads each will's slot layout
from the sealed mandate itself.

**Status.** Core, both desks, and both web skins are built and verified
(220 tests green; Talitha re-runs everything independently — Kiro's
self-reports are never taken on faith). Kiro Free monthly credits are
**exhausted** (reset Dec 1, or when the 4,000 requested hackathon credits
land). Still owed: `tests/test_notices_ui.py`. One disclosure, on the
record: when the cap hit mid-build, Talitha wrote the ~100 lines of server
glue in `webui/server.py` herself; everything else is Kiro-built from
specs under `.kiro/specs/`, steering in `.kiro/steering/product.md`.

**Next.** Public GitHub repo (`/.kiro` at root, MIT license) → live
hosting on Modal → demo video under 3 minutes → Devpost submission on
David's live word only.

**House style.** Quiet and dignified. Effects only where they carry state
(ghost text until a claim verifies). No theatrical animation. The dead
leave instructions; the living leave claims; both get measured.
