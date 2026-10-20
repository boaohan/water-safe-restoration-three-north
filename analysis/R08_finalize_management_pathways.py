# -*- coding: utf-8 -*-
"""
R08_finalize_management_pathways.py

Purpose
-------
Merge:
- 33 direct-management ClassCodes from R06
- 25 Pareto-optimized ClassCodes from R07

into one final 58-ClassCode management table and regional area summaries.

Final pathway taxonomy
----------------------
1. GDE conservation / passive recovery
2. Natural sparse/open conservation
3. Herbaceous/exclosure passive recovery
4. Close-to-nature structural management
5. Shrub-herbaceous restoration
6. Low-tree mixed restoration

Important:
- Gate 3 is "structural management only", even if its selected target structure
  contains a small tree component. It is NOT counted as new tree-involved
  restoration because vegetation footprint expansion is prohibited.
- Gates 4–5 are the only footprint-expansion restoration classes.
- The revised "Low-tree mixed restoration" area is therefore the closest
  management analogue to the old manuscript's large tree-shrub-grass
  restoration area, but the definitions are not identical.

Usage:
python R08_finalize_management_pathways.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd


OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT = 76.50


def aridity_class(ai):
    if pd.isna(ai):
        return "missing"
    if ai < 0.05:
        return "hyper-arid"
    if ai < 0.20:
        return "arid"
    if ai < 0.50:
        return "semi-arid"
    if ai < 0.65:
        return "dry sub-humid"
    return "humid/sub-humid"


def weighted_mean(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(w) & (w >= 0)
    x, w = x[ok], w[ok]
    if len(x) == 0 or w.sum() <= 0:
        return np.nan
    return float(np.average(x, weights=w))


def weighted_median(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    ok = np.isfinite(x) & np.isfinite(w) & (w >= 0)
    x, w = x[ok], w[ok]
    if len(x) == 0 or w.sum() <= 0:
        return np.nan
    idx = np.argsort(x)
    x, w = x[idx], w[idx]
    return float(x[np.cumsum(w) >= 0.5 * w.sum()][0])


def pareto_confidence(x):
    if pd.isna(x):
        return "direct rule"
    if x >= 0.80:
        return "high"
    if x >= 0.50:
        return "moderate"
    return "low"


def main(root: Path):
    root = root.expanduser().resolve()

    direct_path = root / "R06_DirectManagement.csv"
    best_path = root / "R07_BestCompromise.csv"
    weight_path = root / "R07_WeightSensitivity.csv"

    missing = [
        str(p)
        for p in [direct_path, best_path, weight_path]
        if not p.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing required files:\n" + "\n".join(missing)
        )

    direct = pd.read_csv(direct_path)
    best = pd.read_csv(best_path)
    weights = pd.read_csv(weight_path)

    # ---------------------------------------------------------
    # 1. Direct-management classes
    # ---------------------------------------------------------
    direct_final = direct.copy()

    direct_final["FinalManagementPathway"] = (
        direct_final["DirectManagementPathway"]
    )

    direct_final["InterventionIntensity"] = np.select(
        [
            direct_final["EligibilityGateCode"] == 0,
            direct_final["EligibilityGateCode"] == 1,
            direct_final["EligibilityGateCode"] == 2,
        ],
        [
            "conservation",
            "conservation",
            "passive",
        ],
        default="direct",
    )

    direct_final["SelectionBasis"] = "direct eligibility rule"
    direct_final["TargetLifeFormStructure"] = np.nan

    # Candidate-specific fields do not exist for direct pathways.
    for col in [
        "CandidateID",
        "q_tree",
        "q_shrub",
        "q_herb",
        "V_target",
        "LAI_target",
        "f_tree",
        "f_shrub",
        "f_herb",
        "f_open",
        "best_compromise_score",
    ]:
        direct_final[col] = np.nan

    # ---------------------------------------------------------
    # 2. Pareto-optimized classes
    # ---------------------------------------------------------
    opt = best.copy()

    opt["SelectionBasis"] = "Pareto best compromise"
    opt["TargetLifeFormStructure"] = opt["LifeFormStructure"]

    opt["InterventionIntensity"] = opt["EligibilityGateCode"].map(
        {
            3: "structural",
            4: "limited expansion",
            5: "active expansion",
        }
    )

    # Gate 3 remains management of the existing footprint.
    opt["FinalManagementPathway"] = np.where(
        opt["EligibilityGateCode"] == 3,
        "Close-to-nature structural management",
        np.where(
            opt["q_tree"] > 1e-9,
            "Low-tree mixed restoration",
            "Shrub-herbaceous restoration",
        ),
    )

    # ---------------------------------------------------------
    # 3. Attach Dirichlet sensitivity to optimized rows
    # ---------------------------------------------------------
    wdir = weights[
        weights["Scenario"] == "Dirichlet1000_summary"
    ][
        [
            "ClassCode",
            "matches_equal_candidate",
            "matches_equal_structure",
            "matches_equal_tree_presence",
            "q_tree_p05",
            "q_tree_p95",
            "V_target_p05",
            "V_target_p95",
            "LAI_target_p05",
            "LAI_target_p95",
        ]
    ].copy()

    for c in [
        "matches_equal_candidate",
        "matches_equal_structure",
        "matches_equal_tree_presence",
        "q_tree_p05",
        "q_tree_p95",
        "V_target_p05",
        "V_target_p95",
        "LAI_target_p05",
        "LAI_target_p95",
    ]:
        wdir[c] = pd.to_numeric(
            wdir[c],
            errors="coerce",
        )

    opt = opt.merge(
        wdir,
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    opt["ParetoDecisionConfidence"] = opt[
        "matches_equal_structure"
    ].map(pareto_confidence)

    # ---------------------------------------------------------
    # 4. Harmonize columns and combine 58 ClassCodes
    # ---------------------------------------------------------
    direct_keep = [
        "ClassCode",
        "BaseZone",
        "GDE_Level",
        "Area_km2",
        "EligibilityGateCode",
        "EligibilityGate",
        "AI_mean",
        "BarrenLandFrac",
        "ExistingWoodyContext",
        "SelectionBasis",
        "FinalManagementPathway",
        "InterventionIntensity",
        "TargetLifeFormStructure",
        "CandidateID",
        "q_tree",
        "q_shrub",
        "q_herb",
        "V_target",
        "LAI_target",
        "f_tree",
        "f_shrub",
        "f_herb",
        "f_open",
        "best_compromise_score",
    ]

    for c in direct_keep:
        if c not in direct_final.columns:
            direct_final[c] = np.nan

    opt_keep = direct_keep.copy()

    # Optimized table may not contain these direct-context columns.
    for c in opt_keep:
        if c not in opt.columns:
            opt[c] = np.nan

    direct_h = direct_final[direct_keep].copy()
    opt_h = opt[opt_keep].copy()

    final = pd.concat(
        [direct_h, opt_h],
        ignore_index=True,
    ).sort_values("ClassCode").reset_index(drop=True)

    if len(final) != 58 or final["ClassCode"].nunique() != 58:
        raise RuntimeError(
            f"Expected 58 final ClassCodes; got rows={len(final)}, "
            f"unique={final['ClassCode'].nunique()}"
        )

    # Reattach Pareto sensitivity columns after harmonization.
    sens_cols = [
        "ClassCode",
        "matches_equal_candidate",
        "matches_equal_structure",
        "matches_equal_tree_presence",
        "q_tree_p05",
        "q_tree_p95",
        "V_target_p05",
        "V_target_p95",
        "LAI_target_p05",
        "LAI_target_p95",
        "ParetoDecisionConfidence",
    ]

    opt_sens = opt[sens_cols].copy()

    final = final.merge(
        opt_sens,
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    final["ParetoDecisionConfidence"] = final[
        "ParetoDecisionConfidence"
    ].fillna("direct rule")

    final["AridityClass"] = final["AI_mean"].map(
        aridity_class
    )

    # ---------------------------------------------------------
    # 5. Regional management summary
    # ---------------------------------------------------------
    total_area = final["Area_km2"].sum()

    management_summary = (
        final
        .groupby(
            "FinalManagementPathway",
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
        )
    )

    management_summary["Area_share_pct"] = (
        management_summary["Area_km2"]
        / total_area
        * 100.0
    )

    management_summary = management_summary.sort_values(
        "Area_share_pct",
        ascending=False,
    )

    # ---------------------------------------------------------
    # 6. Intervention-intensity summary
    # ---------------------------------------------------------
    intervention_summary = (
        final
        .groupby(
            "InterventionIntensity",
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
        )
    )

    intervention_summary["Area_share_pct"] = (
        intervention_summary["Area_km2"]
        / total_area
        * 100.0
    )

    intervention_summary = intervention_summary.sort_values(
        "Area_share_pct",
        ascending=False,
    )

    # ---------------------------------------------------------
    # 7. Management by GDE level
    # ---------------------------------------------------------
    gde_summary = (
        final
        .groupby(
            [
                "GDE_Level",
                "FinalManagementPathway",
            ],
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
        )
    )

    gde_totals = (
        final.groupby("GDE_Level")["Area_km2"]
        .sum()
        .rename("GDE_total_area_km2")
    )

    gde_summary = gde_summary.merge(
        gde_totals,
        on="GDE_Level",
        how="left",
    )

    gde_summary["Within_GDE_Level_pct"] = (
        gde_summary["Area_km2"]
        / gde_summary["GDE_total_area_km2"]
        * 100.0
    )

    # ---------------------------------------------------------
    # 8. Management by aridity
    # ---------------------------------------------------------
    aridity_summary = (
        final
        .groupby(
            [
                "AridityClass",
                "FinalManagementPathway",
            ],
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
        )
    )

    aridity_totals = (
        final.groupby("AridityClass")["Area_km2"]
        .sum()
        .rename("Aridity_total_area_km2")
    )

    aridity_summary = aridity_summary.merge(
        aridity_totals,
        on="AridityClass",
        how="left",
    )

    aridity_summary["Within_Aridity_pct"] = (
        aridity_summary["Area_km2"]
        / aridity_summary["Aridity_total_area_km2"]
        * 100.0
    )

    # ---------------------------------------------------------
    # 9. Optimized restoration-structure summary
    # ---------------------------------------------------------
    restoration = final[
        final["FinalManagementPathway"].isin(
            [
                "Low-tree mixed restoration",
                "Shrub-herbaceous restoration",
            ]
        )
    ].copy()

    restoration_stats = pd.DataFrame(
        [
            {
                "Metric": "restoration_area_km2",
                "Value": float(
                    restoration["Area_km2"].sum()
                ),
            },
            {
                "Metric": "restoration_area_share_pct",
                "Value": float(
                    restoration["Area_km2"].sum()
                    / total_area
                    * 100
                ),
            },
            {
                "Metric": "area_weighted_mean_q_tree",
                "Value": weighted_mean(
                    restoration["q_tree"],
                    restoration["Area_km2"],
                ),
            },
            {
                "Metric": "area_weighted_mean_whole_land_tree_fraction",
                "Value": weighted_mean(
                    restoration["f_tree"],
                    restoration["Area_km2"],
                ),
            },
            {
                "Metric": "area_weighted_mean_open_fraction",
                "Value": weighted_mean(
                    restoration["f_open"],
                    restoration["Area_km2"],
                ),
            },
            {
                "Metric": "area_weighted_mean_V_target",
                "Value": weighted_mean(
                    restoration["V_target"],
                    restoration["Area_km2"],
                ),
            },
            {
                "Metric": "area_weighted_mean_LAI_target",
                "Value": weighted_mean(
                    restoration["LAI_target"],
                    restoration["Area_km2"],
                ),
            },
        ]
    )

    # ---------------------------------------------------------
    # 10. Old vs revised headline comparison
    # ---------------------------------------------------------
    revised_tree_active = final[
        final["FinalManagementPathway"]
        == "Low-tree mixed restoration"
    ]["Area_km2"].sum() / total_area * 100.0

    comparison = pd.DataFrame(
        [
            {
                "Metric": "Tree-involved active/limited restoration area share",
                "Submitted_manuscript_pct": OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT,
                "Revised_framework_pct": float(
                    revised_tree_active
                ),
                "Difference_percentage_points": float(
                    revised_tree_active
                    - OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT
                ),
                "Interpretation": (
                    "Definitions are not identical. The submitted value was "
                    "tree-shrub-grass restoration across the old 208-unit "
                    "workflow; the revised value counts only gates 4-5 with "
                    "a tree component after eligibility, sparse/open, safe-LAI "
                    "and occupancy constraints."
                ),
            }
        ]
    )

    # ---------------------------------------------------------
    # 11. Pareto confidence summary
    # ---------------------------------------------------------
    optimized_final = final[
        final["SelectionBasis"] == "Pareto best compromise"
    ].copy()

    confidence_summary = (
        optimized_final
        .groupby(
            "ParetoDecisionConfidence",
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
        )
    )

    confidence_summary["Share_of_optimized_area_pct"] = (
        confidence_summary["Area_km2"]
        / optimized_final["Area_km2"].sum()
        * 100.0
    )

    # ---------------------------------------------------------
    # 12. QA
    # ---------------------------------------------------------
    qa = {
        "rows": int(len(final)),
        "unique_classcodes": int(
            final["ClassCode"].nunique()
        ),
        "total_area_km2": float(total_area),
        "missing_final_pathway": int(
            final["FinalManagementPathway"]
            .isna()
            .sum()
        ),
        "optimized_rows": int(
            (
                final["SelectionBasis"]
                == "Pareto best compromise"
            ).sum()
        ),
        "direct_rows": int(
            (
                final["SelectionBasis"]
                == "direct eligibility rule"
            ).sum()
        ),
        "revised_tree_involved_restoration_area_share_pct": float(
            revised_tree_active
        ),
        "old_manuscript_tree_shrub_grass_pct": float(
            OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT
        ),
        "difference_percentage_points": float(
            revised_tree_active
            - OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT
        ),
        "active_plus_limited_expansion_area_share_pct": float(
            final.loc[
                final["InterventionIntensity"].isin(
                    [
                        "active expansion",
                        "limited expansion",
                    ]
                ),
                "Area_km2",
            ].sum()
            / total_area
            * 100.0
        ),
        "conservation_plus_passive_area_share_pct": float(
            final.loc[
                final["InterventionIntensity"].isin(
                    [
                        "conservation",
                        "passive",
                    ]
                ),
                "Area_km2",
            ].sum()
            / total_area
            * 100.0
        ),
        "structural_management_area_share_pct": float(
            final.loc[
                final["InterventionIntensity"]
                == "structural",
                "Area_km2",
            ].sum()
            / total_area
            * 100.0
        ),
    }

    # ---------------------------------------------------------
    # 13. Export
    # ---------------------------------------------------------
    out_final = root / "R08_FinalManagement_ByClass.csv"
    out_management = root / "R08_Management_AreaSummary.csv"
    out_intensity = root / "R08_InterventionIntensity_Summary.csv"
    out_gde = root / "R08_Management_ByGDE.csv"
    out_aridity = root / "R08_Management_ByAridity.csv"
    out_restoration = root / "R08_RestorationStructure_Stats.csv"
    out_compare = root / "R08_SubmittedVsRevised_Headline.csv"
    out_conf = root / "R08_ParetoConfidence_Summary.csv"
    out_qa = root / "R08_QA.json"
    out_readme = root / "R08_README.txt"

    final.to_csv(
        out_final,
        index=False,
        encoding="utf-8-sig",
    )

    management_summary.to_csv(
        out_management,
        index=False,
        encoding="utf-8-sig",
    )

    intervention_summary.to_csv(
        out_intensity,
        index=False,
        encoding="utf-8-sig",
    )

    gde_summary.to_csv(
        out_gde,
        index=False,
        encoding="utf-8-sig",
    )

    aridity_summary.to_csv(
        out_aridity,
        index=False,
        encoding="utf-8-sig",
    )

    restoration_stats.to_csv(
        out_restoration,
        index=False,
        encoding="utf-8-sig",
    )

    comparison.to_csv(
        out_compare,
        index=False,
        encoding="utf-8-sig",
    )

    confidence_summary.to_csv(
        out_conf,
        index=False,
        encoding="utf-8-sig",
    )

    out_qa.write_text(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    readme = f"""
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
{management_summary.to_string(index=False)}

