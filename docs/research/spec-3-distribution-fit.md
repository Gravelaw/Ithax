# Distribution fit, upload parser and Excel reader (spec 3, M6)

## Question

Spec 3 "Endpoints", `POST /v1/projects/{pid}/data/{file}/fit`: "`{column}` → candidate
distributions from the spec 1 list with fitted fields and a fit score (library chosen at
M6 research)". AKS-113 also adds the upload (`POST /v1/projects/{pid}/data`, "an uploaded
CSV or Excel file"), which needs a multipart parser and an Excel reader. Before any code
(guide rule 3):

1. Which library fits the spec 1 distributions to a column? For each spec 1 distribution:
   the library's family, how its parameters map to spec 1's fields, and what happens for a
   constant, tiny, negative or huge column. How is a fit score computed, and how are
   candidates compared?
2. Rule 7: the fit must wrap a library and implement no estimator iteration of its own.
   What is left for the product to write?
3. The multipart parser (`python-multipart`, 0.0.33, Apache-2.0 per AKS-110's research):
   confirm.
4. The Excel reader: current version, licence read from the installed distribution's
   licence file, Windows and Linux support, install on Python 3.11 and 3.13, its runtime
   dependencies' licences, and how it behaves on files that are corrupt, password
   protected, multi-sheet or not Excel at all.

## Finding

Method (2026-11-07): the PyPI JSON of each release read with `curl` (upload date, files,
`requires_python`); the packages installed with `pip` into the project venv (Python
3.13.18) and into a fresh venv on `/usr/bin/python3.11` (3.11.18) in the scratch folder;
licences read from each installed distribution's licence file; the fits and the Excel
reader probed with scratch scripts (run with `python -I`, outside the repository) on the
columns and files described below.

### 1. The fit: `scipy.stats`, maximum likelihood

scipy is already a dependency (`scipy>=1.17.1`; 1.18.1 installed, BSD-3-Clause, recorded
at AKS-101 and AKS-102). Every continuous distribution in `scipy.stats` has `fit(data,
*, floc=..., fscale=..., method="MLE")`, which returns the shape parameters, then `loc`
and `scale`, by maximum likelihood (the default; method of moments with `method="MM"`).
Fixed parameters (`floc=0`) keep a family to the spec 1 form. The documentation (SciPy
1.18.0) says invalid data raises `ValueError` or `TypeError`, a failed fit raises
`FitError`, and data with NaN or infinity raises `RuntimeError`; the probe also saw
`FitDataError` (a `ValueError`) for negative data in `expon` and `lognorm` with
`floc=0`, and `RuntimeWarning`s on degenerate data.

The mapping from scipy to spec 1's fields (spec 1 "Distributions"):

| spec 1 | scipy family and fit | spec 1 fields from the fitted parameters |
| --- | --- | --- |
| `constant` | none: a column whose values are all equal | `value` = that value |
| `exponential` | `expon.fit(x, floc=0)` (closed form inside scipy: scale = mean) | `mean` = scale |
| `uniform` | `uniform.fit(x)` (closed form: loc = min, scale = max − min) | `min` = loc, `max` = loc + scale |
| `triangular` | `triang.fit(x)` (shape c, loc, scale; numerical MLE) | `min` = loc, `mode` = loc + c·scale, `max` = loc + scale |
| `normal` | `norm.fit(x)` (closed form: mean and population sd) | `mean` = loc, `sd` = scale |
| `lognormal` | `lognorm.fit(x, floc=0)` (s, scale; closed form with `floc`) | σ = s, μ = ln scale; `mean` = e^(μ+σ²/2), `sd` = `mean`·√(e^(σ²) − 1) |
| `weibull` | `weibull_min.fit(x, floc=0)` (c, scale; numerical MLE) | `shape` = c, `scale` = scale |
| `empirical` | not fitted: the column itself (`data` reference) | `data` = `{file, column}` |

What the probe showed (scipy 1.18.1, numpy 2.5.4):

- **Ordinary data** (2,000 exponential values, mean 2): the exponential and Weibull fits
  recover the mean and a shape near 1, with Kolmogorov–Smirnov statistics of 0.011 and
  0.011, and the uniform, triangular and normal fits score 0.64, 0.46 and 0.16, so the
  score separates good and bad candidates.
- **A constant column** (50 values of 3.0): `uniform` and `norm` return a zero scale and a
  NaN statistic with a warning; `triang`, `lognorm` and `weibull_min` return parameters at
  the edge of their range (a Weibull shape of 3.9·10⁸). No family describes it; only
  `constant` does.
- **Tiny and huge columns** (exponential values with mean 10⁻³⁰⁰ and 10³⁰⁰): the
  closed-form families are right, but `norm` gives an infinite `sd` for the huge column,
  `weibull_min` an infinite scale and a statistic of 1, and the tiny column's Weibull fit
  is wrong by 275 orders of magnitude. The optimiser works in absolute units. Dividing the
  column by its largest absolute value before the fit, and multiplying `loc` and `scale`
  back, is exact for these location-scale families (the shapes and the
  Kolmogorov–Smirnov statistic do not change), and removes the problem; it is a change of
  unit, not an estimator.
- **Negative values** (normal around 0): `expon` and `lognorm` with `floc=0` raise
  `FitDataError`; `weibull_min` with `floc=0` returns a meaningless fit without an error.
  So the positive families must be left out of a column with values ≤ 0 (and the
  exponential out of one with negative values or a mean of 0) before scipy is called.
- **Two values** (1 and 2): every family returns parameters; the fits are poor but valid.
- **Speed** (200,000 Weibull values): every closed-form fit takes under 0.05 s, the
  Weibull fit 0.26 s, and the triangular fit 4.4 s, the slowest; it grows with the
  number of values.

**Fit score.** Two candidates were compared:

- **Akaike's information criterion** (2k − 2 ln L, from scipy's log-likelihood). The
  textbook score for choosing between families fitted by maximum likelihood, but its value
  means nothing on its own, depends on the unit of the column, and is −∞ or undefined for
  a uniform or triangular fit whose support touches the data.
