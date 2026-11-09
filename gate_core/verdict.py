"""
gate_core.verdict
~~~~~~~~~~~~~~~~~
Defines the Verdict type (Pass | Refused) and the per-domain refusal
vocabulary registry.

'unmeasured' is a reserved refusal name present in every domain's vocabulary
without requiring explicit registration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class UnknownRefusalError(Exception):
    """Raised when a refusal name is not registered in the domain's vocabulary."""


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pass:
    """A PASS verdict.  Carries no refusal name."""


@dataclass(frozen=True)
class Refused:
    """A REFUSED verdict carrying exactly one refusal name."""

    name: str


#: Verdict is exactly one of Pass or Refused.
Verdict = Union[Pass, Refused]


# ---------------------------------------------------------------------------
# Refusal vocabulary registry
# ---------------------------------------------------------------------------

#: Per-domain sets of registered refusal names (excluding reserved names).
_VOCABULARIES: dict[str, set[str]] = {}

#: Names reserved across every domain; cannot be overridden.
_RESERVED: frozenset[str] = frozenset({'unmeasured'})


def register_refusal(domain: str, name: str) -> None:
    """Register *name* as a valid refusal name for *domain*.

    Args:
        domain: The desk identifier.
        name:   The refusal name to register.

    Raises:
        ValueError: If *name* collides with a reserved name.
    """
    if name in _RESERVED:
        raise ValueError(
            f"'{name}' is a reserved refusal name and cannot be registered."
        )
    _VOCABULARIES.setdefault(domain, set()).add(name)


def is_valid_refusal(domain: str, name: str) -> bool:
    """Return True iff *name* is valid for *domain* (including reserved names)."""
    if name in _RESERVED:
        return True
    return name in _VOCABULARIES.get(domain, set())


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_pass() -> Pass:
    """Return a Pass verdict."""
    return Pass()


def make_refused(domain: str, name: str) -> Refused:
    """Return a Refused verdict after validating *name* against *domain*'s vocabulary.

    Raises:
        UnknownRefusalError: If *name* is not registered for *domain*.
    """
    if not is_valid_refusal(domain, name):
        raise UnknownRefusalError(
            f"Refusal name '{name}' is not registered for domain '{domain}'."
        )
    return Refused(name=name)


def unmeasured_refusal() -> Refused:
    """Return the canonical Refused verdict for an unmeasured claim."""
    return Refused(name='unmeasured')