Intervention-intensity summary:
{intervention_summary.to_string(index=False)}

Restoration-structure statistics:
{restoration_stats.to_string(index=False)}

Headline comparison:
Submitted manuscript tree-shrub-grass restoration = {OLD_MANUSCRIPT_TREE_SHRUB_GRASS_PCT:.2f}%
Revised tree-involved active/limited restoration = {revised_tree_active:.2f}%

The two percentages are not strictly identical definitions and should not be
presented as a direct before/after treatment effect. They document how the
revised framework changes the management interpretation after explicit
eligibility, sparse/open, occupancy, safe-LAI, and GDE constraints.

QA:
{json.dumps(qa, ensure_ascii=False, indent=2)}
""".strip()

    out_readme.write_text(
        readme,
        encoding="utf-8",
    )

    print("\nR08 completed successfully.")

    print("\nFinal management area summary:")
    print(
        management_summary.to_string(
            index=False
        )
    )

    print("\nIntervention intensity:")
    print(
        intervention_summary.to_string(
            index=False
        )
    )

    print("\nRestoration structure stats:")
    print(
        restoration_stats.to_string(
            index=False
        )
    )

    print("\nHeadline comparison:")
    print(
        comparison.to_string(
            index=False
        )
    )

    print("\nQA:")
    print(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\nCreated:")
    for p in [
        out_final,
        out_management,
        out_intensity,
        out_gde,
        out_aridity,
        out_restoration,
        out_compare,
        out_conf,
        out_qa,
        out_readme,
    ]:
        print(" -", p.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R06 direct management and R07 outputs",
    )

    args = parser.parse_args()

    main(
        Path(args.root)
    )
