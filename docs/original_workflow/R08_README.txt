R08 — Final management-pathway translation
===========================================

Final management taxonomy:
- GDE conservation / passive recovery
- Natural sparse/open conservation
- Herbaceous/exclosure passive recovery
- Close-to-nature structural management
- Shrub-herbaceous restoration
- Low-tree mixed restoration

Interpretation:
- Gate 3 is structural management within the existing vegetation footprint.
  It is NOT counted as new tree-involved restoration.
- Gates 4 and 5 are the footprint-expansion restoration domain.
- "Low-tree mixed restoration" replaces the old broad tree-shrub-grass
  restoration concept. Its tree component is conditional within vegetation
  patches and is further diluted at the whole-land level by f_open.

Regional area summary:
               FinalManagementPathway  n_ClassCode     Area_km2  Area_share_pct
     Natural sparse/open conservation            7 1.676403e+06       41.914795
Close-to-nature structural management           15 8.261617e+05       20.656373
  GDE conservation / passive recovery           14 7.026202e+05       17.567486
           Low-tree mixed restoration           10 6.437223e+05       16.094874
Herbaceous/exclosure passive recovery           12 1.506418e+05        3.766471

Intervention-intensity summary:
InterventionIntensity  n_ClassCode     Area_km2  Area_share_pct
         conservation           21 2.379023e+06       59.482281
           structural           15 8.261617e+05       20.656373
    limited expansion            3 5.915697e+05       14.790912
              passive           12 1.506418e+05        3.766471
     active expansion            7 5.215259e+04        1.303962

Restoration-structure statistics:
                                     Metric         Value
                       restoration_area_km2 643722.337166
                 restoration_area_share_pct     16.094874
                  area_weighted_mean_q_tree      0.103711
area_weighted_mean_whole_land_tree_fraction      0.023315
           area_weighted_mean_open_fraction      0.781234
                area_weighted_mean_V_target      0.218766
              area_weighted_mean_LAI_target      0.471329

Headline comparison:
Submitted manuscript tree-shrub-grass restoration = 76.50%
Revised tree-involved active/limited restoration = 16.09%

The two percentages are not strictly identical definitions and should not be
presented as a direct before/after treatment effect. They document how the
revised framework changes the management interpretation after explicit
eligibility, sparse/open, occupancy, safe-LAI, and GDE constraints.

QA:
{
  "rows": 58,
  "unique_classcodes": 58,
  "total_area_km2": 3999548.721424142,
  "missing_final_pathway": 0,
  "optimized_rows": 25,
  "direct_rows": 33,
  "revised_tree_involved_restoration_area_share_pct": 16.09487424713533,
  "old_manuscript_tree_shrub_grass_pct": 76.5,
  "difference_percentage_points": -60.40512575286467,
  "active_plus_limited_expansion_area_share_pct": 16.09487424713533,
  "conservation_plus_passive_area_share_pct": 63.248752373421546,
  "structural_management_area_share_pct": 20.65637337944313
}