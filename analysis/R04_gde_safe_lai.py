# -*- coding: utf-8 -*-
"""
R04_gde_safe_lai.py

Recompute GDE-constrained safe LAI using the revised canonical 58-unit chain.

Key revision relative to the old workflow
-----------------------------------------
The historical workflow used:
    GDE_stability = GDE_persistence / 4
which makes "stability" and "persistence" mathematically redundant and then
weights both in the same risk index.

This revised R04 keeps the original transparent five-component risk structure
but makes the temporal components distinct:

1. GDE union fraction:
      GDE_frac

2. GDE temporal persistence:
      mean(GDE_frac_P1, P2, P3, P4)

3. GDE temporal stability:
      1 - CV(GDE_frac_P1..P4), clipped to [0,1]
   and set to 0 in non-GDE classes.

4. Groundwater-storage decline:
      max(-GWSA_trend, 0)

5. GDE management-class component:
      level 0 -> 0.00
      level 1 -> 0.30  (GDE-dominated conservation; hard cap applied later)
      level 2 -> 0.45
      level 3 -> 0.70  (fragmented high-risk)

Baseline weights preserve the old workflow:
      0.30, 0.20, 0.15, 0.20, 0.15

Safe LAI:
      R_gde = weighted robust-normalized risk, clipped [0, 0.80]
      LAI_safe_pre = LAI_hydro * (1 - R_gde)

For GDE_Level == 1:
      LAI_safe = min(LAI_safe_pre, LAI_current_3yr)

Important:
If LAI_safe < current LAI, this is NOT automatically a thinning prescription.
It means there is no additional active-canopy headroom and the unit should be
treated conservatively in R05.

Usage:
python R04_gde_safe_lai.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------
W_GDE_FRAC = 0.30
W_GDE_STABILITY = 0.20
W_GDE_PERSISTENCE = 0.15
W_GWSA_DECLINE = 0.20
W_GDE_CLASS = 0.15

RISK_MIN = 0.00
RISK_MAX = 0.80

WEAK_MULTIPLIER = 0.80
STRONG_MULTIPLIER = 1.20

EPS = 1e-9


def robust_minmax(s: pd.Series, q_low=0.05, q_high=0.95) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    lo = x.quantile(q_low)
    hi = x.quantile(q_high)

    if pd.isna(lo) or pd.isna(hi) or hi <= lo:
        return pd.Series(np.zeros(len(x)), index=x.index, dtype=float)

    return ((x.clip(lo, hi) - lo) / (hi - lo)).fillna(0.0)


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


def class_risk(level: pd.Series) -> pd.Series:
    # level 1 is a conservation class; its hard cap is imposed separately.
    risk_map = {
        0: 0.00,
        1: 0.30,
        2: 0.45,
        3: 0.70,
    }
    return level.map(risk_map).fillna(0.0).astype(float)


def compute_safe(df: pd.DataFrame, multiplier: float, label: str) -> pd.DataFrame:
    out = df.copy()

    rgde = (out["R_gde_baseline"] * multiplier).clip(
        lower=RISK_MIN, upper=RISK_MAX
    )

    pre = out["LAI_hydro"] * (1.0 - rgde)
    safe = pre.copy()

    core = out["GDE_Level"] == 1
    safe.loc[core] = np.minimum(
        pre.loc[core],
        out.loc[core, "LAI_current_3yr"],
    )

    safe = safe.clip(lower=0.0)

    out[f"R_gde_{label}"] = rgde
    out[f"LAI_safe_pre_{label}"] = pre
    out[f"LAI_safe_{label}"] = safe
    out[f"safe_ratio_{label}"] = np.where(
        out["LAI_hydro"] > 0,
        safe / out["LAI_hydro"],
        np.nan,
    )
    out[f"LAI_headroom_{label}"] = np.maximum(
        safe - out["LAI_current_3yr"], 0.0
    )
    out[f"Over_safe_capacity_{label}"] = (
        safe < out["LAI_current_3yr"]
    )

    return out


def main(root: Path):
    root = root.expanduser().resolve()

    paths = {
        "r02": root / "R02_Class_LAIhydro_q25.csv",
        "static": root / "R01B1_Static_ByClass_FINAL.csv",
        "r03": root / "R03_Class_Occupancy.csv",
    }

    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required files:\n"
            + "\n".join(missing)
            + "\n\nMake sure R02 and R03 outputs are in the same --root folder."
        )

    r02 = pd.read_csv(paths["r02"])
    static = pd.read_csv(paths["static"])
    r03 = pd.read_csv(paths["r03"])

    # -----------------------------------------------------------------
    # Merge canonical inputs
    # -----------------------------------------------------------------
    use_static = [
        "ClassCode",
        "GDE_frac_P1",
        "GDE_frac_P2",
        "GDE_frac_P3",
        "GDE_frac_P4",
        "GDE_trend_4period",
        "GWSA_trend",
    ]

    df = r02.merge(
        static[use_static],
        on="ClassCode",
        how="left",
        validate="one_to_one",
        suffixes=("", "_static"),
    )

    use_r03 = [
        "ClassCode",
        "V_hydro",
        "V_headroom",
        "FVC_recent_2022_2024",
        "BarrenLandFrac",
        "SparseOpenCandidate_prelim",
        "AridityClass",
    ]

    df = df.merge(
        r03[use_r03],
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    if len(df) != 58 or df["ClassCode"].nunique() != 58:
        raise RuntimeError(
            f"Expected 58 unique ClassCodes; got rows={len(df)}, "
            f"unique={df['ClassCode'].nunique()}"
        )

    # -----------------------------------------------------------------
    # Revised temporal GDE descriptors
    # -----------------------------------------------------------------
    period_cols = [
        "GDE_frac_P1",
        "GDE_frac_P2",
        "GDE_frac_P3",
        "GDE_frac_P4",
    ]

    period = df[period_cols].astype(float)

    # Mean period fraction = temporal persistence / recurrence extent.
    df["GDE_persistence_revised"] = period.mean(axis=1)

    # Distinct stability metric:
    # 1 - coefficient of variation across the four period fractions.
    pmean = period.mean(axis=1)
    psd = period.std(axis=1, ddof=0)

    cv = psd / (pmean.abs() + EPS)
    stability = 1.0 - cv.clip(lower=0.0, upper=1.0)

    # Avoid "perfectly stable zero-GDE" being interpreted as high GDE stability.
    stability = stability.where(
        (df["GDE_Level"] != 0) & (pmean > 0),
        0.0,
    )

    df["GDE_stability_revised"] = stability.clip(0.0, 1.0)

    # Record old canonical metrics for QA, because R02 carried them.
    if "GDE_persistence_canonical" in df.columns:
        df["OldPersistence_minus_Revised"] = (
            df["GDE_persistence_canonical"]
            - df["GDE_persistence_revised"]
        )

    # -----------------------------------------------------------------
    # Risk components
    # -----------------------------------------------------------------
    df["risk_gde_frac"] = robust_minmax(df["GDE_frac"])
    df["risk_gde_stability"] = robust_minmax(df["GDE_stability_revised"])
    df["risk_gde_persistence"] = robust_minmax(
        df["GDE_persistence_revised"]
    )

    df["GWSA_decline"] = (-df["GWSA_trend"]).clip(lower=0.0)
    df["risk_gwsa_decline"] = robust_minmax(df["GWSA_decline"])
    df["risk_gde_class"] = class_risk(df["GDE_Level"])

    df["R_gde_raw"] = (
        W_GDE_FRAC * df["risk_gde_frac"]
        + W_GDE_STABILITY * df["risk_gde_stability"]
        + W_GDE_PERSISTENCE * df["risk_gde_persistence"]
        + W_GWSA_DECLINE * df["risk_gwsa_decline"]
        + W_GDE_CLASS * df["risk_gde_class"]
    )

    df["R_gde_baseline"] = df["R_gde_raw"].clip(
        lower=RISK_MIN,
        upper=RISK_MAX,
    )

    # -----------------------------------------------------------------
    # Baseline + weak/strong sensitivity
    # -----------------------------------------------------------------
    base = compute_safe(df, 1.00, "baseline")

    # Preserve short canonical names for all later scripts.
    base["LAI_safe"] = base["LAI_safe_baseline"]
    base["safe_ratio"] = base["safe_ratio_baseline"]
    base["LAI_headroom"] = base["LAI_headroom_baseline"]
    base["Over_safe_capacity"] = base["Over_safe_capacity_baseline"]

    weak = compute_safe(df, WEAK_MULTIPLIER, "weak")
    strong = compute_safe(df, STRONG_MULTIPLIER, "strong")

    for col in [
        "R_gde_weak",
        "LAI_safe_weak",
        "safe_ratio_weak",
        "LAI_headroom_weak",
        "Over_safe_capacity_weak",
    ]:
        base[col] = weak[col]

    for col in [
        "R_gde_strong",
        "LAI_safe_strong",
        "safe_ratio_strong",
        "LAI_headroom_strong",
        "Over_safe_capacity_strong",
    ]:
        base[col] = strong[col]

    # -----------------------------------------------------------------
    # QA / summaries
    # -----------------------------------------------------------------
    component_cols = [
        "risk_gde_frac",
        "risk_gde_stability",
        "risk_gde_persistence",
        "risk_gwsa_decline",
        "risk_gde_class",
    ]

    risk_components = base[
        [
            "ClassCode",
            "BaseZone",
            "GDE_Level",
            "Area_km2",
            "GDE_frac",
            "GDE_persistence_revised",
            "GDE_stability_revised",
            "GDE_trend_4period",
            "GWSA_trend",
            "GWSA_decline",
        ]
        + component_cols
        + [
            "R_gde_raw",
            "R_gde_baseline",
        ]
    ].copy()

    # Unweighted and area-weighted summaries by GDE level.
    summary_rows = []
    for level, g in base.groupby("GDE_Level", sort=True):
        summary_rows.append({
            "GDE_Level": int(level),
            "n_ClassCode": int(len(g)),
            "Area_km2": float(g["Area_km2"].sum()),
            "median_LAI_hydro": float(g["LAI_hydro"].median()),
            "median_LAI_safe": float(g["LAI_safe"].median()),
            "median_safe_ratio": float(g["safe_ratio"].median()),
            "area_weighted_median_safe_ratio": weighted_median(
                g["safe_ratio"], g["Area_km2"]
            ),
            "median_R_gde": float(g["R_gde_baseline"].median()),
            "n_over_safe_capacity": int(g["Over_safe_capacity"].sum()),
            "area_over_safe_capacity_km2": float(
                g.loc[g["Over_safe_capacity"], "Area_km2"].sum()
            ),
            "median_LAI_headroom": float(g["LAI_headroom"].median()),
        })

    level_summary = pd.DataFrame(summary_rows)

    sensitivity_rows = []
    for scenario in ["weak", "baseline", "strong"]:
        safe_col = (
            "LAI_safe" if scenario == "baseline"
            else f"LAI_safe_{scenario}"
        )
        ratio_col = (
            "safe_ratio" if scenario == "baseline"
            else f"safe_ratio_{scenario}"
        )
        head_col = (
            "LAI_headroom" if scenario == "baseline"
            else f"LAI_headroom_{scenario}"
        )
        over_col = (
            "Over_safe_capacity" if scenario == "baseline"
            else f"Over_safe_capacity_{scenario}"
        )

        sensitivity_rows.append({
            "Scenario": scenario,
            "Median_LAI_safe": float(base[safe_col].median()),
            "Median_safe_ratio": float(base[ratio_col].median()),
            "Median_LAI_headroom": float(base[head_col].median()),
            "n_over_safe_capacity": int(base[over_col].sum()),
            "Area_over_safe_capacity_km2": float(
                base.loc[base[over_col], "Area_km2"].sum()
            ),
        })

    sensitivity = pd.DataFrame(sensitivity_rows)

    # Safety invariants
    qa = {
        "rows": int(len(base)),
        "unique_classcodes": int(base["ClassCode"].nunique()),
        "missing_LAI_safe": int(base["LAI_safe"].isna().sum()),
        "negative_LAI_safe": int((base["LAI_safe"] < 0).sum()),
        "LAI_safe_above_LAI_hydro": int(
            (base["LAI_safe"] > base["LAI_hydro"] + 1e-9).sum()
        ),
        "core_level1_above_current_LAI": int(
            (
                (base["GDE_Level"] == 1)
                & (
                    base["LAI_safe"]
                    > base["LAI_current_3yr"] + 1e-9
                )
            ).sum()
        ),
        "safe_ratio_min": float(base["safe_ratio"].min()),
        "safe_ratio_median": float(base["safe_ratio"].median()),
        "safe_ratio_max": float(base["safe_ratio"].max()),
        "LAI_safe_min": float(base["LAI_safe"].min()),
        "LAI_safe_median": float(base["LAI_safe"].median()),
        "LAI_safe_max": float(base["LAI_safe"].max()),
        "n_over_safe_capacity": int(base["Over_safe_capacity"].sum()),
        "area_over_safe_capacity_km2": float(
            base.loc[base["Over_safe_capacity"], "Area_km2"].sum()
        ),
        "n_with_positive_LAI_headroom": int((base["LAI_headroom"] > 0).sum()),
        "n_with_positive_V_headroom": int((base["V_headroom"] > 0).sum()),
        "prelim_sparse_open_n": int(
            base["SparseOpenCandidate_prelim"].sum()
        ),
    }

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------
    out_class = root / "R04_Class_LAIsafe.csv"
    out_components = root / "R04_RiskComponents.csv"
    out_level = root / "R04_GDELevel_Summary.csv"
    out_sensitivity = root / "R04_RiskIntensity_Sensitivity.csv"
    out_qa = root / "R04_QA.json"
    out_readme = root / "R04_README.txt"

    base.to_csv(out_class, index=False, encoding="utf-8-sig")
    risk_components.to_csv(out_components, index=False, encoding="utf-8-sig")
    level_summary.to_csv(out_level, index=False, encoding="utf-8-sig")
    sensitivity.to_csv(out_sensitivity, index=False, encoding="utf-8-sig")
    out_qa.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readme = f"""
