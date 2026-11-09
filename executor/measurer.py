"""
executor.measurer
~~~~~~~~~~~~~~~~~
ExecutorMeasurer — implements gate_core.MeasurementProtocol.

Performs all precedence checks in the order defined by the requirements and
returns a MeasurementResult.  Has no knowledge of verdicts; it only observes
and reports.

The measurer never raises intentionally.  If a key is missing from a fixture,
the resulting KeyError propagates to adjudicate(), which catches it and issues
REFUSED('unmeasured').
"""

from __future__ import annotations

from gate_core import Claim, MeasurementResult, SealedMandate, verify_mandate

from executor.registry import ExecutorRegistry

# ---------------------------------------------------------------------------
# Canonical zodiac sign sequence (MSB → LSB, 12 signs)
# Legacy fallback only — used when a mandate's content does not include a
# 'slots' field.  New mandates carry their slot order inside the sealed
# content so the layout is itself under seal.
# Verified against both Elias Vane fixture files:
#   2024 vector "111010010011":  1=Pisces, 1=Aquarius, 1=Capricorn, 0=Sagittarius,
#                                1=Scorpio, 0=Cancer, 0=Gemini, 1=Leo,
#                                0=Virgo, 0=Libra, 1=Taurus, 1=Aries  (7 bequests)
#   2019 vector "111000010011":  1=Pisces, 1=Aquarius, 1=Capricorn, 0=Sagittarius,
#                                0=Scorpio, 0=Cancer, 0=Gemini, 1=Leo,
#                                0=Virgo, 0=Libra, 1=Taurus, 1=Aries  (6 bequests)
# ---------------------------------------------------------------------------
ZODIAC_MSB_TO_LSB: list[str] = [
    "Pisces",       # bit 0 (MSB)
    "Aquarius",     # bit 1
    "Capricorn",    # bit 2
    "Sagittarius",  # bit 3
    "Scorpio",      # bit 4
    "Cancer",       # bit 5
    "Gemini",       # bit 6
    "Leo",          # bit 7
    "Virgo",        # bit 8
    "Libra",        # bit 9
    "Taurus",       # bit 10
    "Aries",        # bit 11 (LSB)
]


class ExecutorMeasurer:
    """Measures an estate_distribution claim against a sealed will.

    Args:
        registry: An ExecutorRegistry instance used to look up death records
                  and other wills for the same testator.
    """

    def __init__(self, registry: ExecutorRegistry) -> None:
        self._registry = registry

    def measure(
        self,
        claim: Claim,
        mandate: SealedMandate,
    ) -> MeasurementResult:
        """Measure claim against mandate and return a MeasurementResult.

        The mandate is the SealedMandate for the specific will being adjudicated
        (the one whose seal matches claim.payload["will_ref"]).

        Precedence (first failing check wins):
            1. Death record check      → death_unverified
            2. Will seal check         → seal_broken
            3. Supersession check      → will_superseded
            4. Per-distribution checks → sign_unoccupied | share_mismatch |
                                         beneficiary_unknown
        """
        # ── 1. Death record check ─────────────────────────────────────────
        testator = mandate.content["testator"]
        dr = self._registry.death_record(testator)
        if dr is None or not verify_mandate(dr):
            return MeasurementResult(
                observations={
                    "refusal_name": "death_unverified",
                    "testator": testator,
                    "death_record_present": dr is not None,
                },
                passed=False,
            )

        # ── 2. Will seal check ────────────────────────────────────────────
        if not verify_mandate(mandate):
            return MeasurementResult(
                observations={
                    "refusal_name": "seal_broken",
                    "will_seal": mandate.seal,
                },
                passed=False,
            )

        # ── 3. Supersession check ─────────────────────────────────────────
        latest = self._registry.latest_will(testator)
        if latest is not None and latest.seal != mandate.seal:
            return MeasurementResult(
                observations={
                    "refusal_name": "will_superseded",
                    "submitted_seal": mandate.seal,
                    "governing_seal": latest.seal,
                    "governing_sealed_date": latest.content["sealed_date"],
                },
                passed=False,
            )

        # ── 4. Per-distribution checks ────────────────────────────────────
        vector: str = mandate.content["vector"]
        stated_popcount: int = mandate.content["stated_popcount"]
        actual_popcount: int = vector.count("1")

        # Derive slot list from the sealed mandate when present; fall back to
        # the legacy zodiac constant for mandates that pre-date the slots field.
        slots: list[str] = mandate.content.get("slots", ZODIAC_MSB_TO_LSB)

        # Build sign → bit_char mapping from the slot list.
        if len(slots) != len(vector):
            return MeasurementResult(
                observations={
                    "refusal_name": "seal_broken",
                    "reason": "vector_length_mismatch",
                    "expected_length": len(slots),
                    "actual_length": len(vector),
                },
                passed=False,
            )
        sign_to_bit: dict[str, str] = {
            sign: bit for sign, bit in zip(slots, vector)
        }

        # 4a. Stated popcount vs actual popcount.
        if stated_popcount != actual_popcount:
            return MeasurementResult(
                observations={
                    "refusal_name": "share_mismatch",
                    "reason": "stated_popcount_mismatch",
                    "stated": stated_popcount,
                    "actual": actual_popcount,
                },
                passed=False,
            )

        # Build bequest map: {sign: bequest_dict}.
        bequest_map: dict[str, dict] = {
            b["sign"]: b for b in mandate.content["bequests"]
        }

        distributions: list[dict] = claim.payload["distributions"]

        # 4b. Distribution count vs actual popcount.
        if len(distributions) != actual_popcount:
            return MeasurementResult(
                observations={
                    "refusal_name": "share_mismatch",
                    "reason": "distribution_count_mismatch",
                    "expected": actual_popcount,
                    "received": len(distributions),
                },
                passed=False,
            )

        # 4c. Per-entry checks.
        seen_signs: set[str] = set()
        for entry in distributions:
            sign: str = entry["sign"]

            # i. Sign occupied?
            if sign_to_bit.get(sign) != "1":
                return MeasurementResult(
                    observations={
                        "refusal_name": "sign_unoccupied",
                        "sign": sign,
                    },
                    passed=False,
                )

            # ii. Duplicate sign?
            if sign in seen_signs:
                return MeasurementResult(
                    observations={
                        "refusal_name": "share_mismatch",
                        "reason": "duplicate_sign",
                        "sign": sign,
                    },
                    passed=False,
                )

            will_bequest = bequest_map[sign]

            # iii. Item match?
            if entry["item"] != will_bequest["item"]:
                return MeasurementResult(
                    observations={
                        "refusal_name": "share_mismatch",
                        "reason": "item_mismatch",
                        "sign": sign,
                        "expected_item": will_bequest["item"],
                        "received_item": entry["item"],
                    },
                    passed=False,
                )

            # iv. Beneficiary match?
            if entry["beneficiary"] != will_bequest["beneficiary"]:
                return MeasurementResult(
                    observations={
                        "refusal_name": "beneficiary_unknown",
                        "sign": sign,
                        "expected_beneficiary": will_bequest["beneficiary"],
                        "received_beneficiary": entry["beneficiary"],
                    },
                    passed=False,
                )

            seen_signs.add(sign)

        # ── 5. All checks passed ──────────────────────────────────────────
        return MeasurementResult(
            observations={
                "signs_verified": [e["sign"] for e in distributions],
                "items_verified": [e["item"] for e in distributions],
                "testator": testator,
                "will_seal": mandate.seal,
                "death_record_seal": dr.seal,
            },
            passed=True,
        )
