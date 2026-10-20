# Scope and provenance

Prepared from the author-specified research folder on 2026-10-18. The folder name and older supplementary material use an earlier manuscript title; the repository identifies the latest supplied English manuscript title. The latest manuscript is anonymized and does not supply an author list.

## Material selection

- R02_LAIhydro_rerun_bundle is used as the consolidated analytical source. Separate R03/R04/R05 execution bundles are redundant/older snapshots and are not merged into this pipeline.
- Original CSV values are copied byte-for-byte. Revised figure tables are stored separately from analytical snapshots; they are not silently substituted into model inputs.
- R02–R09 model equations, thresholds, random seeds and optimization logic are unchanged. Hard-coded example drive paths and R09A external fallback paths are removed. Included local reference files are used instead.
- R10_Figure5_management_pathway.py is omitted: its Shapefile input is absent and its four-panel design predates the supplied six-panel Figure 5. The current plotting script embeds the supplied map raster and preserves the measured chart values.
- Figure 4/5 scripts and PDFs were prepared earlier in this working session from the author's revised tables. Only paths and platform-specific font discovery were adapted for this repository.
- Private full local path strings in R09A_InputAudit.json are converted to repository-relative input paths. SHA-256 provenance records identify all source copies and transformations.
- Manuscript revisions, cover letter, response to editor, Word locks, archived JPG duplicates, Illustrator project files and redundant TIFF previews are excluded. This package is not a preprint deposit.

## Reproducibility boundary

| Stage | Included | Boundary |
|---|---|---|
| R01 | Four class-year panels, static table, canonical rasters | Raw data acquisition, GEE/other preprocessing and polygon generation scripts not found |
| R02–R08 | Analytical Python code, inputs and supplied output snapshots | Environment can change numerical model results; see actual validation |
| R09A | Local ranges and 40-species seed table; audit script | Full 134-species pool not supplied; density transfer is not region-wide evidence |
| R09B | 10,000-row reference environment sample and summary | Sampling/extraction code not found |
| R09C | Transferability code and outputs | Depends on supplied R09B sample |
| Figures 1–3 | Supplied raster outputs and available figure tables | Complete map/figure generation code not supplied |
| Figures 4–5 | Revised tables and current plotting scripts | Figure 5A is a supplied raster, not regenerated spatial analysis |

The 63.25% conservation/passive area, 20.66% structural-management area and 16.09% expansion area are different denominators/concepts from the 22/25 and 3/25 structure counts. Do not mix them. The older manuscript's 76.5% figure uses another definition and must not be described as a before/after treatment effect.

Third-party source datasets retain their original terms and required attribution. Dataset identifiers, retrieval dates, processing versions and redistribution permissions were not independently reconstructed from the directory; authors should complete these from acquisition records before a public release. No license is assumed from mere file possession.