R04 — Revised GDE-constrained safe LAI
======================================

Inputs:
- R02_Class_LAIhydro_q25.csv
- R01B1_Static_ByClass_FINAL.csv
- R03_Class_Occupancy.csv

Critical correction:
The old workflow defined GDE_stability = GDE_persistence / 4, so the two risk
components were mathematically redundant. R04 replaces that duplicate stability
term with a temporal-stability index derived from the four period-specific GDE
fractions.

Revised GDE descriptors:
- GDE_frac: 2005–2024 union fraction
- GDE_persistence_revised: mean of GDE_frac_P1..P4
- GDE_stability_revised:
      1 - CV(GDE_frac_P1..P4), clipped [0,1],
      and set to 0 for GDE_Level == 0
- GWSA decline: max(-GWSA_trend, 0)
- GDE class component:
      0 -> 0.00
      1 -> 0.30 + separate hard conservation cap
      2 -> 0.45
      3 -> 0.70

Baseline risk:
R_gde =
  0.30 * risk(GDE fraction)
+ 0.20 * risk(temporal stability)
+ 0.15 * risk(temporal persistence)
+ 0.20 * risk(GWSA decline)
+ 0.15 * GDE-class component

R_gde is clipped to [0, 0.80].

Safe LAI:
LAI_safe_pre = LAI_hydro * (1 - R_gde)

