# Validation report — 2026-10-18

Tested on Windows using Python 3.12, numpy 2.2.6, pandas 2.2.3, scipy 1.15.3, scikit-learn 1.6.1 and matplotlib 3.10.7. Exact installed packages are recorded in requirements-lock-tested.txt. Cross-platform execution has not been tested.

## Executed checks

- All nine R02, R03, R04, R05, R06, R07, R08, R09A and R09C stages finished successfully from the eight supplied input CSVs in a new build/run directory. Archived outputs were not used as substitute model outputs during that run.
- R02's 58-row result matches the archived result within rtol=1e-8, atol=1e-10.
- The regenerated candidate library has 4,784 records. The same 480 Pareto candidate identities and the same 25 selected candidate identities are recovered. Selected life-form proportions and 22/3 structure counts agree.
- All 58 final management classifications and regional area shares agree. The four high-transferability units are retained (see supplied and rerun R09C summaries).
- Strict numerical equality fails from R03 onward: maximum baseline V_hydro difference is 0.000255524 (fraction units), maximum selected V_target difference is 0.000170349. R03's q85 sensitivity column differs by up to 0.006294552. Small downstream objective/sensitivity differences are enumerated in reproduction_comparison.json.
- ExistingWoodyContext differs in CSV representation (True/False versus 1.0/0.0), not logical assignments. The original computation environment was not supplied; the cause of all floating-point/model differences is not conclusively established. These differences are not hidden by loosening test tolerances.
- tools/compare_run.py deliberately returns exit code 1 when strict differences are found. This does not mean that the nine stages failed to run. The stored comparison and headline reports explain the distinction.
- Figure 4 and complete Figure 5 A–F were regenerated successfully from the preserved revised tables. Both scripts verify numerical joins, ranges, summaries, text bounds and font embedding. Outputs use Arial and 600 dpi raster formats; source map pixels remain a raster component of Figure 5.
- CITATION.cff passes the official CFF 1.2.0 JSON Schema with format checking. The supplied ORCID passes its check-digit test; this does not independently verify identity.
- Published CSVs are byte-identical copies. Source hashes and transformation descriptions are in source_manifest.json. The ZIP excludes test outputs, dependencies, local caches and original manuscript/correspondence files.

## Important limits

This is a runnable companion starting from aggregated inputs, not a complete reconstruction of every upstream satellite preprocessing step. R01 preprocessing, R09B sample generation and the old R10 Shapefile were not supplied. Figures 1–3 are provided images, not newly rerun maps. R09 local species/density material has the applicability limits stated in SCOPE_AND_PROVENANCE.md.

The preserved revised tables are the source of the released journal figures. New retraining results must not silently replace them in an article or release. If the author wants strict identity to the historical computation, the original environment and upstream export history should be recovered first.
