"""
executor.registry
~~~~~~~~~~~~~~~~~
Loads will and death-record fixtures from JSON files, seals each as a
gate_core.SealedMandate, and answers queries needed by the measurer.
"""

from __future__ import annotations

import json

from gate_core import SealedMandate, seal_mandate


class ExecutorRegistry:
    """Stores sealed wills and death records and answers registry queries.

    Construction:
        Reads each path with json.load, calls gate_core.seal_mandate with
        domain="executor", and stores the results.  Wills are grouped by
        testator name and sorted by sealed_date ascending.  Death records
        are stored by deceased name.

    Args:
        will_paths:         List of file paths to will JSON fixtures.
        death_record_paths: List of file paths to death record JSON fixtures.
    """

    def __init__(
        self,
        will_paths: list[str],
        death_record_paths: list[str],
    ) -> None:
        # _wills: {testator: [SealedMandate, ...]} sorted by sealed_date asc
        self._wills: dict[str, list[SealedMandate]] = {}
        # _death_records: {deceased: SealedMandate}
        self._death_records: dict[str, SealedMandate] = {}

        for path in will_paths:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            sealed = seal_mandate(domain="executor", content=data)
            testator = data["testator"]
            self._wills.setdefault(testator, []).append(sealed)

        # Sort each testator's list by sealed_date ascending.
        # ISO-8601 YYYY-MM-DD strings sort lexicographically == chronologically.
        for testator in self._wills:
            self._wills[testator].sort(key=lambda sm: sm.content["sealed_date"])

        for path in death_record_paths:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            sealed = seal_mandate(domain="executor", content=data)
            deceased = data["deceased"]
            self._death_records[deceased] = sealed

    # ── Queries ───────────────────────────────────────────────────────────

    def latest_will(self, testator: str) -> SealedMandate | None:
        """Return the SealedMandate with the greatest sealed_date for testator.

        Returns None if no will exists for testator.
        """
        wills = self._wills.get(testator)
        if not wills:
            return None
        return wills[-1]

    def all_wills(self, testator: str) -> list[SealedMandate]:
        """Return all sealed wills for testator, oldest first.

        Returns an empty list if no wills exist.
        """
        return list(self._wills.get(testator, []))

    def will_by_seal(self, seal: str) -> SealedMandate | None:
        """Return the SealedMandate whose seal field equals the given hex string.

        Returns None if no match is found.  Used by the measurer to locate
        the will referenced by will_ref in the claim payload.
        """
        for wills in self._wills.values():
            for sm in wills:
                if sm.seal == seal:
                    return sm
        return None

    def death_record(self, name: str) -> SealedMandate | None:
        """Return the sealed death record for name, or None.

        Never raises; a missing record returns None.
        """
        return self._death_records.get(name)
