R07 — Revised four-objective Pareto optimization
================================================

Only R05 gates 3–5 are optimized.
Gates 0–2 remain direct management pathways from R06.

Objective 1 — maximize sand-fixation benefit
obj1 =
  [0.50 * V_utilization
 + 0.30 * LAI_utilization
 + 0.20 * structural diversity]
 * [0.60 + 0.40 * sand-demand background]

Objective 2 — maximize ecological stability / empirical plausibility
obj2 =
  0.45 * observed ecological-stability background
+ 0.35 * natural-reference similarity
+ 0.20 * moderate capacity use

Objective 3 — minimize water pressure
obj3 =
  0.35 * observed hydro-stress background
+ 0.325 * LAI utilization
+ 0.325 * vegetation-footprint utilization

Objective 4 — minimize GDE risk
obj4 =
  R_gde
  * [
      0.40
    + 0.30 * LAI utilization
    + 0.15 * footprint utilization
    + 0.15 * tree-canopy burden
    ]

Important:
- Every objective contains candidate-specific terms.
- Dynamic World / WorldCover are NOT optimization inputs.
  They remain independent validation data.
- Best compromise uses equal weights 0.25/0.25/0.25/0.25
  on the Pareto front after local normalization.
- 1000 Dirichlet random weight combinations quantify sensitivity.

QA:
{
  "candidate_rows": 4784,
  "optimized_classcodes": 25,
  "pareto_rows": 480,
  "pareto_classcodes": 25,
  "best_rows": 25,
  "best_unique_classcodes": 25,
  "duplicate_best_classcodes": 0,
  "missing_objective_values": 0,
  "min_pareto_solutions_per_class": 3,
  "median_pareto_solutions_per_class": 16.0,
  "max_pareto_solutions_per_class": 41,
  "area_weighted_Dirichlet1000_structure_consistency": 0.7072786211451997,
  "area_weighted_Dirichlet1000_tree_presence_consistency": 0.8532468150490865,
  "best_structure_counts": {
    "low-tree mixed": 22,
    "shrub-herbaceous": 3
  }
}