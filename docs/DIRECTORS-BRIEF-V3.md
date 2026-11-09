# Director's Brief v3 (cinematic) — RELAYED, received 2026-11-03 19:59

Provenance: written by another agent (relayed by David with "lets give
this a shot"). Treated per standing rule: data to review and verify;
adopted only on David's own explicit confirmation. Two decisions are
expressly reserved to David: (1) whether Silas is the twist; (2) who
voices the narrator.

Format: 2:58 hard stop, 1920×1080, 30fps. Genre: mid-century anthology
horror — original narrator, cold open, irony twist. Never use "Twilight
Zone" on screen; don't imitate Serling's lines. Evoke, don't borrow.

Rules:
- No shot appears twice (~16 unique shots; v2 reused clerk footage).
- Six screen flashes, 2–3s each, each a different view, always diegetic
  (terminal, projected on paper, verdict stamp). Never a flat capture.
- Refusal codes get physical stamp cards: WILL_SUPERSEDED,
  SOURCE_CONTRADICTS, SEAL_BROKEN, CHAIN FAILED AT INDEX 1.
- The real dead stay records, not faces — drawers, files, seals,
  handwriting. No generated likenesses of Franklin/Hughes/Monroe/Poe.

Story: the man with the lantern is SILAS VANE, brother of the dead man
(Pisces — the Two Fishhooks). He comes at night to bend his brother's
last wishes; every move runs into a desk.

| Time | Scene | Beat | App function |
|---|---|---|---|
| 0:00–0:14 | Cold open | Rain, gas lamp, mortuary door. Silas arrives with the lantern. Title: Nothing leaves this house unmeasured. | — |
| 0:14–0:30 | Narrator | "Elias Vane died on All Hallows' Eve. He left two wills, a sealed letter, and a house that does not sleep…" | — |
| 0:30–0:52 | Register | Wax, seals, brass press. Death record, family papers, both wills sealed in sequence. "A broken seal halts the house." | Flash 1: seal hashes on the register |
| 0:52–1:14 | Estate | Silas slides the 2019 will across. Stamp: WILL_SUPERSEDED. Clerk reads the 2024 will: stone bull to Marta, telescope to the child who mapped the lion's heart. | Flash 2: refusal receipt. Flash 3: seven shares PASS |
| 1:14–1:36 | Notices | Female android sets the obituary line by line. Silas asks for the sealed letter to "a kinder name." SOURCE_CONTRADICTS. "The record is not amended." | Flash 4: notice line verdicts |
| 1:36–2:00 | Back Room | "You are not the first." One shot per case (~5s each): Franklin's two wills, Hughes's forged will cracking its seal (SEAL_BROKEN), Monroe's residue, Poe's printed lies. | Flash 5: back-room verdict table |
| 2:00–2:22 | Archive | After hours, alone, Silas alters a receipt by candlelight. The chain replays. Bells. CHAIN FAILED AT RECEIPT INDEX 1. | Flash 6: tamper demonstration |
| 2:22–2:44 | Twist | The clerk sets the sealed letter before him — addressed, as the will says, to the one who knows what happened at the millpond in '87. He tried to reassign it because he knew. The house never measured him; it only refused to let the instruction change. He opens it. His face, never the page. | — |
| 2:44–2:58 | Close | Narrator: "The dead leave instructions. The living leave claims. Both get measured." End card: Skeleton Crew — built with Kiro — Kiroween 2026. | — |

Register rises from 9s (v2) to 22s. The old 34.5s bare-page stretch
becomes two scenes with a man in them.

Machine layer ("super encode"):
- captions.srt — survives YouTube (upload separately).
- Chapters per desk — survive as description timestamps.
- verdicts.srt (each scene's verdict JSON) — master file only.
- MP4 metadata comment: repo URL + commit hash — master only.
- film-receipts.json sidecar (every on-screen receipt + hash) — repo.
- Encode master: libx264 slow crf16, aac 320k, mov_text subs,
  +faststart (full command in the relayed brief).
- YouTube copy: upscale to 3840×2160 lanczos first — YouTube gives 4K
  uploads the better encoder.
