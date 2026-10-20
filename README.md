# Water-safe restoration in the Three-North region

Code and derived-data companion for **Groundwater-dependent ecosystems define water-safe restoration space and vegetation structures across China's Three-North Shelterbelt region**.

This prepared repository has not been published and has no registered DOI yet. Author: **Aohan Bo**, Beijing Forestry University, Beijing, China ([ORCID](https://orcid.org/0009-0002-0355-0262)). Code is MIT licensed; author-owned data, figures and documentation use CC BY 4.0. See [upload and DOI instructions in Chinese](docs/UPLOAD_AND_DOI_zh.md). This is a research-companion archive; a journal article DOI is a separate identifier.

## Contents

| Folder | Contents |
|---|---|
| `analysis/` | Supplied R02–R09 analytical scripts with portable path cleanup |
| `data/inputs/` | Four five-year panels, static 58-unit table, local reference tables, R09B reference environment sample |
| `data/reference/` | Supplied result snapshots for comparison; not overwritten during reruns |
| `data/reference_qa/` | Supplied quality summaries, distinguished from new validation |
| `data/figure2`–`data/figure5` | Figure-specific tables; revised R07/R08 tables drive Figure 4/5 |
| `data/spatial/` | Supplied canonical analytical-unit, base-zone and GDE-class GeoTIFFs |
| `plots/` | Portable Figure 4 and complete Figure 5 A–F scripts |
| `figures/` | Supplied Figures 1–3 and previously prepared Figure 4/5 PDFs/PNGs/captions |
| `docs/` | Scope, field definitions, provenance, validation and publication instructions |
| `tools/` | Re-run, compare, integrity and citation-metadata helpers |

## Quick start

Tested with Python 3.12 on Windows. For the exact tested package set install `requirements-lock-tested.txt`; `requirements.txt` lists direct dependencies. Python 3.11 is expected to work but was not tested. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools/check_integrity.py
.venv\Scripts\python.exe tools/validate_data.py
.venv\Scripts\python.exe tools/run_pipeline.py
.venv\Scripts\python.exe tools/compare_run.py
.venv\Scripts\python.exe plots/figure4.py
.venv\Scripts\python.exe plots/figure5.py
```

On macOS/Linux use `.venv/bin/python` instead. Arial must be installed for the journal figures; set `ARIAL_FONT_DIR` if needed. No font files are distributed. Each model rerun writes to a **new** directory under `build/`; use `--output build/run2` for another run. Stored snapshots remain unchanged. Figure scripts write to `build/figure4` and `build/figure5`.

## Reproduction result

All nine analytical stages executed successfully in the tested Windows/Python 3.12 environment. The same 480 Pareto candidate identities, 25 selected candidate identities and 58 final management classes were obtained. Strict numeric identity is **not** achieved: small differences begin in R03 occupancy predictions (maximum baseline V_hydro difference 0.000256) and propagate downstream. Archived figure inputs are preserved and reproduce Figure 4/5 directly. `compare_run.py` deliberately returns nonzero for this strict mismatch. Details and full comparison are in docs/VALIDATION.md.

## Scope and interpretation

The supplied aggregation covers 2005–2024, 1,160 class-year records and 58 analytical units. The model candidate library contains 4,784 records; 480 Pareto records span 25 optimized units. The selected structures comprise 22 low-tree mixed and 3 shrub–herbaceous units. These are **unit counts**, not area percentages. The remaining 33 units follow direct management pathways.

Regional management shares are 41.91% sparse/open conservation, 20.66% close-to-nature structural management, 17.57% GDE conservation/passive recovery, 16.09% low-tree mixed restoration and 3.77% herbaceous/exclosure recovery. Life-form proportions `q_tree + q_shrub + q_herb = 1` refer to vegetated area; whole-land tree fraction is `V_target * q_tree`. Pareto min–max ranges are not confidence intervals.

The repository starts at the supplied aggregated tables. Original satellite downloads, R01 preprocessing/export code, R09B sample-generation code and the Shapefile referenced by an obsolete R10 plotting script were not found in the supplied directory. The local species seed table has 40 entries, not the documented 134-species full pool. Numerical planting densities must not be interpreted as validated region-wide prescriptions. See [scope and provenance](docs/SCOPE_AND_PROVENANCE.md) and [validation report](docs/VALIDATION.md).

## Citation and rights

The root `CITATION.cff` contains the author-approved name, affiliation, ORCID and licenses and passes the CFF 1.2.0 schema. The prepared release version is 1.0.0. The repository URL, actual publication date and archive DOI remain unset until created. After obtaining these values, update `metadata/publication.json`, run `python tools/prepare_metadata.py`, and refresh checksums. See [license scope](LICENSE) and [rights](RIGHTS.md). When the article receives a DOI, relate the archive to it as supplementary material; do not replace the archive DOI with the article DOI.