For GDE_Level == 1:
LAI_safe = min(LAI_safe_pre, LAI_current_3yr)

Interpretation:
LAI_safe is a water-safety boundary, not a planting target.
If LAI_safe < current LAI, do NOT automatically prescribe thinning.
R05 will interpret this as "no additional active-canopy headroom" and combine
it with V_headroom, sparse/open-land status, land use, and GDE constraints.

Weak/strong sensitivity:
- weak:   R_gde × {WEAK_MULTIPLIER}
- strong: R_gde × {STRONG_MULTIPLIER}

QA:
{json.dumps(qa, ensure_ascii=False, indent=2)}

By GDE level:
{level_summary.to_string(index=False)}

Sensitivity:
{sensitivity.to_string(index=False)}
""".strip()

    out_readme.write_text(readme, encoding="utf-8")

    print("\nR04 completed successfully.")
    print(f"Root: {root}")
    print("\nQA:")
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    print("\nBy GDE level:")
    print(level_summary.to_string(index=False))
    print("\nRisk-intensity sensitivity:")
    print(sensitivity.to_string(index=False))
    print("\nCreated:")
    for p in [
        out_class,
        out_components,
        out_level,
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
        help="Folder containing R02 and R03 outputs",
    )
    args = parser.parse_args()
    main(Path(args.root))
