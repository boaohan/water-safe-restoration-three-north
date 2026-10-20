R03 — Hydroclimatic vegetation-occupancy envelope
=================================================

Baseline definition:
V_hydro = Q25 over 2005–2024 annual q0.90 FVC-envelope predictions.

Calibration domain:
- GDE_Level == 0
- CroplandFrac < 0.10
- PermanentWaterFrac < 0.05
- NaturalRefAreaShare >= 0.05

Target:
- annual whole-unit FVC

Predictors:
- P_mm
- PET_mm
- Runoff_mm
- Soil_mm
- Tmean_C
- VPD_kPa
- AI_P_PET
- Elevation_m
- Slope_deg

Excluded:
- AET, because it is partly vegetation-dependent
- GDE/GWSA variables, because groundwater constraint is applied later
- tree/shrub/herbaceous decision variables
- current LAI

Baseline diagnostic sparse/open candidate:
- V_hydro < 0.15
- BarrenLandFrac >= 0.50

This diagnostic is NOT the final management classification.
R04 will recompute GDE-safe LAI.
R05 will combine LAI headroom + V_headroom + GDE + land-surface constraints
to define final active-restoration eligibility.

QA:
{
  "input_classyear_rows": 1160,
  "input_classcodes": 58,
  "input_years": 20,
  "training_rows": 180,
  "training_classcodes": 9,
  "training_basezones": 9,
  "training_basezone_list": [
    0,
    3,
    6,
    7,
    8,
    9,
    11,
    13,
    14
  ],
  "output_classcodes": 58,
  "V_hydro_min": 0.07486857573201812,
  "V_hydro_median": 0.3874630761932666,
  "V_hydro_max": 0.5383568765481986,
  "V_headroom_median": 0.0,
  "current_FVC_above_Vhydro_n": 38,
  "prelim_sparse_open_n": 7,
  "prelim_sparse_open_ClassCodes": [
    20,
    40,
    80,
    90,
    120,
    130,
    140
  ]
}

Validation:
                     model                 validation  n_samples  n_classcodes  n_basezones  pinball_loss_q90      MAE     RMSE       R2  empirical_coverage_y_le_pred
R03_FVC_hydro_envelope_q90     5-fold grouped by Year        180             9            9          0.007765 0.041990 0.062902 0.850300                      0.833333
R03_FVC_hydro_envelope_q90 5-fold grouped by BaseZone        180             9            9          0.029014 0.098855 0.131080 0.349936                      0.755556