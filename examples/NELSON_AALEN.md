# Nelson–Aalen cumulative hazard point estimate: experimental source preview

This experimental in-process source preview is not a complete reliability workbench or a full export of the original nonparametric service. It reuses event times and risk-set rows from the published Kaplan–Meier module, whose bytes remain unchanged from e353434, and accumulates `d/n` at each failure time; it **does not transform Kaplan–Meier survival into cumulative hazard**. Tied failures are grouped as `d/n`, and units censored at the same time remain in the risk set for the event; other tie conventions may differ.

The 2026-11-06 integration was reviewed against public baseline `87513889038fb31a446e311586cc6cf33abe5218`, preserving its later CSV, input-validation and report changes. In an isolated source copy, this is an invented example:

```python
from fractions import Fraction
from app.services.nelson_aalen import nelson_aalen_point
answer = nelson_aalen_point([1, 2], [2, 3], time_unit="hour")
assert abs(answer["rows"][-1]["cumulative_hazard"] - float(Fraction(7, 12))) < 1e-15
```

Failures and right-censored observations must be lists or tuples with at most 10,000 observations, a specified unit (`second`/`minute`/`hour`/`day`/`year`), positive finite times and at least one failure. **Rejecting zero times and all-censored data is a preview quality gate, not a claim that those cases are universally invalid statistics.** Units are not converted. Inexact integers, booleans and non-finite inputs are rejected; already-rounded binary floating-point inputs cannot be recovered. Output is cumulative hazard point estimates at event times, risk sets, counts and limitations; no survival transform, confidence interval, delayed entry, extrapolation, chart or field forecast is included.

One observation per unit and independent non-informative right censoring are assumptions; data provenance, event definitions and engineering applicability are not independently verified. A point estimate is not a guarantee. The current report renderer does not support this result kind; it must not be disguised as another model.

Provenance: the project's licensed public Kaplan–Meier risk-set implementation and the standard `d/n` method; see [Brian P Hobbs (2015)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4617278/) for method context. The original project has a wider nonparametric implementation whose source and licensing need further review; this candidate does not import the `reliability` library or copy that whole service. Other third-party dependencies retain their own terms; limited comparisons do not establish complete historical provenance or prove no copying elsewhere.

The original 50-file candidate has historical Windows x64/Python 3.10.11 evidence: 80 tests and both bilingual examples passed. The current integration passed 22 targeted checks (15 Nelson–Aalen and 7 Kaplan–Meier) on Linux x86_64/Python 3.12.14. Both bilingual examples were rerun, and 3,000 additional deterministic synthetic cases agreed with independent exact-fraction risk-count references within two floating-point ULPs per event row. These checks do not constitute a new full-suite or Windows run. Real engineering use, report integration, web UI, browser visual review and VDI remain unverified. The generic `app` namespace was checked only in the test copy and may conflict in other processes; this is not production or complete security acceptance. Source publication does not validate deployment, project installation or the wider workbench. Existing unsupported-model and filesystem-path restrictions remain in place.
