# -*- coding: utf-8 -*-
"""
R06_generate_lifeform_candidates.py

Revised feasible candidate-space generation.

Scientific changes:
- No universal Horqin–Otindag species pool.
- q_tree + q_shrub + q_herb = 1 applies only inside vegetated patches.
- Whole-land fractions explicitly retain open land:
      f_tree  = V_target * q_tree
      f_shrub = V_target * q_shrub
      f_herb  = V_target * q_herb
      f_open  = 1 - V_target
- Gates 0–2 do not enter Pareto optimization.
- Gates 3–5 generate life-form candidates.
- Coupled horizontal/vertical feasibility:
      LAI_target / V_target <= LAI_hydro / V_hydro
- No species-level density is calculated here.

Usage:
python R06_generate_lifeform_candidates.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

RATIO_STEP = 0.10
PATCH_EPS = 1e-6

V_LEVELS = {3: 1, 4: 3, 5: 4}
LAI_LEVELS = {3: 3, 4: 4, 5: 4}


def tree_cap(ai: float, gde_level: int, scenario: str = "baseline") -> float:
    """
    Precautionary candidate-screening cap for q_tree.
    It is not the final recommended tree proportion.
    """
    if scenario == "strict":
        max_cap, gde2_cap, gde3_cap = 0.50, 0.10, 0.00
    elif scenario == "relaxed":
        max_cap, gde2_cap, gde3_cap = 0.70, 0.30, 0.20
    else:
        max_cap, gde2_cap, gde3_cap = 0.60, 0.20, 0.10

    climate_cap = float(np.clip(ai - 0.05, 0.0, max_cap))
    cap = climate_cap

    if gde_level == 1:
        cap = 0.0
    elif gde_level == 2:
        cap = min(cap, gde2_cap)
    elif gde_level == 3:
        cap = min(cap, gde3_cap)

    return max(0.0, cap)


def simplex_ratios(step: float, tree_cap_value: float):
    n = int(round(1.0 / step))
    rows = []

    for it in range(n + 1):
        qt = it * step

        if qt > tree_cap_value + 1e-9:
            continue

        for ishrub in range(n - it + 1):
            qs = ishrub * step
            qh = 1.0 - qt - qs

            if qh < -1e-9:
                continue

            rows.append(
                (
                    round(qt, 6),
                    round(qs, 6),
                    round(max(qh, 0.0), 6),
                )
            )

    return rows


def lin_levels(lo: float, hi: float, n: int):
    # Preserve original floating-point endpoints. Do not round here:
    # rounding can move an endpoint by >1e-9 and falsely violate a hard bound.
    lo = float(lo)
    hi = float(max(hi, lo))

    if n <= 1 or abs(hi - lo) < 1e-12:
        return [lo]

    return [float(x) for x in np.linspace(lo, hi, n)]


def lifeform_label(qt, qs, qh):
    if qt <= 1e-9 and qs <= 1e-9:
        return "herbaceous"
    if qt <= 1e-9:
        return "shrub-herbaceous"
    if qt <= 0.20 + 1e-9:
        return "low-tree mixed"
    return "tree-shrub-herbaceous"


def direct_management_label(row):
    gate = int(row["EligibilityGateCode"])

    if gate == 0:
        return "GDE conservation / passive recovery"

    if gate == 1:
        return "Natural sparse/open conservation"

    if gate == 2:
        if bool(row.get("ExistingWoodyContext", False)):
            return "Close-to-nature stand management"
        return "Herbaceous/exclosure passive recovery"

    return ""


def generate_candidates(df):
    candidate_rows = []
    direct_rows = []

    for _, row in df.iterrows():
        gate = int(row["EligibilityGateCode"])
        cc = int(row["ClassCode"])

        # Gates 0–2: direct management; no Pareto candidate generation.
        if gate <= 2:
            direct_rows.append({
                "ClassCode": cc,
                "BaseZone": int(row["BaseZone"]),
                "GDE_Level": int(row["GDE_Level"]),
                "Area_km2": float(row["Area_km2"]),
                "EligibilityGateCode": gate,
                "EligibilityGate": row["EligibilityGate"],
                "DirectManagementPathway": direct_management_label(row),
                "FVC_recent_2022_2024": float(
                    row["FVC_recent_2022_2024"]
                ),
                "V_hydro": float(row["V_hydro"]),
                "LAI_current_3yr": float(row["LAI_current_3yr"]),
                "LAI_safe": float(row["LAI_safe"]),
                "AI_mean": float(row["AI_mean"]),
                "BarrenLandFrac": float(row["BarrenLandFrac"]),
                "ExistingWoodyContext": bool(
                    row["ExistingWoodyContext"]
                ),
                "OptimizationEligible": False,
            })
            continue

        ai = float(row["AI_mean"])
        gde = int(row["GDE_Level"])

        tcap = tree_cap(
            ai,
            gde,
            "baseline",
        )

        q_grid = simplex_ratios(
            RATIO_STEP,
            tcap,
        )

        v_levels = lin_levels(
            float(row["V_candidate_min"]),
            float(row["V_candidate_max"]),
            V_LEVELS[gate],
        )

        lai_levels = lin_levels(
            float(row["LAI_current_3yr"]),
            float(row["LAI_safe"]),
            LAI_LEVELS[gate],
        )

        # Coupled vertical-horizontal hydroclimatic envelope.
        patch_lai_hydro = (
            float(row["LAI_hydro"])
            / max(float(row["V_hydro"]), 0.05)
        )

        class_candidate_id = 0

        for v_target in v_levels:
            for lai_target in lai_levels:

                if lai_target > float(row["LAI_safe"]) + 1e-8:
                    continue

                if v_target < float(row["V_candidate_min"]) - 1e-8:
                    continue

                if v_target > float(row["V_candidate_max"]) + 1e-8:
                    continue

                # Gate 3: no vegetation-footprint expansion.
                if (
                    gate == 3
                    and abs(
                        v_target
                        - float(row["FVC_recent_2022_2024"])
                    ) > 1e-7
                ):
                    continue

                patch_lai = (
                    lai_target
                    / max(v_target, PATCH_EPS)
                )

                if patch_lai > patch_lai_hydro + 1e-8:
                    continue

                for qt, qs, qh in q_grid:
                    class_candidate_id += 1

                    f_tree = v_target * qt
                    f_shrub = v_target * qs
                    f_herb = v_target * qh
                    f_open = 1.0 - v_target

                    candidate_rows.append({
                        "ClassCode": cc,
                        "CandidateID": (
                            f"C{cc:03d}_{class_candidate_id:04d}"
                        ),
                        "BaseZone": int(row["BaseZone"]),
                        "GDE_Level": gde,
                        "Area_km2": float(row["Area_km2"]),
                        "EligibilityGateCode": gate,
                        "EligibilityGate": row["EligibilityGate"],

                        "AI_mean": ai,
                        "AridityClass": row["AridityClass"],
                        "GDE_frac": float(row["GDE_frac"]),
                        "R_gde": float(row["R_gde_baseline"]),

                        "LAI_hydro": float(row["LAI_hydro"]),
                        "LAI_safe": float(row["LAI_safe"]),
                        "LAI_current": float(row["LAI_current_3yr"]),
                        "LAI_target": lai_target,
                        "LAI_increment": (
                            lai_target
                            - float(row["LAI_current_3yr"])
                        ),

                        "V_current": float(
                            row["FVC_recent_2022_2024"]
                        ),
                        "V_hydro": float(row["V_hydro"]),
                        "V_target": v_target,
                        "V_expansion": (
                            v_target
                            - float(row["FVC_recent_2022_2024"])
                        ),

                        # Conditional composition inside vegetation patches.
                        "q_tree": qt,
                        "q_shrub": qs,
                        "q_herb": qh,

                        # Whole-land fractions.
                        "f_tree": f_tree,
                        "f_shrub": f_shrub,
                        "f_herb": f_herb,
                        "f_open": f_open,

                        # LAI partition.
                        "LAI_tree": lai_target * qt,
                        "LAI_shrub": lai_target * qs,
                        "LAI_herb": lai_target * qh,

                        "TreeCap": tcap,
                        "PatchLAI_target": patch_lai,
                        "PatchLAI_hydro_cap": patch_lai_hydro,

                        "LifeFormStructure": lifeform_label(
                            qt, qs, qh
                        ),

                        "OptimizationEligible": True,
                        "SpeciesSpecific": False,
                    })

    return (
        pd.DataFrame(candidate_rows),
        pd.DataFrame(direct_rows),
    )


def main(root: Path):
    root = root.expanduser().resolve()

    input_path = root / "R05_Class_Eligibility.csv"

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    df = pd.read_csv(input_path)

    candidates, direct = generate_candidates(df)

    if candidates.empty:
        raise RuntimeError(
            "No optimization candidates generated."
        )

    candidates["q_sum"] = (
        candidates["q_tree"]
        + candidates["q_shrub"]
        + candidates["q_herb"]
    )

    candidates["land_sum"] = (
        candidates["f_tree"]
        + candidates["f_shrub"]
        + candidates["f_herb"]
        + candidates["f_open"]
    )

    v_violation = (
        (
            candidates["V_target"]
            > candidates["V_hydro"] + 1e-9
        )
        & candidates["EligibilityGateCode"].isin([4, 5])
    )

    qa = {
        "input_classcodes": int(
            df["ClassCode"].nunique()
        ),
        "candidate_rows": int(
            len(candidates)
        ),
        "optimized_classcodes": int(
            candidates["ClassCode"].nunique()
        ),
        "direct_management_classcodes": int(
            direct["ClassCode"].nunique()
        ),
        "duplicate_candidate_ids": int(
            candidates["CandidateID"]
            .duplicated()
            .sum()
        ),
        "q_sum_failure_n": int(
            (
                ~np.isclose(
                    candidates["q_sum"],
                    1.0,
                    atol=1e-8,
                )
            ).sum()
        ),
        "land_fraction_sum_failure_n": int(
            (
                ~np.isclose(
                    candidates["land_sum"],
                    1.0,
                    atol=1e-8,
                )
            ).sum()
        ),
        "LAI_safe_violation_n": int(
            (
                candidates["LAI_target"]
                > candidates["LAI_safe"] + 1e-9
            ).sum()
        ),
        "V_max_violation_n": int(
            v_violation.sum()
        ),
        "PatchLAI_violation_n": int(
            (
                candidates["PatchLAI_target"]
                > candidates["PatchLAI_hydro_cap"] + 1e-9
            ).sum()
        ),
        "TreeCap_violation_n": int(
            (
                candidates["q_tree"]
                > candidates["TreeCap"] + 1e-9
            ).sum()
        ),
        "candidates_in_gate0_2_n": int(
            candidates["EligibilityGateCode"]
            .isin([0, 1, 2])
            .sum()
        ),
    }

    summary = (
        candidates
        .groupby("ClassCode", as_index=False)
        .agg(
            BaseZone=("BaseZone", "first"),
            GDE_Level=("GDE_Level", "first"),
            EligibilityGateCode=(
                "EligibilityGateCode", "first"
            ),
            EligibilityGate=(
                "EligibilityGate", "first"
            ),
            n_candidates=("CandidateID", "size"),
            TreeCap=("TreeCap", "first"),
            V_target_min=("V_target", "min"),
            V_target_max=("V_target", "max"),
            LAI_target_min=("LAI_target", "min"),
            LAI_target_max=("LAI_target", "max"),
            q_tree_min=("q_tree", "min"),
            q_tree_max=("q_tree", "max"),
            q_shrub_min=("q_shrub", "min"),
            q_shrub_max=("q_shrub", "max"),
            q_herb_min=("q_herb", "min"),
            q_herb_max=("q_herb", "max"),
            f_open_min=("f_open", "min"),
            f_open_max=("f_open", "max"),
        )
        .sort_values("ClassCode")
    )

    # Tree-cap sensitivity.
    sens_rows = []

    for scenario in [
        "strict",
        "baseline",
        "relaxed",
    ]:
        for _, row in df[
            df["EligibilityGateCode"].isin([3, 4, 5])
        ].iterrows():

            cap = tree_cap(
                float(row["AI_mean"]),
                int(row["GDE_Level"]),
                scenario,
            )

            n_structures = len(
                simplex_ratios(
                    RATIO_STEP,
                    cap,
                )
            )

            sens_rows.append({
                "Scenario": scenario,
                "ClassCode": int(row["ClassCode"]),
                "BaseZone": int(row["BaseZone"]),
                "GDE_Level": int(row["GDE_Level"]),
                "EligibilityGateCode": int(
                    row["EligibilityGateCode"]
                ),
                "AI_mean": float(row["AI_mean"]),
                "TreeCap": cap,
                "n_lifeform_structures": n_structures,
            })

    sensitivity = pd.DataFrame(sens_rows)

    out_candidates = root / "R06_CandidateLibrary.csv"
    out_direct = root / "R06_DirectManagement.csv"
    out_summary = root / "R06_CandidateSummary_ByClass.csv"
    out_sensitivity = root / "R06_TreeCap_Sensitivity.csv"
    out_qa = root / "R06_QA.json"
    out_readme = root / "R06_README.txt"

    candidates.drop(
        columns=["q_sum", "land_sum"]
    ).to_csv(
        out_candidates,
        index=False,
        encoding="utf-8-sig",
    )

    direct.to_csv(
        out_direct,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        out_summary,
        index=False,
        encoding="utf-8-sig",
    )

    sensitivity.to_csv(
        out_sensitivity,
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
{RATIO_STEP}

Baseline precautionary tree-cap screen:
climate cap = clip(AI - 0.05, 0, 0.60)
GDE level 2: q_tree <= 0.20
GDE level 3: q_tree <= 0.10

Coupled vertical-horizontal constraint:
LAI_target / V_target <= LAI_hydro / V_hydro

No species names and no species-specific density values are generated.

QA:
{json.dumps(qa, ensure_ascii=False, indent=2)}
""".strip()

    out_readme.write_text(
        readme,
        encoding="utf-8",
    )

    print("\nR06 completed successfully.")
    print("\nQA:")
    print(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\nCandidate counts by eligibility gate:")
    print(
        candidates.groupby(
            "EligibilityGateCode"
        )["CandidateID"]
        .count()
        .to_string()
    )

    print("\nDirect-management pathways:")
    print(
        direct["DirectManagementPathway"]
        .value_counts()
        .to_string()
    )

    print("\nCreated:")
    for p in [
        out_candidates,
        out_direct,
        out_summary,
        out_sensitivity,
        out_qa,
        out_readme,
    ]:
        print(" -", p.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R05_Class_Eligibility.csv",
    )

    args = parser.parse_args()

    main(
        Path(args.root)
    )
