"""
citation_gate.sources
~~~~~~~~~~~~~~~~~~~~~
Loads the three source record fixtures from JSON files, seals each as a
``gate_core.SealedMandate``, derives a flat fact table from each, and answers
registry queries needed by the measurer.

Fixture paths are injected at construction time; no paths are hard-coded here.
"""

from __future__ import annotations

import json

from gate_core import SealedMandate, seal_mandate


# ---------------------------------------------------------------------------
# Module-private extractor functions
# ---------------------------------------------------------------------------

def _extract_death_record_facts(data: dict) -> dict[str, str]:
    """Return the flat fact table for a death record fixture."""
    return {
        "deceased":      data["deceased"],
        "date_of_death": data["date_of_death"],
        "place":         data["place"],
        "registrar":     data["registrar"],
    }


def _extract_family_record_facts(data: dict) -> dict[str, str]:
    """Return the flat fact table for a family record fixture."""
    return {
        "person":     data["person"],
        "born":       data["born"],
        "birthplace": data["birthplace"],
        "occupation": data["occupation"],
        "residence":  data["residence"],
    }


def _extract_will_facts(data: dict) -> dict[str, str]:
    """Return the flat fact table for a will fixture.

    One ``bequest.<Sign>.item`` and one ``bequest.<Sign>.beneficiary`` key is
    produced per entry in ``data["bequests"]``.  Signs that have no entry in
    the bequests list (empty signs) produce no keys.
    """
    facts: dict[str, str] = {}
    for bequest in data.get("bequests", []):
        sign = bequest["sign"]
        facts[f"bequest.{sign}.item"]        = bequest["item"]
        facts[f"bequest.{sign}.beneficiary"] = bequest["beneficiary"]
    return facts


# ---------------------------------------------------------------------------
# SourceRegistry
# ---------------------------------------------------------------------------

class SourceRegistry:
    """Holds the three sealed source records for the citation gate desk.

    Args:
        death_record_path:  Path to the death record JSON fixture.
        will_path:          Path to the will JSON fixture (e.g. will_2024.json).
        family_record_path: Path to the family record JSON fixture.
    """

    def __init__(
        self,
        death_record_path: str,
        will_path: str,
        family_record_path: str,
    ) -> None:
        with open(death_record_path, "r", encoding="utf-8") as fh:
            death_data: dict = json.load(fh)
        with open(will_path, "r", encoding="utf-8") as fh:
            will_data: dict = json.load(fh)
        with open(family_record_path, "r", encoding="utf-8") as fh:
            family_data: dict = json.load(fh)

        self._sources: dict[str, SealedMandate] = {
            "death_record":  seal_mandate("citation", death_data),
            "will_2024":     seal_mandate("citation", will_data),
            "family_record": seal_mandate("citation", family_data),
        }
        self._fact_tables: dict[str, dict[str, str]] = {
            "death_record":  _extract_death_record_facts(death_data),
            "will_2024":     _extract_will_facts(will_data),
            "family_record": _extract_family_record_facts(family_data),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def source(self, source_id: str) -> SealedMandate | None:
        """Return the SealedMandate for *source_id*, or ``None`` if not registered."""
        return self._sources.get(source_id)

    def fact_table(self, source_id: str) -> dict[str, str] | None:
        """Return the flat fact table for *source_id*, or ``None`` if not registered."""
        return self._fact_tables.get(source_id)

    def known_source_ids(self) -> frozenset[str]:
        """Return the frozenset of registered source id strings."""
        return frozenset(self._sources.keys())
