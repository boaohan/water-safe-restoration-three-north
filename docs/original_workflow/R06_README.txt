R06 — Revised tree/shrub/herb/open candidate space
==================================================

Main composition equation:
q_tree + q_shrub + q_herb = 1

q refers only to conditional life-form allocation within the vegetated
component.

Whole-land fractions:
f_tree  = V_target * q_tree
f_shrub = V_target * q_shrub
f_herb  = V_target * q_herb
f_open  = 1 - V_target

Therefore:
f_tree + f_shrub + f_herb + f_open = 1

Direct management:
Gate 0, 1 and 2 do not enter Pareto optimization.

Optimization:
Gate 3, 4 and 5.

Ratio grid step:
0.1

Baseline precautionary tree-cap screen:
climate cap = clip(AI - 0.05, 0, 0.60)
GDE level 2: q_tree <= 0.20
GDE level 3: q_tree <= 0.10

Coupled vertical-horizontal constraint:
LAI_target / V_target <= LAI_hydro / V_hydro

No species names and no species-specific density values are generated.

QA:
{
  "input_classcodes": 58,
  "candidate_rows": 4784,
  "optimized_classcodes": 25,
  "direct_management_classcodes": 33,
  "duplicate_candidate_ids": 0,
  "q_sum_failure_n": 0,
  "land_fraction_sum_failure_n": 0,
  "LAI_safe_violation_n": 0,
  "V_max_violation_n": 0,
  "PatchLAI_violation_n": 0,
  "TreeCap_violation_n": 0,
  "candidates_in_gate0_2_n": 0
}