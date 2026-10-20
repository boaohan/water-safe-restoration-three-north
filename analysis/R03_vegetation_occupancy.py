# -*- coding: utf-8 -*-
"""
R03_vegetation_occupancy.py

Purpose
-------
Build a hydroclimatic vegetation-occupancy envelope for the revised Three-North
shelterbelt analysis, using the R02 outputs.

Baseline scientific definition
------------------------------
1) Target = annual whole-unit FVC (fractional vegetation cover).
2) Calibration domain excludes obvious groundwater/cropland/surface-water support:
   - GDE_Level == 0
   - CroplandFrac < 0.10
   - PermanentWaterFrac < 0.05
   - NaturalRefAreaShare >= 0.05
3) Predictors are hydroclimatic/terrain variables only:
   P, PET, runoff, soil water, Tmean, VPD, AI=P/PET, elevation, slope.
   AET is intentionally excluded because it is partly vegetation-dependent.
4) Baseline model = q0.90 GradientBoostingRegressor.
5) For each ClassCode, V_hydro = q0.25 of the 20 annual q0.90 predictions.
   This is a conservative, long-term hydroclimatic occupancy envelope.
6) q0.85 and q0.95 versions are retained as sensitivity bounds.
7) Sparse/open-land flags are diagnostic only at R03. They do NOT yet assign
   the final management pathway. Final active-restoration eligibility will be
   decided after GDE-safe LAI is recomputed.

Usage
-----
python R03_vegetation_occupancy.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_pinball_loss, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline


def make_model(alpha: float):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", GradientBoostingRegressor(
            loss="quantile",
            alpha=alpha,
            n_estimators=400,
            learning_rate=0.025,
            max_depth=2,
            min_samples_leaf=4,
            subsample=1.0,
            random_state=42,
        )),
    ])


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


def main(root: Path):
    root = root.expanduser().resolve()

    required = {
        "panel": root / "R02_ClassYear_With_LAIcapPred.csv",
        "r02class": root / "R02_Class_LAIhydro_q25.csv",
        "static": root / "R01B1_Static_ByClass_FINAL.csv",
    }

    missing = [str(p) for p in required.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required files:\n" + "\n".join(missing)
            + "\n\nMake sure R02_LAIhydro_rerun_bundle.zip has been extracted into --root."
        )

    panel = pd.read_csv(required["panel"])
    r02class = pd.read_csv(required["r02class"])
    static = pd.read_csv(required["static"])

    # Add static land-surface variables not already carried into R02 panel.
    extra_static = [
        "ClassCode",
        "CroplandFrac",
        "PermanentWaterFrac",
        "BarrenLandFrac",
        "SW_occurrence_landmean_pct",
        "ForestLandFrac",
        "ShrubLandFrac",
        "SavannaLandFrac",
        "GrassLandFrac",
    ]

    df = panel.merge(
        static[extra_static],
        on="ClassCode",
        how="left",
        validate="many_to_one",
    )

    df = df.merge(
        r02class[["ClassCode", "LAI_hydro"]],
        on="ClassCode",
        how="left",
        validate="many_to_one",
    )

    # Hydroclimatic/terrain predictors only.
    features = [
        "P_mm",
        "PET_mm",
        "Runoff_mm",
        "Soil_mm",
        "Tmean_C",
        "VPD_kPa",
        "AI_P_PET",
        "Elevation_m",
        "Slope_deg",
    ]

    # Calibration domain:
    # non-GDE, low-cropland, little permanent surface water, and at least
    # a minimal natural-reference footprint.
    train_mask = (
        (df["GDE_Level"] == 0)
        & (df["CroplandFrac"] < 0.10)
        & (df["PermanentWaterFrac"] < 0.05)
        & (df["NaturalRefAreaShare"] >= 0.05)
        & df["FVC"].notna()
    )

    train = df.loc[train_mask].copy().reset_index(drop=True)

    if len(train) < 100:
        raise RuntimeError(f"Too few occupancy calibration records: {len(train)}")

    X = train[features]
    y = train["FVC"].astype(float)

    # -----------------------
    # Cross-validation
    # -----------------------
    metrics = []
    oof = train[
        [
            "ClassCode",
            "BaseZone",
            "GDE_Level",
            "Year",
            "FVC",
            "AI_P_PET",
            "CroplandFrac",
            "PermanentWaterFrac",
            "NaturalRefAreaShare",
        ]
    ].copy()

    for validation_name, groups, out_col in [
        ("5-fold grouped by Year", train["Year"], "pred_q90_CV_year"),
        ("5-fold grouped by BaseZone", train["BaseZone"], "pred_q90_CV_basezone"),
    ]:
        n_splits = min(5, int(groups.nunique()))
        pred = np.full(len(train), np.nan, dtype=float)

        cv = GroupKFold(n_splits=n_splits)

        for tr_idx, te_idx in cv.split(X, y, groups=groups):
            model = make_model(0.90)
            model.fit(X.iloc[tr_idx], y.iloc[tr_idx])
            pred[te_idx] = np.clip(model.predict(X.iloc[te_idx]), 0, 1)

        oof[out_col] = pred

        metrics.append({
            "model": "R03_FVC_hydro_envelope_q90",
            "validation": validation_name,
            "n_samples": len(train),
            "n_classcodes": int(train["ClassCode"].nunique()),
            "n_basezones": int(train["BaseZone"].nunique()),
            "pinball_loss_q90": mean_pinball_loss(y, pred, alpha=0.90),
            "MAE": mean_absolute_error(y, pred),
            "RMSE": mean_squared_error(y, pred) ** 0.5,
            "R2": r2_score(y, pred),
            "empirical_coverage_y_le_pred": float(np.mean(y <= pred)),
        })

    metrics = pd.DataFrame(metrics)

    # -----------------------
    # Baseline + sensitivity
    # -----------------------
    for alpha in (0.85, 0.90, 0.95):
        model = make_model(alpha)
        model.fit(X, y)
        df[f"Vpred_q{int(alpha*100)}"] = np.clip(
            model.predict(df[features]), 0, 1
        )

    # Class-level summaries
    rows = []

    for cc, g in df.groupby("ClassCode", sort=True):
        recent = g.loc[g["Year"].between(2022, 2024), "FVC"]

        rows.append({
            "ClassCode": int(cc),
            "BaseZone": int(g["BaseZone"].iloc[0]),
            "GDE_Level": int(g["GDE_Level"].iloc[0]),
            "Area_km2": float(g["Area_km2"].iloc[0]),
            "NaturalRefAreaShare": float(g["NaturalRefAreaShare"].iloc[0]),
            "CroplandFrac": float(g["CroplandFrac"].iloc[0]),
            "PermanentWaterFrac": float(g["PermanentWaterFrac"].iloc[0]),
            "BarrenLandFrac": float(g["BarrenLandFrac"].iloc[0]),
            "SW_occurrence_landmean_pct": float(g["SW_occurrence_landmean_pct"].iloc[0]),
            "GDE_frac": float(g["GDE_frac"].iloc[0]),
            "LAI_hydro": float(g["LAI_hydro"].iloc[0]),
            "LAI_current_3yr": float(g["LAI_current_3yr"].iloc[0]),
            "AI_mean": float(g["AI_P_PET"].mean()),
            "P_mean": float(g["P_mm"].mean()),
            "PET_mean": float(g["PET_mm"].mean()),
            "FVC_mean_2005_2024": float(g["FVC"].mean()),
            "FVC_recent_2022_2024": float(recent.mean()),
            "BareSoilFrac_mean": float(g["BareSoilFrac"].mean()),
            "V_hydro_q85": float(np.quantile(g["Vpred_q85"], 0.25)),
            "V_hydro_q90": float(np.quantile(g["Vpred_q90"], 0.25)),
            "V_hydro_q95": float(np.quantile(g["Vpred_q95"], 0.25)),
            "V_hydro_q90_median_year": float(np.median(g["Vpred_q90"])),
            "V_hydro_q90_min_year": float(np.min(g["Vpred_q90"])),
            "V_hydro_q90_max_year": float(np.max(g["Vpred_q90"])),
        })

    class_out = pd.DataFrame(rows).sort_values("ClassCode").reset_index(drop=True)

    # Baseline occupancy envelope
    class_out["V_hydro"] = class_out["V_hydro_q90"]

    # Continuous headroom: no management category assigned here.
    class_out["V_headroom"] = np.maximum(
        class_out["V_hydro"] - class_out["FVC_recent_2022_2024"],
        0.0
    )

    class_out["V_current_to_hydro_ratio"] = (
        class_out["FVC_recent_2022_2024"]
        / class_out["V_hydro"].replace(0, np.nan)
    )

    class_out["CurrentFVC_above_Vhydro"] = (
        class_out["FVC_recent_2022_2024"] > class_out["V_hydro"]
    )

    class_out["AridityClass"] = class_out["AI_mean"].map(aridity_class)

    # Diagnostic sparse/open candidate flag only.
    # It is intentionally NOT the final management assignment.
    # Baseline threshold: V_hydro < 0.15 and BarrenLandFrac >= 0.50.
    class_out["SparseOpenCandidate_prelim"] = (
        (class_out["V_hydro"] < 0.15)
        & (class_out["BarrenLandFrac"] >= 0.50)
    )

    # -----------------------
    # Threshold sensitivity
    # -----------------------
    sens_rows = []
    total_area = class_out["Area_km2"].sum()

    for v_thr in (0.10, 0.15, 0.20):
        for barren_thr in (0.40, 0.50, 0.60):
            flag = (
                (class_out["V_hydro"] < v_thr)
                & (class_out["BarrenLandFrac"] >= barren_thr)
            )
            area = float(class_out.loc[flag, "Area_km2"].sum())

            sens_rows.append({
                "V_hydro_threshold": v_thr,
                "BarrenLandFrac_threshold": barren_thr,
                "n_ClassCode": int(flag.sum()),
                "Area_km2": area,
                "Area_share_pct": area / total_area * 100.0,
                "ClassCodes": ",".join(
                    map(str, class_out.loc[flag, "ClassCode"].tolist())
                ),
            })

    sensitivity = pd.DataFrame(sens_rows)

    # -----------------------
    # QA
    # -----------------------
    qa = {
        "input_classyear_rows": int(len(df)),
        "input_classcodes": int(df["ClassCode"].nunique()),
        "input_years": int(df["Year"].nunique()),
        "training_rows": int(len(train)),
        "training_classcodes": int(train["ClassCode"].nunique()),
        "training_basezones": int(train["BaseZone"].nunique()),
        "training_basezone_list": sorted(map(int, train["BaseZone"].unique())),
        "output_classcodes": int(len(class_out)),
        "V_hydro_min": float(class_out["V_hydro"].min()),
        "V_hydro_median": float(class_out["V_hydro"].median()),
        "V_hydro_max": float(class_out["V_hydro"].max()),
        "V_headroom_median": float(class_out["V_headroom"].median()),
        "current_FVC_above_Vhydro_n": int(class_out["CurrentFVC_above_Vhydro"].sum()),
        "prelim_sparse_open_n": int(class_out["SparseOpenCandidate_prelim"].sum()),
        "prelim_sparse_open_ClassCodes": list(
            map(
                int,
                class_out.loc[
                    class_out["SparseOpenCandidate_prelim"], "ClassCode"
                ].tolist()
            )
        ),
    }

    # -----------------------
    # Export
    # -----------------------
    out_training = root / "R03_Training_Occupancy.csv"
    out_metrics = root / "R03_Occupancy_ModelMetrics.csv"
    out_oof = root / "R03_Occupancy_CV_predictions.csv"
    out_panel = root / "R03_ClassYear_OccupancyPred.csv"
    out_class = root / "R03_Class_Occupancy.csv"
    out_sens = root / "R03_SparseOpen_Sensitivity.csv"
    out_qa = root / "R03_QA.json"
    out_readme = root / "R03_README.txt"

    train.to_csv(out_training, index=False, encoding="utf-8-sig")
    metrics.to_csv(out_metrics, index=False, encoding="utf-8-sig")
    oof.to_csv(out_oof, index=False, encoding="utf-8-sig")
    df.to_csv(out_panel, index=False, encoding="utf-8-sig")
    class_out.to_csv(out_class, index=False, encoding="utf-8-sig")
    sensitivity.to_csv(out_sens, index=False, encoding="utf-8-sig")

    out_qa.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    readme = f"""
