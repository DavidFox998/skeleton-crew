# Vault Desk

The third desk of Skeleton Crew. At intake the house seals a client's whole
estate file (will, death record, family record, inventory) as one bundle under
a single chain certificate. Before the file may leave, a `bundle_release`
claim is re-measured against that lock record.

- **Lock record** (`vault/lock.py`): a `gate_core.SealedMandate`, domain `vault`, holding a path→SHA-256 table in canonical order and one certificate (hash of the table).
- **Measurer** (`vault/measurer.py`): lock record first — if its seal or certificate does not recompute, `MandateTamperError` (hard tamper, nothing appended). Then the census is compared; first difference named: `file_changed`, then `file_missing`, then `file_added` (path order within each).
- **Scenarios** B1–B6 (`vault/scenarios.py`), tests in `tests/test_vault.py`.

```python
from vault import lock_bundle, present_bundle, VaultMeasurer
from gate_core import adjudicate
lock = lock_bundle("vane-estate-file", "/path/to/bundle")
chain = []
verdict, receipt = adjudicate(present_bundle("vane-estate-file", "/path/to/bundle"), lock, VaultMeasurer(), chain)
```

Method disclosure: the bundle-certificate method is the author's own prior work (Appendix G); all code here is written fresh, standard library only. No web skin yet.
