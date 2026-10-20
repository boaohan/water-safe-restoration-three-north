R02 — Hydroclimatic LAI carrying-capacity rerun
================================================

Selected revised calibration:
- Target: LAI_nat_max (annual growing-season maximum LAI averaged over natural-reference 1-km cells)
- Training domain: GDE_Level == 0 only
- Natural-reference support threshold: >= 30 km2
- Training observations: 300 = 15 non-GDE BaseZones × 20 years
- Quantile: 0.95
- Final sustainable LAI_hydro: q25 of the 20 annual q95 predictions for each ClassCode
- Model: GradientBoostingRegressor(loss='quantile')
- n_estimators=300, learning_rate=0.03, max_depth=2,
  min_samples_leaf=3, subsample=1.0, random_state=42

Predictors:
- BaseZone
- P_mm, PET_mm, AET_mm, Runoff_mm, Soil_mm
- Tmean_C, VPD_kPa, AI_P_PET
- Elevation_m, Slope_deg

Explicitly excluded from the hydroclimatic model:
- GDE_Level, GDE_frac, GDE stability/persistence
- GWSA_mean_period and GWSA_trend
- current LAI and other current vegetation-state variables
- downstream tree/shrub/herbaceous decision variables

Why train only in non-GDE units?
The purpose of LAI_hydro is to estimate the hydroclimatic envelope before groundwater-dependent
ecosystem constraints are imposed. Including GDE-supported natural vegetation in the calibration
set can allow groundwater-subsidized high LAI to inflate the hydroclimatic envelope. The revised
calibration therefore uses non-GDE natural-reference units and applies GDE/GWSA constraints later.

Validation:
             model                 validation  n_samples  n_classcodes  n_basezones      target  quantile_alpha  pinball_loss_q95      MAE     RMSE       R2  empirical_coverage_y_le_pred  target_mean  prediction_mean
R02_revised_nonGDE     5-fold grouped by Year        300            15           15 LAI_nat_max            0.95          0.023227 0.315379 0.403867 0.738956                      0.906667     1.398204         1.697011
R02_revised_nonGDE 5-fold grouped by BaseZone        300            15           15 LAI_nat_max            0.95          0.134435 0.490870 0.592618 0.437935                      0.796667     1.398204         1.644870

R01B1 QA:
{
  "panel_rows": 1160,
  "years": 20,
  "classes": 58,
  "duplicate_class_year": 0,
  "missing_cells_panel": 0,
  "static_rows": 58,
  "missing_cells_static": 0,
  "natural_ref_area_km2_min": 2.928532,
  "natural_ref_share_min": 0.0050377228034773,
  "natural_ref_share_median": 0.5987258815720116,
  "sw_occurrence_median_pct": 0.8930127217037348,
  "training_rows": 300,
  "training_classcodes": 15,
  "training_basezones": 15,
  "training_years": 20,
  "training_min_natural_ref_area_km2": 420.4706097968136,
  "output_classcodes": 58,
  "output_missing_LAI_hydro": 0,
  "current_LAI_exceeds_LAI_hydro_count": 0,
  "LAI_hydro_min": 1.1717098118288303,
  "LAI_hydro_median": 1.6189598954860216,
  "LAI_hydro_max": 3.34011449228227,
  "support_low_n": 3,
  "support_medium_n": 6,
  "support_high_n": 49
}

Diagnostic comparison:
The file R02_LegacyLike_vs_Revised_byClass.csv compares the selected non-GDE calibration with
an otherwise identical model calibrated on all GDE classes. This is for method auditing / supplement,
not for the main model output.

Important interpretation:
NaturalRefAreaShare is NOT used to remove sparse dryland classes. Low natural-reference share is
an ecological signal of sparse vegetation, which will be handled explicitly in the next occupancy /
active-restoration eligibility step. NaturalRefSupport is retained as a reliability flag.