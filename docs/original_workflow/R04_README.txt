R04 — Revised GDE-constrained safe LAI
======================================

Inputs:
- R02_Class_LAIhydro_q25.csv
- R01B1_Static_ByClass_FINAL.csv
- R03_Class_Occupancy.csv

Critical correction:
The old workflow defined GDE_stability = GDE_persistence / 4, so the two risk
components were mathematically redundant. R04 replaces that duplicate stability
term with a temporal-stability index derived from the four period-specific GDE
fractions.

Revised GDE descriptors:
- GDE_frac: 2005–2024 union fraction
- GDE_persistence_revised: mean of GDE_frac_P1..P4
- GDE_stability_revised:
      1 - CV(GDE_frac_P1..P4), clipped [0,1],
      and set to 0 for GDE_Level == 0
- GWSA decline: max(-GWSA_trend, 0)
- GDE class component:
      0 -> 0.00
      1 -> 0.30 + separate hard conservation cap
      2 -> 0.45
      3 -> 0.70

Baseline risk:
R_gde =
  0.30 * risk(GDE fraction)
+ 0.20 * risk(temporal stability)
+ 0.15 * risk(temporal persistence)
+ 0.20 * risk(GWSA decline)
+ 0.15 * GDE-class component

R_gde is clipped to [0, 0.80].

Safe LAI:
LAI_safe_pre = LAI_hydro * (1 - R_gde)

For GDE_Level == 1:
LAI_safe = min(LAI_safe_pre, LAI_current_3yr)

Interpretation:
LAI_safe is a water-safety boundary, not a planting target.
If LAI_safe < current LAI, do NOT automatically prescribe thinning.
R05 will interpret this as "no additional active-canopy headroom" and combine
it with V_headroom, sparse/open-land status, land use, and GDE constraints.

Weak/strong sensitivity:
- weak:   R_gde × 0.8
- strong: R_gde × 1.2

QA:
{
  "rows": 58,
  "unique_classcodes": 58,
  "missing_LAI_safe": 0,
  "negative_LAI_safe": 0,
  "LAI_safe_above_LAI_hydro": 0,
  "core_level1_above_current_LAI": 0,
  "safe_ratio_min": 0.14600953534034988,
  "safe_ratio_median": 0.5497436424719344,
  "safe_ratio_max": 0.9999986621311489,
  "LAI_safe_min": 0.2248031581368352,
  "LAI_safe_median": 0.9726340536601922,
  "LAI_safe_max": 3.334740673907067,
  "n_over_safe_capacity": 23,
  "area_over_safe_capacity_km2": 800581.22227797,
  "n_with_positive_LAI_headroom": 32,
  "n_with_positive_V_headroom": 20,
  "prelim_sparse_open_n": 7
}

By GDE level:
 GDE_Level  n_ClassCode     Area_km2  median_LAI_hydro  median_LAI_safe  median_safe_ratio  area_weighted_median_safe_ratio  median_R_gde  n_over_safe_capacity  area_over_safe_capacity_km2  median_LAI_headroom
         0           15 2.994900e+06          1.246096         1.171944           0.934091                         0.931238      0.065909                     0                     0.000000             0.739001
         1           14 7.026202e+05          1.684057         0.546042           0.264908                         0.258326      0.702093                    11                649939.375743             0.000000
         2           14 1.152206e+05          1.684057         0.908754           0.501950                         0.475880      0.498050                     8                 95789.223437             0.000000
         3           15 1.868080e+05          1.697069         1.011510           0.605316                         0.547901      0.394684                     4                 54852.623097             0.264111

Sensitivity:
Scenario  Median_LAI_safe  Median_safe_ratio  Median_LAI_headroom  n_over_safe_capacity  Area_over_safe_capacity_km2
    weak         1.105193           0.639795             0.290952                    15                660855.202911
baseline         0.972634           0.549744             0.152367                    23                800581.222278
  strong         0.794508           0.459692             0.006750                    27                911615.996884