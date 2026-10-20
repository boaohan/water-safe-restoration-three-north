# -*- coding: utf-8 -*-
"""
R09C_environmental_transferability.py

Purpose
-------
Quantify environmental transferability from the Horqin / Otindag source domain
to each revised Three-North ClassCode.

Inputs
------
- R09B_ReferenceDomain_Environment.csv
- R02_ClassYear_With_LAIcapPred.csv
- R01B1_Static_ByClass_FINAL.csv
- R08_FinalManagement_ByClass.csv
- optional: R09A_EngineeringReference_Validation.csv

Method
------
1. Build 2005–2024 mean environment for each ClassCode.
2. For each local source domain separately, robust-standardize variables using
   the source-domain median and IQR.
3. Fit Ledoit-Wolf covariance in that standardized environmental space.
4. Calculate Mahalanobis distance of each ClassCode to each source domain.
5. Thresholds are data-derived from internal source-sample distances:
      High transferability:
          D <= source q95 AND envelope_fraction >= 0.75
      Moderate:
          D <= source q99 OR envelope_fraction >= 0.75
      Low:
          otherwise
6. The best (highest) tier across Horqin and Otindag is retained.

Important
---------
This determines whether LOCAL density/species references are environmentally
transferable. It does not validate regional life-form / LAI outputs; those were
already derived independently in R01–R08.

Usage
-----
python R09C_environmental_transferability.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

from sklearn.covariance import LedoitWolf


FEATURES = [
    "P_mm",
    "PET_mm",
    "Soil_mm",
    "Tmean_C",
    "VPD_kPa",
    "AI_P_PET",
    "Elevation_m",
    "Slope_deg",
]


TIER_RANK = {
    "low": 0,
    "moderate": 1,
    "high": 2,
}


def robust_scale_fit(df, features):
    med = df[features].median()
    q25 = df[features].quantile(0.25)
    q75 = df[features].quantile(0.75)

    iqr = (q75 - q25).replace(0, np.nan)

    # Fallback to std for zero-IQR variables.
    std = df[features].std(ddof=0).replace(0, np.nan)
    scale = iqr.fillna(std).fillna(1.0)

    return med, scale


def transform(df, med, scale):
    return (
        df[med.index]
        .astype(float)
        .sub(med, axis=1)
        .div(scale, axis=1)
    )


def mahalanobis_distance(X, location, precision):
    D = X - location
    d2 = np.einsum(
        "ij,jk,ik->i",
        D,
        precision,
        D,
    )
    return np.sqrt(
        np.clip(
            d2,
            0,
            None,
        )
    )


def guidance(pathway, tier):
    if pathway in [
        "GDE conservation / passive recovery",
        "Natural sparse/open conservation",
        "Herbaceous/exclosure passive recovery",
    ]:
        return (
            "not_applicable",
            "No numerical planting density; conservation/passive guidance only",
        )

    if pathway == "Close-to-nature structural management":
        if tier == "high":
            return (
                "local_structural_reference_only",
                "Existing-stand density reference may be consulted, but local stand inventory is required",
            )
        return (
            "no_numeric_density",
            "Use structural-management guidance only; do not transfer stems/ha",
        )

    if pathway in [
        "Low-tree mixed restoration",
        "Shrub-herbaceous restoration",
    ]:
        if tier == "high":
            return (
                "provisional_local_reference",
                "Horqin–Otindag density/species references may be used as a provisional planning envelope only after local species/site screening",
            )

        if tier == "moderate":
            return (
                "functional_structure_only",
                "Report LAI, occupancy and life-form structure; no stems/ha or species prescription",
            )

        return (
            "regional_structure_only",
            "Report LAI + occupancy + life-form structure only; local density/species references are outside their empirical domain",
        )

    return (
        "no_numeric_density",
        "Local calibration required",
    )


def main(root: Path):
    root = root.expanduser().resolve()

    ref_path = root / "R09B_ReferenceDomain_Environment.csv"
    panel_path = root / "R02_ClassYear_With_LAIcapPred.csv"
    static_path = root / "R01B1_Static_ByClass_FINAL.csv"
    r08_path = root / "R08_FinalManagement_ByClass.csv"

    required = [
        ref_path,
        panel_path,
        static_path,
        r08_path,
    ]

    missing = [
        str(p)
        for p in required
        if not p.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required files:\n"
            + "\n".join(missing)
        )

    ref = pd.read_csv(ref_path)
    panel = pd.read_csv(panel_path)
    static = pd.read_csv(static_path)
    r08 = pd.read_csv(r08_path)

    missing_ref_features = [
        c
        for c in FEATURES + ["SourceDomain"]
        if c not in ref.columns
    ]

    if missing_ref_features:
        raise KeyError(
            "Reference-domain table missing columns: "
            + ", ".join(missing_ref_features)
        )

    # --------------------------------------------------------
    # Build ClassCode mean environment
    # --------------------------------------------------------
    class_env = (
        panel
        .groupby(
            "ClassCode",
            as_index=False,
        )
        .agg(
            P_mm=("P_mm", "mean"),
            PET_mm=("PET_mm", "mean"),
            Soil_mm=("Soil_mm", "mean"),
            Tmean_C=("Tmean_C", "mean"),
            VPD_kPa=("VPD_kPa", "mean"),
            AI_P_PET=("AI_P_PET", "mean"),
        )
    )

    class_env = class_env.merge(
        static[
            [
                "ClassCode",
                "Elevation_m",
                "Slope_deg",
            ]
        ],
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    out = r08.merge(
        class_env,
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # One model per source domain
    # --------------------------------------------------------
    domain_summaries = []

    for domain in sorted(
        ref["SourceDomain"]
        .dropna()
        .astype(str)
        .unique()
    ):
        rr = ref[
            ref["SourceDomain"].astype(str) == domain
        ].dropna(
            subset=FEATURES
        ).copy()

        if len(rr) < 50:
            raise RuntimeError(
                f"Too few reference samples for {domain}: {len(rr)}"
            )

        med, scale = robust_scale_fit(
            rr,
            FEATURES,
        )

        X_ref = transform(
            rr,
            med,
            scale,
        ).to_numpy(float)

        lw = LedoitWolf().fit(
            X_ref
        )

        ref_dist = mahalanobis_distance(
            X_ref,
            lw.location_,
            lw.precision_,
        )

        q95 = float(
            np.quantile(
                ref_dist,
                0.95,
            )
        )

        q99 = float(
            np.quantile(
                ref_dist,
                0.99,
            )
        )

        # Source-domain 1st-99th percentiles.
        lo = rr[FEATURES].quantile(
            0.01
        )

        hi = rr[FEATURES].quantile(
            0.99
        )

        X_target = transform(
            out,
            med,
            scale,
        ).to_numpy(float)

        target_dist = mahalanobis_distance(
            X_target,
            lw.location_,
            lw.precision_,
        )

        within = (
            out[FEATURES]
            .ge(
                lo,
                axis=1,
            )
            & out[FEATURES]
            .le(
                hi,
                axis=1,
            )
        )

        envelope_fraction = within.mean(
            axis=1
        )

        tier = np.where(
            (target_dist <= q95)
            & (envelope_fraction >= 0.75),
            "high",
            np.where(
                (target_dist <= q99)
                | (envelope_fraction >= 0.75),
                "moderate",
                "low",
            ),
        )

        prefix = domain.replace(
            " ",
            "_",
        )

        out[
            f"R09_distance_{prefix}"
        ] = target_dist

        out[
            f"R09_envelope_fraction_{prefix}"
        ] = envelope_fraction

        out[
            f"R09_tier_{prefix}"
        ] = tier

        domain_summaries.append(
            {
                "SourceDomain": domain,
                "n_reference_samples": int(
                    len(rr)
                ),
                "distance_q95": q95,
                "distance_q99": q99,
            }
        )

    # --------------------------------------------------------
    # Best domain/tier
    # --------------------------------------------------------
    domains = [
        d["SourceDomain"]
        for d in domain_summaries
    ]

    best_domain = []
    best_tier = []
    best_dist = []
    best_envfrac = []

    for _, row in out.iterrows():
        candidates = []

        for domain in domains:
            prefix = domain.replace(
                " ",
                "_",
            )

            tier = row[
                f"R09_tier_{prefix}"
            ]

            dist = row[
                f"R09_distance_{prefix}"
            ]

            envfrac = row[
                f"R09_envelope_fraction_{prefix}"
            ]

            candidates.append(
                (
                    TIER_RANK.get(
                        str(tier),
                        -1,
                    ),
                    float(dist),
                    float(envfrac),
                    domain,
                    str(tier),
                )
            )

        # Highest tier; within same tier choose smaller distance.
        candidates = sorted(
            candidates,
            key=lambda x: (
                -x[0],
                x[1],
            ),
        )

        chosen = candidates[0]

        best_domain.append(
            chosen[3]
        )

        best_tier.append(
            chosen[4]
        )

        best_dist.append(
            chosen[1]
        )

        best_envfrac.append(
            chosen[2]
        )

    out["R09_best_reference_domain"] = best_domain
    out["R09_transferability_tier"] = best_tier
    out["R09_best_distance"] = best_dist
    out["R09_best_envelope_fraction"] = best_envfrac

    # --------------------------------------------------------
    # Density/species reporting policy
    # --------------------------------------------------------
    guidance_rows = []

    for _, row in out.iterrows():
        level, rule = guidance(
            row["FinalManagementPathway"],
            row["R09_transferability_tier"],
        )

        guidance_rows.append(
            {
                "ClassCode": int(
                    row["ClassCode"]
                ),
                "FinalManagementPathway": row[
                    "FinalManagementPathway"
                ],
                "TransferabilityTier": row[
                    "R09_transferability_tier"
                ],
                "BestReferenceDomain": row[
                    "R09_best_reference_domain"
                ],
                "DensityGuidanceLevel": level,
                "DensityReportingRule": rule,
            }
        )

    guidance_df = pd.DataFrame(
        guidance_rows
    )

    out = out.merge(
        guidance_df[
            [
                "ClassCode",
                "DensityGuidanceLevel",
                "DensityReportingRule",
            ]
        ],
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # Summaries
    # --------------------------------------------------------
    summary = (
        out.groupby(
            [
                "FinalManagementPathway",
                "R09_transferability_tier",
                "DensityGuidanceLevel",
            ],
            as_index=False,
        )
        .agg(
            n_ClassCode=(
                "ClassCode",
                "size",
            ),
            Area_km2=(
                "Area_km2",
                "sum",
            ),
        )
    )

    total_area = out[
        "Area_km2"
    ].sum()

    summary[
        "Area_share_pct"
    ] = (
        summary[
            "Area_km2"
        ]
        / total_area
        * 100
    )

    density_summary = (
        guidance_df
        .merge(
            out[
                [
                    "ClassCode",
                    "Area_km2",
                ]
            ],
            on="ClassCode",
            how="left",
            validate="one_to_one",
        )
        .groupby(
            "DensityGuidanceLevel",
            as_index=False,
        )
        .agg(
            n_ClassCode=(
                "ClassCode",
                "size",
            ),
            Area_km2=(
                "Area_km2",
                "sum",
            ),
        )
    )

    density_summary[
        "Area_share_pct"
    ] = (
        density_summary[
            "Area_km2"
        ]
        / total_area
        * 100
    )

    qa = {
        "rows": int(len(out)),
        "unique_classcodes": int(
            out["ClassCode"].nunique()
        ),
        "reference_domains": domains,
        "domain_summaries": domain_summaries,
        "tier_counts": {
            str(k): int(v)
            for k, v in out[
                "R09_transferability_tier"
            ]
            .value_counts()
            .to_dict()
            .items()
        },
        "density_guidance_counts": {
            str(k): int(v)
            for k, v in out[
                "DensityGuidanceLevel"
            ]
            .value_counts()
            .to_dict()
            .items()
        },
        "critical_interpretation": (
            "Only high-transferability classes may use local Horqin–Otindag "
            "density/species references as provisional planning envelopes; "
            "regional stems/ha prescriptions remain unsupported without "
            "local field/site calibration."
        ),
    }

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------
    out.to_csv(
        root / "R09C_Transferability_ByClass.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        root / "R09C_Transferability_Summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    density_summary.to_csv(
        root / "R09C_DensityGuidance_Summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    guidance_df.to_csv(
        root / "R09C_DensityReportingPolicy_ByClass.csv",
        index=False,
        encoding="utf-8-sig",
    )

    (root / "R09C_QA.json").write_text(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nR09C completed successfully.")
    print("\nTransferability summary:")
    print(
        summary.to_string(
            index=False
        )
    )
    print("\nDensity-guidance summary:")
    print(
        density_summary.to_string(
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R09B reference samples and revised model outputs",
    )

    args = parser.parse_args()

    main(
        Path(args.root)
    )
