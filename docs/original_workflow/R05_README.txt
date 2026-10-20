R05 — Active-restoration eligibility gate
=========================================

Purpose:
Separate "whether active restoration is justified" from the later question
"what tree/shrub/herb configuration is preferred".

Baseline gates:
0 = GDE conservation / no active expansion
1 = Natural sparse/open conservation
2 = No additional canopy headroom
3 = Structural management only
4 = Limited footprint expansion
5 = Active footprint expansion eligible

Baseline thresholds:
- Natural sparse/open:
    V_hydro < 0.15
    AND BarrenLandFrac >= 0.5
- Meaningful LAI headroom:
    LAI_headroom >= 0.05
    AND LAI_headroom / LAI_safe >= 0.05
- Meaningful vegetation-footprint headroom:
    V_headroom >= 0.005
- Active-expansion capacity:
    min(relative LAI headroom, relative V headroom) >=
    0.1

Important interpretation:
- Gate 3 does not prohibit active management. It prohibits expansion of the
  vegetation footprint; composition/density can still be adjusted inside the
  existing footprint.
- Gate 4 allows only limited footprint expansion.
- Gate 5 is eligible for active footprint expansion.
- These are NOT final tree/shrub/herb management categories.
- R06 will generate candidate structures subject to these gate-specific bounds.

Candidate bounds passed to R06:
- V_candidate_min
- V_candidate_max
- LAI_target_max

QA:
{
  "rows": 58,
  "unique_classcodes": 58,
  "missing_gate": 0,
  "total_area_km2": 3999548.721424142,
  "active_expansion_n": 7,
  "active_expansion_area_km2": 52152.58776148496,
  "active_expansion_area_share_pct": 1.3039618065438816,
  "limited_expansion_area_share_pct": 14.79091244059145,
  "structural_only_area_share_pct": 20.65637337944313,
  "no_canopy_headroom_area_share_pct": 3.7664710952951594,
  "natural_sparse_area_share_pct": 41.91479510704584,
  "gde_conservation_area_share_pct": 17.567486171080535,
  "V_candidate_max_below_min_n": 0,
  "LAI_target_max_negative_n": 0
}

Baseline area summary:
 EligibilityGateCode                        EligibilityGate  n_ClassCode     Area_km2  Area_share_pct  median_AI  median_LAI_headroom  median_V_headroom  median_ExpansionCapacityScore  area_weighted_median_safe_ratio
                   0 GDE conservation / no active expansion           14 7.026202e+05       17.567486   0.448515             0.000000           0.000000                       0.000000                         0.258326
                   1       Natural sparse/open conservation            7 1.676403e+06       41.914795   0.112714             0.677110           0.023938                       0.289939                         0.940494
                   2          No additional canopy headroom           12 1.506418e+05        3.766471   0.366110             0.000000           0.000000                       0.000000                         0.528020
                   3             Structural management only           15 8.261617e+05       20.656373   0.369729             0.410635           0.000000                       0.000000                         0.869452
                   4            Limited footprint expansion            3 5.915697e+05       14.790912   0.206340             0.604620           0.013557                       0.065483                         0.879163
                   5    Active footprint expansion eligible            7 5.215259e+04        1.303962   0.594343             0.678073           0.108995                       0.469081                         0.618431