- **The Kolmogorov–Smirnov statistic** D, from `scipy.stats.kstest(x, cdf)` with the
  fitted distribution: the largest distance between the column's cumulative fractions and
  the fitted distribution's. It lies from 0 (a perfect fit) to 1, has the same meaning for
  every family and every unit, and can be said in plain words ("how well the pattern
  fits", the design system's term). Its p-value is not valid when the parameters were
  fitted to the same data, so the statistic is used only to rank, not to test.

### 2. Rule 7

`fit` iterates (scipy's optimiser), but inside the library. The product writes only:
choosing which families apply to a column (positive families need positive values), the
change of unit before and after, the mapping of the table above, the checks that the
fitted fields are finite and agree (spec 1 E160: `sd`, `shape`, `scale` and a positive
`mean` above zero, `min` ≤ `mode` ≤ `max`), and the sort by score. The lognormal `mean`
and `sd` are closed-form formulas of the fitted σ and μ. No estimator, optimiser or
iteration is written.

### 3. Multipart parser: `python-multipart` confirmed

`python-multipart` 0.0.33, uploaded 2026-10-31, one pure-Python wheel
(`python_multipart-0.0.33-py3-none-any.whl`), `requires_python >=3.11`, licence
expression `Apache-2.0`; the installed licence file
`python_multipart-0.0.33.dist-info/licenses/LICENSE.txt` is the Apache License 2.0
text. No runtime dependencies. Installed and imported on 3.11.18 and 3.13.18. It is the
parser Starlette 1.10's `MultiPartParser` uses, so the product imports nothing from it
directly. Starlette's parser spools file parts to a temporary file beyond 1 MiB and takes
`max_files`, `max_fields` and `max_part_size` (for non-file fields), but no limit on a
file's size, so the upload's size limit must be enforced on the request stream before
the parser.

### 4. Excel reader: `openpyxl`, with `defusedxml`

| Package | Version (uploaded) | Licence (file read) | Wheel | Python |
| --- | --- | --- | --- | --- |
| openpyxl | 3.1.5 (2024-06-28), the latest | MIT (`openpyxl-3.1.5.dist-info/LICENCE.rst`, "Copyright (c) 2010 openpyxl") | pure Python, `py2.py3-none-any` | `>=3.8` |
| et-xmlfile (openpyxl's only dependency) | 2.0.0 (2024-10-25) | MIT (`LICENCE.rst`, "Copyright (c) 2010 openpyxl"), with `LICENCE.python` for the standard-library code it includes (PSF) | pure Python | `>=3.8` |
| defusedxml | 0.7.1 (2021-03-08), the latest | PSF-2.0 (`defusedxml-0.7.1.dist-info/LICENSE`, "Python Software Foundation License Version 2") | pure Python | 2.7 and 3.5 onwards |

All three are pure Python, so they install the same way on Windows and Linux; they
installed and ran on Python 3.11.18 and 3.13.18 (the probe below gave the same results on
both). openpyxl reads `.xlsx` and `.xlsm` (Office Open XML), not the old binary `.xls`.

**XML attacks.** openpyxl's documentation (read 2026-11-07, its page shows 3.1.3) says:
"By default openpyxl does not guard against quadratic blowup or billion laughs xml
attacks. To guard against these attacks install defusedxml." The Python documentation
(`xml` module, read 2026-11-07) says Expat versions lower than 2.7.2 may be vulnerable to
the billion laughs, quadratic blowup and large-token attacks; the scratch Python 3.11.18
has Expat 2.6.1, the project's 3.13.18 Expat 2.9.0. openpyxl uses defusedxml whenever it
is installed (`openpyxl.DEFUSEDXML` is `True`; it can be switched off only by setting
`OPENPYXL_DEFUSEDXML` to something other than `True`). lxml, which openpyxl would prefer,
is not installed in the product.

**Probe of untrusted files** (openpyxl 3.1.5, `load_workbook(..., read_only=True,
data_only=True)`, then `iter_rows(values_only=True)` on the first worksheet):

- a workbook with two sheets: `worksheets` lists both, the first sheet's rows come back
  as tuples of `float`/`int`, `str`, `datetime`, `bool` and `None`;
- bytes that are not a zip file, a password-protected workbook (an OLE compound file,
  magic `D0 CF 11 E0`) and a truncated workbook: `zipfile.BadZipFile`;
- a sheet whose XML declares an entity: `ValueError` ("Unable to read workbook");
- a number cell of 5,000 digits: `ValueError` from Python's integer-string limit, raised
  while the rows are iterated, not at load;
- a number cell that is `1e999` would read as an infinity, and one of 400 digits as an
  integer too large for a float.

So every failure of the reader is an exception of some kind, raised at load or during
iteration; the product has to catch them all and give a coded issue, and has to check
every number cell for a finite float.

## Sources

- SciPy 1.18.0 documentation, `scipy.stats.rv_continuous.fit`,
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rv_continuous.fit.html>,
  read 2026-11-07.
- SciPy documentation, `scipy.stats.kstest`, `expon`, `uniform`, `triang`, `norm`,
  `lognorm`, `weibull_min`,
  <https://docs.scipy.org/doc/scipy/reference/stats.html>, read 2026-11-07; the installed
  scipy 1.18.1 and its docstrings.
- PyPI JSON, read 2026-11-07: <https://pypi.org/pypi/python-multipart/0.0.33/json>,
  <https://pypi.org/pypi/openpyxl/3.1.5/json>, <https://pypi.org/pypi/et-xmlfile/2.0.0/json>,
  <https://pypi.org/pypi/defusedxml/0.7.1/json>, <https://pypi.org/pypi/scipy/1.17.1/json>.
- openpyxl documentation, "Security", <https://openpyxl.readthedocs.io/en/stable/>, read
  2026-11-07.
- Python documentation, "XML Processing Modules", XML vulnerabilities,
  <https://docs.python.org/3/library/xml.html>, read 2026-11-07.
- Starlette 1.10.0 source, `starlette/formparsers.py` (`MultiPartParser`), installed.
- `docs/research/spec-3-service-framework-check.md` (AKS-110: `python-multipart` 0.0.33,
  Apache-2.0).
- Akaike, H. (1974), "A new look at the statistical model identification", *IEEE
  Transactions on Automatic Control* 19(6), 716–723 (AIC); Massey, F. J. (1951), "The
  Kolmogorov-Smirnov test for goodness of fit", *JASA* 46(253), 68–78 (D and the
  fitted-parameters caveat).

## Decision

- **The fit library is `scipy.stats`** (already a dependency, BSD-3-Clause), by maximum
  likelihood with the families and mappings of the table above. Candidates are the spec 1
  distributions that apply to the column: `constant` alone for a column whose values are
  all equal; otherwise `exponential` (values ≥ 0, mean > 0), `uniform`, `triangular`,
  `normal`, and `lognormal` and `weibull` (values > 0). `empirical` is not fitted: the
  Data screen's "Use the data as it is" writes the `data` reference itself. The column is
  divided by its largest absolute value before the fit and the fitted `loc` and `scale`
  are multiplied back. A family whose fit raises, warns its way to a non-finite value, or
  gives fields that would fail spec 1's E160 rules is left out; it is never an error.
- **The fit score is the Kolmogorov–Smirnov statistic** (`scipy.stats.kstest`), from 0
  (best) to 1, used to rank: candidates are returned best first, ties in spec 1 order.
- **Fields are in spec 1's parameterisation**, written as spec 1 writes them: a quantity
  in the column's declared unit (`"2.0 min"`) for a time field when the column has a unit,
  a plain number otherwise and for the Weibull `shape`; so a candidate is a distribution
  object `set_setting` can take as it is.
- **Uploads use `python-multipart` 0.0.33** (Apache-2.0) through Starlette's
  `MultiPartParser`, fed from a request stream that stops at the upload size limit.
- **The Excel reader is `openpyxl` 3.1.5** (MIT; its dependency `et-xmlfile` 2.0.0,
  MIT), read-only with cached values, first worksheet only, with **`defusedxml` 0.7.1**
  (PSF-2.0) installed so that openpyxl refuses entity declarations whatever Expat the
  Python has. Every exception from openpyxl is caught and becomes a coded issue; every
  number cell is checked to be a finite float.
- Each dependency is recorded in `docs/DECISIONS.md` with its version, licence and how it
  was checked.

## Tested

- `tests/model/test_fit.py`: each family's fields in spec 1's parameterisation from a
  known column, the score ranking, a constant column giving `constant` alone, positive
  families left out of a column with zero or negative values, tiny (10⁻³⁰⁰) and huge
  (10³⁰⁰) columns fitted after the change of unit, a family whose fit fails left out, and
  quantities written in the column's unit that spec 1 reads back.
- `tests/model/test_data_files.py`: CSV and Excel reading, including the probe's
  corrupt, password-protected, multi-sheet, entity-declaring and oversized-number files.
- `tests/service/test_data.py`: the four endpoints, the upload size limit and the
  multipart parser's refusals.
