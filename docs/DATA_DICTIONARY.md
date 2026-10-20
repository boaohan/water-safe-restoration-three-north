# Core fields and table conventions

All tables use original UTF-8 CSV values (some include a UTF-8 BOM). `docs/table_inventory.csv` lists every published table, row count and column names. Empty cells remain empty; no missing observations are fabricated.

| Field | Meaning / scale |
|---|---|
| ClassCode | Canonical analytical-unit identifier; join key; not a continuous predictor |
| BaseZone | Base ecohydrological-zone code; retain source coding |
| GDE_Level | Categorical GDE class code; numerical order is not an increasing-risk scale |
| Year | Observation year, 2005–2024 in class-year inputs |
| Area_km2 | Analytical-unit or aggregated area in square kilometres |
| LAI_hydro | Hydroclimatic LAI envelope from the supplied quantile model |
| LAI_safe | LAI constrained by the groundwater/GDE framework |
| LAI_target | Selected/candidate LAI; model output, not measured stand density |
| V_current / V_target | Vegetated-area occupancy fractions, 0–1 |
| V_expansion | Vegetation-footprint expansion fraction; distinguish from structural management |
| q_tree / q_shrub / q_herb | Fractions within vegetated area; sum to 1 |
| q_*_min / q_*_max | Exported Pareto minimum/maximum; not confidence limits |
| CandidateID | Candidate identifier; pair with ClassCode where needed |
| obj1_sand_benefit | Sand-fixation benefit score, maximize |
| obj2_eco_stability | Ecological-stability score, maximize |
| obj3_water_pressure | Water-pressure score, minimize |
| obj4_gde_risk | GDE-risk score, minimize |
| LifeFormStructure | Selected/candidate life-form category |
| FinalManagementPathway | Final management class, incorporating eligibility and footprint constraints |
| n_ClassCode | Number of analytical units, not area |
| Area_share_pct | Share of all study-area km², already in percent |
| Within_GDE_Level_pct | Share within the specified GDE class, already in percent |
| Within_Aridity_pct | Share within the specified aridity class, already in percent |
| Figure5_EF_Include | 1 for the 25 optimized units displayed in Figure 5E/F |

Figure 4 uses per-unit four-objective Pareto sets projected into two dimensions. Selected compromises must not be reselected from a two-objective view. Figure 5E/F display unweighted unit distributions; V_target is multiplied by 100 only for display. Other fields are preserved exactly and explained, where available, in `docs/original_workflow/` and the associated analytical code. The inventory is not a substitute for an author-reviewed complete variable dictionary.
