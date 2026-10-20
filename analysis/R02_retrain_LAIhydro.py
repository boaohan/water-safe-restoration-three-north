from pathlib import Path
import json
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_pinball_loss, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

HERE = Path(__file__).resolve().parent

STATIC = HERE / "R01B1_Static_ByClass_FINAL.csv"
PERIODS = [
    HERE / "R01B1_ClassYear_2005_2009.csv",
    HERE / "R01B1_ClassYear_2010_2014.csv",
    HERE / "R01B1_ClassYear_2015_2019.csv",
    HERE / "R01B1_ClassYear_2020_2024.csv",
]

TARGET = "LAI_nat_max"
QUANTILE_ALPHA = 0.95
SUSTAINABLE_Q = 0.25
RANDOM_STATE = 42
MIN_NATURAL_REF_AREA_KM2 = 30.0

NUM_FEATURES = [
    "P_mm", "PET_mm", "AET_mm", "Runoff_mm", "Soil_mm",
    "Tmean_C", "VPD_kPa", "AI_P_PET", "Elevation_m", "Slope_deg",
]
CAT_FEATURES = ["BaseZone"]
ALL_FEATURES = CAT_FEATURES + NUM_FEATURES

def make_pipeline():
    try:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse=False)

    prep = ColumnTransformer(
        [
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", ohe),
            ]), CAT_FEATURES),
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
            ]), NUM_FEATURES),
        ],
        remainder="drop",
    )

    model = GradientBoostingRegressor(
        loss="quantile",
        alpha=QUANTILE_ALPHA,
        n_estimators=300,
        learning_rate=0.03,
        max_depth=2,
        min_samples_leaf=3,
        subsample=1.0,
        random_state=RANDOM_STATE,
    )
    return Pipeline([("prep", prep), ("model", model)])

static = pd.read_csv(STATIC)
panel = pd.concat([pd.read_csv(p) for p in PERIODS], ignore_index=True)

static["GDE_persistence_canonical"] = (
    static["GDE_persistence_count"] - static["GDE_persistence_delta_vs_R01A2"]
)
static["GDE_stability_canonical"] = static["GDE_persistence_canonical"] / 4.0

df = panel.merge(
    static[[
        "ClassCode", "Area_km2", "NaturalRefAreaShare", "NaturalRefArea_km2",
        "GWSA_trend", "Elevation_m", "Slope_deg", "GDE_frac",
        "GDE_persistence_canonical", "GDE_stability_canonical", "LAI_current_3yr",
    ]],
    on="ClassCode",
    how="left",
    validate="many_to_one",
)

train = df[
    (df["GDE_Level"] == 0)
    & (df["NaturalRefArea_km2"] >= MIN_NATURAL_REF_AREA_KM2)
    & df[TARGET].notna()
    & (df[TARGET] > 0)
    & (df[TARGET] < 10)
].copy().reset_index(drop=True)

X = train[ALL_FEATURES]
y = train[TARGET]

metrics = []
for name, groups in [
    ("5-fold grouped by Year", train["Year"]),
    ("5-fold grouped by BaseZone", train["BaseZone"]),
]:
    pred = np.full(len(train), np.nan)
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups=groups):
        model_cv = make_pipeline()
        model_cv.fit(X.iloc[tr], y.iloc[tr])
        pred[te] = np.clip(model_cv.predict(X.iloc[te]), 0, None)

    metrics.append({
        "model": "R02_revised_nonGDE",
        "validation": name,
        "pinball_loss_q95": mean_pinball_loss(y, pred, alpha=QUANTILE_ALPHA),
        "MAE": mean_absolute_error(y, pred),
        "RMSE": mean_squared_error(y, pred) ** 0.5,
        "R2": r2_score(y, pred),
        "empirical_coverage_y_le_pred": float(np.mean(y <= pred)),
    })

pd.DataFrame(metrics).to_csv(HERE / "R02_ModelMetrics.csv", index=False, encoding="utf-8-sig")

model = make_pipeline()
model.fit(X, y)

df["LAI_cap_pred_annual"] = np.clip(model.predict(df[ALL_FEATURES]), 0, None)
df.to_csv(HERE / "R02_ClassYear_With_LAIcapPred.csv", index=False, encoding="utf-8-sig")

summary = (
    df.groupby("ClassCode", as_index=False)
    .agg(
        BaseZone=("BaseZone", "first"),
        GDE_Level=("GDE_Level", "first"),
        Area_km2=("Area_km2", "first"),
        NaturalRefAreaShare=("NaturalRefAreaShare", "first"),
        NaturalRefArea_km2=("NaturalRefArea_km2", "first"),
        GDE_frac=("GDE_frac", "first"),
        GDE_persistence_canonical=("GDE_persistence_canonical", "first"),
        GDE_stability_canonical=("GDE_stability_canonical", "first"),
        GWSA_trend=("GWSA_trend", "first"),
        LAI_current_3yr=("LAI_current_3yr", "first"),
        LAI_cap_pred_q25=("LAI_cap_pred_annual", lambda s: float(np.nanquantile(s, 0.25))),
        LAI_cap_pred_q50=("LAI_cap_pred_annual", lambda s: float(np.nanquantile(s, 0.50))),
        LAI_cap_pred_q75=("LAI_cap_pred_annual", lambda s: float(np.nanquantile(s, 0.75))),
        LAI_cap_pred_mean=("LAI_cap_pred_annual", "mean"),
        LAI_cap_pred_min=("LAI_cap_pred_annual", "min"),
        LAI_cap_pred_max=("LAI_cap_pred_annual", "max"),
        LAI_nat_max_mean=("LAI_nat_max", "mean"),
        LAI_nat_mean_mean=("LAI_nat_mean", "mean"),
        AI_mean=("AI_P_PET", "mean"),
        P_mean=("P_mm", "mean"),
        PET_mean=("PET_mm", "mean"),
        FVC_mean=("FVC", "mean"),
        BareSoilFrac_mean=("BareSoilFrac", "mean"),
    )
    .sort_values("ClassCode")
)

summary["LAI_hydro"] = summary["LAI_cap_pred_q25"]
summary["NaturalRefSupport"] = np.select(
    [
        summary["NaturalRefAreaShare"] < 0.05,
        summary["NaturalRefAreaShare"] < 0.20,
    ],
    ["low", "medium"],
    default="high",
)
summary["CurrentLAI_exceeds_LAIhydro"] = (
    summary["LAI_current_3yr"] > summary["LAI_hydro"]
)

summary.to_csv(HERE / "R02_Class_LAIhydro_q25.csv", index=False, encoding="utf-8-sig")
print("R02 complete.")
