"""
citation_gate.publish
~~~~~~~~~~~~~~~~~~~~~
PublishChecker — inspects the desk's receipt chain for a draft and returns a
publish or refuse decision.

The check is a pure function: it does not call ``adjudicate()``, it does not
mutate the chain, and it has no side effects.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from gate_core import Receipt


def _canonical_json(obj: dict) -> str:
    """Return canonical JSON: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _claim_hash(claim_dict: dict) -> str:
    """Return the SHA-256 hex digest of the canonical JSON of *claim_dict*."""
    return hashlib.sha256(_canonical_json(claim_dict).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublishDecision:
    """The outcome of a publish check.

    Attributes:
        publishable:  True iff every assertion in the draft has a PASS receipt.
        receipt_ids:  List of ``own_hash`` values in assertion order; ``None``
                      if not publishable.
        refusal_name: Refusal name of the first non-passing assertion; ``None``
                      if publishable.
    """

    publishable: bool
    receipt_ids: list[str] | None
    refusal_name: str | None


def check_publish(
    draft_id: str,
    assertion_claim_hashes: list[str],
    chain: list[Receipt],
) -> PublishDecision:
    """Inspect *chain* to determine whether the draft identified by *draft_id*
    is ready for publication.

    Args:
        draft_id:               Logical identifier for the draft (used for
                                labelling only; not stored in receipts).
        assertion_claim_hashes: Ordered list of canonical-JSON SHA-256 hex
                                hashes of each assertion's Claim dict, in
                                draft assertion order.  Used to locate each
                                assertion's receipt in the chain.
        chain:                  The desk's receipt chain (list of Receipt
                                objects).

    Returns:
        A ``PublishDecision``.  ``publishable=True`` means every assertion in
        the draft has a PASS receipt in the chain.  ``publishable=False`` means
        at least one assertion is refused or unadjudicated.
    """
    # A draft with no assertions is not publishable.
    if not assertion_claim_hashes:
        return PublishDecision(
            publishable=False,
            receipt_ids=None,
            refusal_name="missing_citation",
        )

    # Build an index of receipts keyed by the hash of their stored claim dict.
    receipt_by_claim_hash: dict[str, Receipt] = {
        _claim_hash(r.claim): r
        for r in chain
    }

    pass_ids: list[str] = []

    for claim_hash in assertion_claim_hashes:
        receipt = receipt_by_claim_hash.get(claim_hash)
        if receipt is None:
            # Assertion was never adjudicated.
            return PublishDecision(
                publishable=False,
                receipt_ids=None,
                refusal_name="unmeasured",
            )
        if receipt.verdict["type"] != "pass":
            refusal = receipt.verdict.get("name", "unmeasured")
            return PublishDecision(
                publishable=False,
                receipt_ids=None,
                refusal_name=refusal,
            )
        pass_ids.append(receipt.own_hash)

    return PublishDecision(
        publishable=True,
        receipt_ids=pass_ids,
        refusal_name=None,
    )


# Alias for callers that prefer the class-style name from the design doc.
PublishChecker = check_publish
