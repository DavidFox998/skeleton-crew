# The Vault — plan (David's proposal 2026-11-07; name RATIFIED by David 2026-11-07: The Vault)

Put the Bundle Lock tech (David's Appendix G chain certificate, integrated
with the trust harness on zerobeacon 2026-11-05) into Skeleton Crew as a
THIRD application of the gate skeleton.

## What it is in house language

At intake the house seals the whole estate file — will, death record,
family record, inventory — as ONE bundle under a single chain certificate.
When anyone asks for the file to leave the house, this desk re-measures
the bundle against its lock record before release. A changed, added, or
missing paper is refused BY NAME. Law one, applied to the file itself:
nothing leaves this house unmeasured — not even the records.

## Mechanics (fresh implementation, in Kiro, on gate_core)

- Sealed mandate = the lock record: per-file SHA-256 manifest in canonical
  order (path:hash table), one bundle certificate = hash of the table.
- Claim: `bundle_release`, payload = the presented bundle manifest.
- Measurer: record self-check first (a lock record that does not recompute
  to its own certificate is a hard tamper, same as the other desks);
  then compare manifests and name the first difference.
- Refusals: `file_changed`, `file_missing`, `file_added`; core `unmeasured`
  if the measurer cannot run. PASS issues the chained receipt; the bundle
  may leave.
- The bundle's contents are the other desks' own sources — the desks over-
  lap on purpose: the whole house's papers, sealed as one object.

## Scenarios (mirroring the proven Bundle Lock demo)

B1 untouched bundle -> PASS (lock holds, receipt issued)
B2 one paper altered (an inventory figure) -> file_changed, naming it
B3 a stray paper added -> file_added, naming it
B4 a paper removed (the death record) -> file_missing, naming it
B5 bundle restored -> PASS with the original certificate
B6 lock record itself altered -> hard tamper, nothing appended

## Disclosure (standing rule, same as will_seal)

The METHOD is David's prior work (Appendix G chain certificate; a
production version shipped in the ZeroBeacon trust harness 2026-11-05).
The Kiroween code is written fresh inside Kiro during the window, on the
skeleton, and the write-up discloses the method as prior work. No
zerobeacon code or API is imported — same boundary as the other desks.

## Cost / schedule box

One Kiro spec + implementation block when the 4,000 credits land (after
the notices-ui debt, which is owed first). Talitha verifies: full suite
re-run, tamper probes, scenario table. Web skin is STRETCH ONLY, after
the film — the film stays two desks and does not change.