R03 — Hydroclimatic vegetation-occupancy envelope
=================================================

Baseline definition:
V_hydro = Q25 over 2005–2024 annual q0.90 FVC-envelope predictions.

Calibration domain:
- GDE_Level == 0
- CroplandFrac < 0.10
- PermanentWaterFrac < 0.05
- NaturalRefAreaShare >= 0.05

Target:
- annual whole-unit FVC

Predictors:
- P_mm
- PET_mm
- Runoff_mm
- Soil_mm
- Tmean_C
- VPD_kPa
- AI_P_PET
- Elevation_m
- Slope_deg

Excluded:
- AET, because it is partly vegetation-dependent
- GDE/GWSA variables, because groundwater constraint is applied later
- tree/shrub/herbaceous decision variables
- current LAI

Baseline diagnostic sparse/open candidate:
- V_hydro < 0.15
- BarrenLandFrac >= 0.50

This diagnostic is NOT the final management classification.
R04 will recompute GDE-safe LAI.
R05 will combine LAI headroom + V_headroom + GDE + land-surface constraints
to define final active-restoration eligibility.

QA:
{json.dumps(qa, ensure_ascii=False, indent=2)}

Validation:
{metrics.to_string(index=False)}
""".strip()

    out_readme.write_text(readme, encoding="utf-8")

    print("\nR03 completed successfully.")
    print(f"Root: {root}")
    print(f"Training rows: {len(train)}")
    print(f"Output ClassCodes: {len(class_out)}")
    print(
        "V_hydro min / median / max:",
        round(class_out["V_hydro"].min(), 4),
        round(class_out["V_hydro"].median(), 4),
        round(class_out["V_hydro"].max(), 4),
    )
    print(
        "Preliminary sparse/open ClassCodes:",
        class_out.loc[
            class_out["SparseOpenCandidate_prelim"], "ClassCode"
        ].tolist()
    )
    print("\nValidation metrics:")
    print(metrics.to_string(index=False))
    print("\nCreated:")
    for p in [
        out_training, out_metrics, out_oof, out_panel,
        out_class, out_sens, out_qa, out_readme
    ]:
        print(" -", p.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing the extracted R02 bundle"
    )
    args = parser.parse_args()
    main(Path(args.root))
