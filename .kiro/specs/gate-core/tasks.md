# Implementation Tasks — Gate Core Library

Derived from design.md. Each task corresponds to one module, one test file, or one documentation artefact. Work top-to-bottom; later tasks depend on earlier ones.

---

- [x] 1. Implement `gate_core/claim.py` — frozen `Claim` dataclass with `domain`, `claim_type`, `payload`; validate non-blank fields and JSON-serialisable payload at construction.
- [x] 2. Implement `gate_core/mandate.py` — frozen `SealedMandate` dataclass; `seal_mandate()` and `verify_mandate()` functions; `MandateTamperError` exception; canonical-JSON helper.
- [x] 3. Implement `gate_core/measure.py` — frozen `MeasurementResult` dataclass with `observations` and `passed`; `MeasurementProtocol` structural protocol.
- [x] 4. Implement `gate_core/verdict.py` — frozen `Pass` and `Refused` dataclasses; `Verdict` type alias; `_VOCABULARIES` registry; `register_refusal()`, `is_valid_refusal()`, `make_pass()`, `make_refused()`, `unmeasured_refusal()`; `UnknownRefusalError` exception; `unmeasured` reserved for every domain.
- [x] 5. Implement `gate_core/receipt.py` — frozen `Receipt` dataclass; `append_receipt()` chain-append helper; frozen `ReplayResult` dataclass; `verify_chain()` replay verifier; `receipt_to_dict()`, `receipt_from_dict()`, `save_chain()`, `load_chain()` I/O helpers.
- [x] 6. Implement `gate_core/__init__.py` — export all public names from the five modules so callers can `from gate_core import ...`.
- [x] 7. Write `tests/test_gate_core.py` — unittest suite covering: mandate seal/verify round-trip; tampered mandate detection; PASS verdict for a satisfying claim; REFUSED verdict for a violating claim; unmeasured claim refused as `unmeasured`; unknown refusal name raises `UnknownRefusalError`; receipt hash chain integrity; replay success on clean chain; replay detects tampered receipt; replay detects broken chain link.
- [x] 8. Run `python3 -m unittest discover -s tests -v` and fix all failures until the suite passes green.
- [x] 9. Write `gate_core/README.md` — one-page developer reference: module map, canonical-JSON rule, error taxonomy, and a minimal end-to-end usage example.
- [x] 10. Implement `gate_core/gate.py` — `adjudicate(claim, sealed_mandate, measurer, chain)` composition function; export from `gate_core/__init__.py`; add tests to `tests/test_gate_core.py` covering: end-to-end PASS with chained receipt; end-to-end refusal with domain refusal name; measurer exception → `Refused('unmeasured')` with receipt appended; tampered mandate → `MandateTamperError` with nothing appended.
