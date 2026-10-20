# -*- coding: utf-8 -*-
"""
R05_active_restoration_eligibility.py

Purpose
-------
Separate "whether active restoration is justified" from "how to restore".

This script does NOT assign the final tree/shrub/herb management category.
It creates a management gate using:
- GDE conservation status
- natural sparse/open-land status
- LAI headroom
- vegetation-footprint headroom
- current land-cover context

Baseline gate
-------------
0  GDE conservation / no active expansion
1  Natural sparse/open conservation
2  No additional canopy headroom
3  Structural management only
4  Limited footprint expansion
5  Active footprint expansion eligible

Interpretation
--------------
- "Structural management only" means composition/density may be adjusted within
  the existing vegetation footprint, but the vegetation footprint should not expand.
- "Limited footprint expansion" means both LAI and occupancy headroom exist,
  but the smaller relative headroom is < 0.10.
- "Active footprint expansion eligible" means both headrooms exist and the
  smaller relative headroom is >= 0.10.
- These are eligibility gates, NOT final planting prescriptions.

Usage
-----
python R05_active_restoration_eligibility.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Baseline thresholds
# ---------------------------------------------------------------------
SPARSE_VHYDRO_THRESHOLD = 0.15
SPARSE_BARREN_THRESHOLD = 0.50

LAI_HEADROOM_ABS_MIN = 0.05
LAI_HEADROOM_REL_MIN = 0.05

V_HEADROOM_ABS_MIN = 0.005

ACTIVE_EXPANSION_SCORE_THRESHOLD = 0.10

# Existing woody-context diagnostic only (not a hard gate).
EXISTING_WOODY_THRESHOLD = 0.20


def weighted_median(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)

    ok = np.isfinite(values) & np.isfinite(weights) & (weights >= 0)
    values = values[ok]
    weights = weights[ok]

    if len(values) == 0 or weights.sum() <= 0:
        return np.nan

    order = np.argsort(values)
    values = values[order]
    weights = weights[order]

    cutoff = 0.5 * weights.sum()
    return float(values[np.cumsum(weights) >= cutoff][0])


def build_gate(
    df,
    sparse_v_thr=SPARSE_VHYDRO_THRESHOLD,
    sparse_barren_thr=SPARSE_BARREN_THRESHOLD,
    lai_abs_min=LAI_HEADROOM_ABS_MIN,
    lai_rel_min=LAI_HEADROOM_REL_MIN,
    v_abs_min=V_HEADROOM_ABS_MIN,
    active_score_thr=ACTIVE_EXPANSION_SCORE_THRESHOLD,
):
    out = df.copy()

    out["LAI_headroom_rel"] = np.where(
        out["LAI_safe"] > 0,
        out["LAI_headroom"] / out["LAI_safe"],
        0.0,
    )

    out["V_headroom_rel"] = np.where(
        out["V_hydro"] > 0,
        out["V_headroom"] / out["V_hydro"],
        0.0,
    )

    out["ExpansionCapacityScore"] = np.minimum(
        out["LAI_headroom_rel"].clip(lower=0),
        out["V_headroom_rel"].clip(lower=0),
    )

    out["NaturalSparseOpen_baseline"] = (
        (out["V_hydro"] < sparse_v_thr)
        & (out["BarrenLandFrac"] >= sparse_barren_thr)
    )

    out["Meaningful_LAI_headroom"] = (
        (out["LAI_headroom"] >= lai_abs_min)
        & (out["LAI_headroom_rel"] >= lai_rel_min)
    )

    out["Meaningful_V_headroom"] = (
        out["V_headroom"] >= v_abs_min
    )

    gate_code = np.full(len(out), 5, dtype=int)
    gate_name = np.full(
        len(out),
        "Active footprint expansion eligible",
        dtype=object,
    )

    # Lowest-priority assignment first, then overwrite with stricter gates.
    limited = (
        out["Meaningful_LAI_headroom"]
        & out["Meaningful_V_headroom"]
        & (out["ExpansionCapacityScore"] < active_score_thr)
    )
    gate_code[limited] = 4
    gate_name[limited] = "Limited footprint expansion"

    structural = (
        out["Meaningful_LAI_headroom"]
        & (~out["Meaningful_V_headroom"])
    )
    gate_code[structural] = 3
    gate_name[structural] = "Structural management only"

    no_lai = ~out["Meaningful_LAI_headroom"]
    gate_code[no_lai] = 2
    gate_name[no_lai] = "No additional canopy headroom"

    sparse = out["NaturalSparseOpen_baseline"]
    gate_code[sparse] = 1
    gate_name[sparse] = "Natural sparse/open conservation"

    # Hardest conservation gate has final precedence.
    gde_core = out["GDE_Level"] == 1
    gate_code[gde_core] = 0
    gate_name[gde_core] = "GDE conservation / no active expansion"

    out["EligibilityGateCode"] = gate_code
    out["EligibilityGate"] = gate_name

    out["ActiveExpansionEligible"] = (
        out["EligibilityGateCode"] == 5
    )

    out["AnyFootprintExpansionAllowed"] = (
        out["EligibilityGateCode"].isin([4, 5])
    )

    out["ExistingFootprintManagementOnly"] = (
        out["EligibilityGateCode"] == 3
    )

    return out


def area_summary(df):
    rows = []
    total = df["Area_km2"].sum()

    for (code, name), g in df.groupby(
        ["EligibilityGateCode", "EligibilityGate"],
        sort=True,
    ):
        rows.append({
            "EligibilityGateCode": int(code),
            "EligibilityGate": name,
            "n_ClassCode": int(len(g)),
            "Area_km2": float(g["Area_km2"].sum()),
            "Area_share_pct": float(g["Area_km2"].sum() / total * 100),
            "median_AI": float(g["AI_mean"].median()),
            "median_LAI_headroom": float(g["LAI_headroom"].median()),
            "median_V_headroom": float(g["V_headroom"].median()),
            "median_ExpansionCapacityScore": float(
                g["ExpansionCapacityScore"].median()
            ),
            "area_weighted_median_safe_ratio": weighted_median(
                g["safe_ratio"], g["Area_km2"]
            ),
        })

    return pd.DataFrame(rows).sort_values("EligibilityGateCode")


def main(root: Path):
    root = root.expanduser().resolve()

    r04_path = root / "R04_Class_LAIsafe.csv"
    static_path = root / "R01B1_Static_ByClass_FINAL.csv"

    missing = [str(p) for p in [r04_path, static_path] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required files:\n"
            + "\n".join(missing)
            + "\n\nPut R04 outputs in the same root folder."
        )

    r04 = pd.read_csv(r04_path)
    static = pd.read_csv(static_path)

    add_cols = [
        "ClassCode",
        "CroplandFrac",
        "PermanentWaterFrac",
        "NaturalFrac",
        "ForestLandFrac",
        "ShrubLandFrac",
        "SavannaLandFrac",
        "GrassLandFrac",
        "BarrenLandFrac",
        "SW_occurrence_landmean_pct",
    ]

    df = r04.merge(
        static[add_cols],
        on="ClassCode",
        how="left",
        validate="one_to_one",
        suffixes=("", "_static"),
    )

    if len(df) != 58 or df["ClassCode"].nunique() != 58:
        raise RuntimeError(
            f"Expected 58 ClassCodes, got rows={len(df)}, "
            f"unique={df['ClassCode'].nunique()}"
        )

    # Land-cover context diagnostics.
    df["WoodyLandFrac"] = (
        df["ForestLandFrac"]
        + df["ShrubLandFrac"]
        + df["SavannaLandFrac"]
    ).clip(0, 1)

    df["ExistingWoodyContext"] = (
        df["WoodyLandFrac"] >= EXISTING_WOODY_THRESHOLD
    )

    # Baseline gate.
    out = build_gate(df)

    # -----------------------------------------------------------------
    # Gate-specific candidate constraints for R06
    # -----------------------------------------------------------------
    # v_min / v_max define the admissible vegetation-footprint range.
    # LAI_target_max defines the canopy upper boundary for candidate generation.
    #
    # No final tree/shrub/herb proportions are assigned here.
    # -----------------------------------------------------------------

    out["V_candidate_min"] = out["FVC_recent_2022_2024"].clip(0, 1)
    out["V_candidate_max"] = out["FVC_recent_2022_2024"].clip(0, 1)
    out["LAI_target_max"] = out["LAI_current_3yr"]

    # Active / limited footprint expansion:
    can_expand = out["EligibilityGateCode"].isin([4, 5])
    out.loc[can_expand, "V_candidate_max"] = np.maximum(
        out.loc[can_expand, "FVC_recent_2022_2024"],
        out.loc[can_expand, "V_hydro"],
    )
    out.loc[can_expand, "LAI_target_max"] = out.loc[
        can_expand, "LAI_safe"
    ]

    # Structural-management-only:
    # footprint stays fixed, but canopy may change up to safe LAI.
    structural = out["EligibilityGateCode"] == 3
    out.loc[structural, "LAI_target_max"] = out.loc[
        structural, "LAI_safe"
    ]

    # No additional canopy headroom:
    # do not generate candidates above current canopy.
    no_lai = out["EligibilityGateCode"] == 2
    out.loc[no_lai, "LAI_target_max"] = np.minimum(
        out.loc[no_lai, "LAI_current_3yr"],
        out.loc[no_lai, "LAI_safe"],
    )

    # Natural sparse/open:
    # maintain present sparse footprint; no active expansion.
    sparse = out["EligibilityGateCode"] == 1
    out.loc[sparse, "V_candidate_min"] = out.loc[
        sparse, "FVC_recent_2022_2024"
    ]
    out.loc[sparse, "V_candidate_max"] = out.loc[
        sparse, "FVC_recent_2022_2024"
    ]
    out.loc[sparse, "LAI_target_max"] = np.minimum(
        out.loc[sparse, "LAI_current_3yr"],
        out.loc[sparse, "LAI_safe"],
    )

    # GDE-dominated conservation:
    # no artificial expansion; R06 will not create active planting candidates.
    core = out["EligibilityGateCode"] == 0
    out.loc[core, "V_candidate_min"] = out.loc[
        core, "FVC_recent_2022_2024"
    ]
    out.loc[core, "V_candidate_max"] = out.loc[
        core, "FVC_recent_2022_2024"
    ]
    out.loc[core, "LAI_target_max"] = np.minimum(
        out.loc[core, "LAI_current_3yr"],
        out.loc[core, "LAI_safe"],
    )

    out["V_candidate_range"] = np.maximum(
        out["V_candidate_max"] - out["V_candidate_min"],
        0.0,
    )

    # -----------------------------------------------------------------
    # Baseline summary
    # -----------------------------------------------------------------
    summary = area_summary(out)

    # -----------------------------------------------------------------
    # Sensitivity of eligibility gates
    # -----------------------------------------------------------------
    sens_rows = []

    # 1) Active expansion score threshold
    for score_thr in [0.05, 0.10, 0.15]:
        temp = build_gate(
            df,
            active_score_thr=score_thr,
        )

        total_area = temp["Area_km2"].sum()

        for code in [0, 1, 2, 3, 4, 5]:
            g = temp[temp["EligibilityGateCode"] == code]
            sens_rows.append({
                "SensitivityType": "active_score_threshold",
                "ParameterA": score_thr,
                "ParameterB": np.nan,
                "EligibilityGateCode": code,
                "EligibilityGate": (
                    g["EligibilityGate"].iloc[0]
                    if len(g) else ""
                ),
                "n_ClassCode": int(len(g)),
                "Area_km2": float(g["Area_km2"].sum()),
                "Area_share_pct": float(
                    g["Area_km2"].sum() / total_area * 100
                ),
            })

    # 2) Sparse/open thresholds
    for v_thr in [0.10, 0.15, 0.20]:
        for barren_thr in [0.40, 0.50, 0.60]:
            temp = build_gate(
                df,
                sparse_v_thr=v_thr,
                sparse_barren_thr=barren_thr,
            )

            total_area = temp["Area_km2"].sum()

            sparse_g = temp[
                temp["EligibilityGateCode"] == 1
            ]

            sens_rows.append({
                "SensitivityType": "sparse_open_threshold",
                "ParameterA": v_thr,
                "ParameterB": barren_thr,
                "EligibilityGateCode": 1,
                "EligibilityGate": "Natural sparse/open conservation",
                "n_ClassCode": int(len(sparse_g)),
                "Area_km2": float(sparse_g["Area_km2"].sum()),
                "Area_share_pct": float(
                    sparse_g["Area_km2"].sum() / total_area * 100
                ),
            })

    sensitivity = pd.DataFrame(sens_rows)

    # -----------------------------------------------------------------
    # QA
    # -----------------------------------------------------------------
    total_area = float(out["Area_km2"].sum())

    qa = {
        "rows": int(len(out)),
        "unique_classcodes": int(out["ClassCode"].nunique()),
        "missing_gate": int(out["EligibilityGate"].isna().sum()),
        "total_area_km2": total_area,
        "active_expansion_n": int(
            (out["EligibilityGateCode"] == 5).sum()
        ),
        "active_expansion_area_km2": float(
            out.loc[
                out["EligibilityGateCode"] == 5,
                "Area_km2",
            ].sum()
        ),
        "active_expansion_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 5,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "limited_expansion_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 4,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "structural_only_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 3,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "no_canopy_headroom_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 2,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "natural_sparse_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 1,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "gde_conservation_area_share_pct": float(
            out.loc[
                out["EligibilityGateCode"] == 0,
                "Area_km2",
            ].sum()
            / total_area
            * 100
        ),
        "V_candidate_max_below_min_n": int(
            (out["V_candidate_max"] < out["V_candidate_min"]).sum()
        ),
        "LAI_target_max_negative_n": int(
            (out["LAI_target_max"] < 0).sum()
        ),
    }

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------
    out_class = root / "R05_Class_Eligibility.csv"
    out_summary = root / "R05_Eligibility_AreaSummary.csv"
    out_sens = root / "R05_Eligibility_Sensitivity.csv"
    out_qa = root / "R05_QA.json"
    out_readme = root / "R05_README.txt"

    out.to_csv(
        out_class,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        out_summary,
        index=False,
        encoding="utf-8-sig",
    )

    sensitivity.to_csv(
        out_sens,
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
    V_hydro < {SPARSE_VHYDRO_THRESHOLD}
    AND BarrenLandFrac >= {SPARSE_BARREN_THRESHOLD}
- Meaningful LAI headroom:
    LAI_headroom >= {LAI_HEADROOM_ABS_MIN}
    AND LAI_headroom / LAI_safe >= {LAI_HEADROOM_REL_MIN}
- Meaningful vegetation-footprint headroom:
    V_headroom >= {V_HEADROOM_ABS_MIN}
- Active-expansion capacity:
    min(relative LAI headroom, relative V headroom) >=
    {ACTIVE_EXPANSION_SCORE_THRESHOLD}

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
{json.dumps(qa, ensure_ascii=False, indent=2)}

Baseline area summary:
{summary.to_string(index=False)}
""".strip()

    out_readme.write_text(
        readme,
        encoding="utf-8",
    )

    print("\nR05 completed successfully.")
    print(f"Root: {root}")

    print("\nBaseline area summary:")
    print(summary.to_string(index=False))

    print("\nQA:")
    print(json.dumps(qa, ensure_ascii=False, indent=2))

    print("\nCreated:")
    for p in [
        out_class,
        out_summary,
        out_sens,
        out_qa,
        out_readme,
    ]:
        print(" -", p.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R01B1, R03 and R04 outputs",
    )
    args = parser.parse_args()
    main(Path(args.root))
