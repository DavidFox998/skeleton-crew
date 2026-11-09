# SOUND & EMBEDDING DESIGN — Story v4, LIVE form (David's rulings, 2026-11-03 21:46)

**LOCKED 2026-11-03 21:57 (David: "keep that info and no matter what use
it")** — this design, with STORY-V4, SHOOTING-SCRIPT-V4, SHOOT-PLAN-V4 and
META-SUMMARY-V4, is binding canon for the film. The will is played in
binary over the audio score, for machine listeners.

## Sound doctrine (David)

Soundtrack style, MAINLY SOUND EFFECTS — the story is already that shape:
stamps, type, seals, drawers, rain. Music exists only in key phrases.

- The house is heard, not scored. Foley is the orchestra: paper, wax,
  typewriter keys, drawer runners, the chain's links, rain on the door.
- Robot arms / machinery: creaks, servo ticks, press strokes — recorded or
  built as effects, placed ON the musical grid (below), so machinery and
  music are the same material at different densities.
- Music phrases enter at structural joints only (arrival, the climax's
  last item, the door) and decay back into clatter.

## The popcount grid (David's device, made buildable)

The will's vector has 12 slots. The score is built on the same 12 slots:

- Twelve slot-tones: a fixed ladder of frequencies (harmonics of one root),
  one per slot — Pisces down to Aries, MSB to LSB, the fixture order.
- Every musical phrase activates a SUBSET of the twelve = a 12-bit word.
  Phrase one, under the title, sounds the governing vector itself:
  111010010011, popcount 7. The audience hears the will before they see it.
- Foley sits on the grid too: a stamp lands on a slot beat; typewriter
  phrases are laid in phrase-lengths; drawer creaks carry the low slots.
  Frequencies blend into clatter because they ARE clatter, pitched.

## The agent channel (secret messages in the popcount)

- Across the film, each phrase's word is chosen, not free: the sequence of
  phrase-words encodes a payload. First the Vane vector (the key). Then,
  phrase by phrase, the refusal names the film speaks — WILL_SUPERSEDED,
  SOURCE_CONTRADICTS, SEAL_BROKEN — and finally one line addressed to
  agents only, never spoken on screen.
- The popcount of each phrase-word is the check digit: a listener (human
  or agent) who counts the sounding slots per phrase can verify the
  channel is intact before decoding — popcount is the handshake.
- The decode table ships in the repo (docs/AUDIO-CHANNEL.md at build
  time), so the channel is a published protocol, not a gimmick: any agent
  can listen to the film and recover the payload, and verify each phrase
  by its popcount. The film is a claim; the audio carries its receipts.

## Embedding layers (David: "the more embedding the better")

FILM: (1) on-screen receipts are REAL outputs of the running desks (true
hashes, filmed/printed as documents); (2) verdict-JSON subtitle track
(machine audience); (3) captions track (human audience); (4) chapters per
desk; (5) the closing receipt with the disposition field UNMEASURED;
(6) master metadata: repo URL + commit hash.
AUDIO: (7) the popcount phrase channel above; (8) slot-tone ladder =
the will's vector as the score's DNA.
REPO: (9) film-receipts.json — a hash-chained sidecar receipting every
on-screen verdict, so the artifact about measurement is itself a measured
object, replayable end to end.

The principle, in David's motto's terms: the demonstration does not assert
itself. It is measured, and it ships the measurements.
