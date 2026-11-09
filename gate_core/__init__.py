"""
gate_core
~~~~~~~~~
The Skeleton Crew gate core library.

Exports all public names so callers can write::

    from gate_core import Claim, seal_mandate, verify_mandate, ...
"""

from gate_core.claim import Claim

from gate_core.mandate import (
    MandateTamperError,
    SealedMandate,
    seal_mandate,
    verify_mandate,
)

from gate_core.measure import MeasurementProtocol, MeasurementResult

from gate_core.verdict import (
    Pass,
    Refused,
    UnknownRefusalError,
    Verdict,
    is_valid_refusal,
    make_pass,
    make_refused,
    register_refusal,
    unmeasured_refusal,
)

from gate_core.receipt import (
    Receipt,
    ReplayResult,
    append_receipt,
    load_chain,
    receipt_from_dict,
    receipt_to_dict,
    save_chain,
    verify_chain,
)

from gate_core.gate import adjudicate

__all__ = [
    # claim
    "Claim",
    # mandate
    "MandateTamperError",
    "SealedMandate",
    "seal_mandate",
    "verify_mandate",
    # measure
    "MeasurementProtocol",
    "MeasurementResult",
    # verdict
    "Pass",
    "Refused",
    "UnknownRefusalError",
    "Verdict",
    "is_valid_refusal",
    "make_pass",
    "make_refused",
    "register_refusal",
    "unmeasured_refusal",
    # receipt
    "Receipt",
    "ReplayResult",
    "append_receipt",
    "load_chain",
    "receipt_from_dict",
    "receipt_to_dict",
    "save_chain",
    "verify_chain",
    # gate
    "adjudicate",
]
