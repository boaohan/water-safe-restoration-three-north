# -*- coding: utf-8 -*-
"""
R09A_engineering_reference_audit.py

Purpose
-------
Use the existing Horqin–Hunshandake engineering reference-range table only as
LOCAL EMPIRICAL ANCHORING, not as a universal Three-North density calibration.

This script:
1. Finds/copies S11_Engineering_ReferenceRanges_AllSandlands.csv.
2. Finds/copies ThreeNorth_SpeciesPool_Seed.csv.
3. Re-checks revised R08 LAI / life-form structure against engineering ranges
   for all available scopes (pooled_two_sandlands, Horqin, Hunshandake, etc.).
4. Audits the species pool and explicitly flags the current *_Seed file as a
   local/partial reference rather than a complete region-wide species database.
5. Creates a density-evidence policy. It does NOT calculate region-wide stems/ha.

Usage
-----
python R09A_engineering_reference_audit.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import shutil
import numpy as np
import pandas as pd


EXPECTED_FULL_SPECIES_N = 134  # documented in the original process notes


def find_first(paths):
    for p in paths:
        p = Path(p)
        if p.exists():
            return p
    return None


def bool_rate(s):
    s = s.dropna()
    if len(s) == 0:
        return np.nan
    return float(s.astype(bool).mean())


def in_range(x, lo, hi):
    if pd.isna(x) or pd.isna(lo) or pd.isna(hi):
        return np.nan
    return bool((x >= lo) and (x <= hi))


def map_engineering_group(pathway, available_groups):
    mapping = {
        "Low-tree mixed restoration": "tree_shrub_grass",
        "Close-to-nature structural management": "close_nature_management",
        "Herbaceous/exclosure passive recovery": "low_cover_shrub_grass",
    }

    group = mapping.get(pathway)

    if group is None:
        return None, False

    fallback = False

    if group not in available_groups:
        if (
            pathway == "Close-to-nature structural management"
            and "typical_shrub_grass" in available_groups
        ):
            group = "typical_shrub_grass"
            fallback = True
        else:
            return None, False

    return group, fallback


def density_policy(pathway):
    if pathway in [
        "GDE conservation / passive recovery",
        "Natural sparse/open conservation",
        "Herbaceous/exclosure passive recovery",
    ]:
        return (
            "No planting-density prescription",
            "LAI / cover / conservation guidance only",
        )

    if pathway == "Close-to-nature structural management":
        return (
            "Existing-stand density management only",
            "No regional stems/ha transfer; local stand inventory required",
        )

    if pathway == "Low-tree mixed restoration":
        return (
            "Local-reference density translation only",
            "Do not report region-wide stems/ha until environmental transferability "
            "and local species/site calibration are demonstrated",
        )

    if pathway == "Shrub-herbaceous restoration":
        return (
            "Local-reference shrub density only",
            "Do not report region-wide individuals/ha without local calibration",
        )

    return (
        "No regional density prescription",
        "Local calibration required",
    )


def main(root: Path):
    root = root.expanduser().resolve()

    r08_path = root / "R08_FinalManagement_ByClass.csv"
    r04_path = root / "R04_Class_LAIsafe.csv"

    if not r08_path.exists():
        raise FileNotFoundError(r08_path)
    if not r04_path.exists():
        raise FileNotFoundError(r04_path)

    # --------------------------------------------------------
    # Locate local reference files
    # --------------------------------------------------------
    ref_candidates = [
        root / "S11_Engineering_ReferenceRanges_AllSandlands.csv",
    ]

    species_candidates = [
        root / "ThreeNorth_SpeciesPool_Seed.csv",
    ]

    ref_path = find_first(ref_candidates)
    species_path = find_first(species_candidates)

    if ref_path is None:
        raise FileNotFoundError(
            "\nCannot find S11_Engineering_ReferenceRanges_AllSandlands.csv.\n"
            "Expected one of:\n"
            + "\n".join(str(x) for x in ref_candidates)
            + "\n\nLocate this file first. It is the engineering reference-range "
              "table used by the earlier S11 validation."
        )

    if species_path is None:
        raise FileNotFoundError(
            "\nCannot find ThreeNorth_SpeciesPool_Seed.csv.\n"
            "Expected one of:\n"
            + "\n".join(str(x) for x in species_candidates)
        )

    # Reproducible copies into current root.
    if ref_path.resolve() != (root / ref_path.name).resolve():
        shutil.copy2(ref_path, root / ref_path.name)
        ref_path = root / ref_path.name

    if species_path.resolve() != (root / species_path.name).resolve():
        shutil.copy2(species_path, root / species_path.name)
        species_path = root / species_path.name

    # --------------------------------------------------------
    # Read inputs
    # --------------------------------------------------------
    r08 = pd.read_csv(r08_path)
    r04 = pd.read_csv(r04_path)
    ref = pd.read_csv(ref_path)
    species = pd.read_csv(species_path)

    model = r08.merge(
        r04[
            [
                "ClassCode",
                "LAI_safe",
                "LAI_hydro",
                "LAI_current_3yr",
                "safe_ratio",
            ]
        ],
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    required_ref = [
        "scope",
        "engineering_group",
        "capacity_min",
        "capacity_max",
        "tree_ratio_min",
        "tree_ratio_max",
        "shrub_ratio_min",
        "shrub_ratio_max",
        "grass_ratio_min",
        "grass_ratio_max",
    ]

    missing_ref = [c for c in required_ref if c not in ref.columns]
    if missing_ref:
        raise KeyError(
            "Engineering reference table missing columns: "
            + ", ".join(missing_ref)
        )

    # Numeric conversion.
    numeric_ref = [
        c
        for c in ref.columns
        if any(
            key in c
            for key in [
                "capacity",
                "ratio",
                "_min",
                "_max",
                "_p05",
                "_p95",
                "_median",
            ]
        )
    ]

    for c in numeric_ref:
        ref[c] = pd.to_numeric(ref[c], errors="coerce")

    # Ensure p05/p95/median exist.
    for v in [
        "capacity",
        "tree_ratio",
        "shrub_ratio",
        "grass_ratio",
    ]:
        if f"{v}_p05" not in ref.columns:
            ref[f"{v}_p05"] = ref[f"{v}_min"]
        if f"{v}_p95" not in ref.columns:
            ref[f"{v}_p95"] = ref[f"{v}_max"]
        if f"{v}_median" not in ref.columns:
            ref[f"{v}_median"] = (
                ref[f"{v}_min"] + ref[f"{v}_max"]
            ) / 2.0

    # --------------------------------------------------------
    # Validation for every available scope
    # --------------------------------------------------------
    detail_rows = []

    scopes = [
        x
        for x in [
            "pooled_two_sandlands",
            "Horqin",
            "Hunshandake",
        ]
        if x in set(ref["scope"].astype(str))
    ]

    # Also retain any extra scopes.
    for x in sorted(set(ref["scope"].astype(str))):
        if x not in scopes:
            scopes.append(x)

    for scope in scopes:
        ref_scope = ref[
            ref["scope"].astype(str) == str(scope)
        ].copy()

        available_groups = set(
            ref_scope["engineering_group"]
            .dropna()
            .astype(str)
        )

        for _, row in model.iterrows():
            group, fallback = map_engineering_group(
                row["FinalManagementPathway"],
                available_groups,
            )

            base = {
                "scope": scope,
                "ClassCode": int(row["ClassCode"]),
                "BaseZone": int(row["BaseZone"]),
                "GDE_Level": int(row["GDE_Level"]),
                "Area_km2": float(row["Area_km2"]),
                "FinalManagementPathway": row["FinalManagementPathway"],
                "engineering_group": group,
                "reference_group_fallback": fallback,
                "LAI_safe": row["LAI_safe"],
                "LAI_target": row["LAI_target"],
                "q_tree": row["q_tree"],
                "q_shrub": row["q_shrub"],
                "q_herb": row["q_herb"],
            }

            if group is None:
                base.update(
                    {
                        "reference_available": False,
                        "capacity_within_p05_p95": np.nan,
                        "capacity_within_minmax": np.nan,
                        "tree_within_p05_p95": np.nan,
                        "shrub_within_p05_p95": np.nan,
                        "grass_within_p05_p95": np.nan,
                        "all_ratios_within_p05_p95": np.nan,
                    }
                )
                detail_rows.append(base)
                continue

            rr = ref_scope[
                ref_scope["engineering_group"].astype(str)
                == str(group)
            ]

            if len(rr) == 0:
                base["reference_available"] = False
                detail_rows.append(base)
                continue

            rr = rr.iloc[0]
            base["reference_available"] = True

            # Safe LAI is the relevant regional water-safety boundary.
            base["capacity_within_p05_p95"] = in_range(
                row["LAI_safe"],
                rr["capacity_p05"],
                rr["capacity_p95"],
            )

            base["capacity_within_minmax"] = in_range(
                row["LAI_safe"],
                rr["capacity_min"],
                rr["capacity_max"],
            )

            # Ratios are only meaningful for optimized rows with q values.
            base["tree_within_p05_p95"] = in_range(
                row["q_tree"],
                rr["tree_ratio_p05"],
                rr["tree_ratio_p95"],
            )

            base["shrub_within_p05_p95"] = in_range(
                row["q_shrub"],
                rr["shrub_ratio_p05"],
                rr["shrub_ratio_p95"],
            )

            base["grass_within_p05_p95"] = in_range(
                row["q_herb"],
                rr["grass_ratio_p05"],
                rr["grass_ratio_p95"],
            )

            ratio_flags = [
                base["tree_within_p05_p95"],
                base["shrub_within_p05_p95"],
                base["grass_within_p05_p95"],
            ]

            if all(pd.notna(x) for x in ratio_flags):
                base["all_ratios_within_p05_p95"] = bool(
                    all(ratio_flags)
                )
            else:
                base["all_ratios_within_p05_p95"] = np.nan

            detail_rows.append(base)

    detail = pd.DataFrame(detail_rows)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    summary_rows = []

    for (scope, pathway), g in detail.groupby(
        ["scope", "FinalManagementPathway"],
        dropna=False,
        sort=True,
    ):
        available = g[g["reference_available"] == True].copy()

        summary_rows.append(
            {
                "scope": scope,
                "FinalManagementPathway": pathway,
                "n_ClassCode": int(len(g)),
                "n_reference_available": int(len(available)),
                "capacity_p05_p95_rate": bool_rate(
                    available["capacity_within_p05_p95"]
                ),
                "capacity_minmax_rate": bool_rate(
                    available["capacity_within_minmax"]
                ),
                "all_ratios_p05_p95_rate": bool_rate(
                    available["all_ratios_within_p05_p95"]
                ),
            }
        )

    summary = pd.DataFrame(summary_rows)

    # --------------------------------------------------------
    # Species-pool audit
    # --------------------------------------------------------
    species_counts = (
        species["life_form"]
        .astype(str)
        .value_counts()
        .to_dict()
        if "life_form" in species.columns
        else {}
    )

    species_audit = {
        "species_file": str(species_path),
        "species_rows": int(len(species)),
        "documented_full_species_n": EXPECTED_FULL_SPECIES_N,
        "is_full_documented_134_species_pool": bool(
            len(species) >= EXPECTED_FULL_SPECIES_N
        ),
        "life_form_counts": {
            str(k): int(v)
            for k, v in species_counts.items()
        },
        "has_density_min_max": bool(
            {"density_min", "density_max"}.issubset(
                species.columns
            )
        ),
        "has_lai_coeff": bool(
            "lai_coeff" in species.columns
        ),
        "recommended_use": (
            "Local Horqin–Hunshandake implementation example / "
            "candidate screening only; not a universal Three-North "
            "species or density calibration."
        ),
    }

    # --------------------------------------------------------
    # Density evidence policy
    # --------------------------------------------------------
    policy_rows = []

    for pathway in sorted(
        model["FinalManagementPathway"]
        .dropna()
        .unique()
    ):
        level, rule = density_policy(pathway)

        policy_rows.append(
            {
                "FinalManagementPathway": pathway,
                "DensityEvidenceLevel": level,
                "ReportingRule": rule,
            }
        )

    policy = pd.DataFrame(policy_rows)

    qa = {
        "model_rows": int(len(model)),
        "model_unique_classcodes": int(
            model["ClassCode"].nunique()
        ),
        "reference_file": str(ref_path),
        "reference_scopes": scopes,
        "reference_groups": sorted(
            set(
                ref["engineering_group"]
                .dropna()
                .astype(str)
            )
        ),
        "species_audit": species_audit,
        "key_conclusion": (
            "Current local reference sources support engineering-range "
            "consistency checks, but do not justify region-wide numerical "
            "stems/ha transfer."
        ),
    }

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------
    detail.to_csv(
        root / "R09A_EngineeringReference_Validation.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        root / "R09A_EngineeringReference_Summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    policy.to_csv(
        root / "R09A_DensityEvidencePolicy.csv",
        index=False,
        encoding="utf-8-sig",
    )

    (root / "R09A_InputAudit.json").write_text(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nR09A completed successfully.")
    print("\nReference scopes:", scopes)
    print("\nEngineering validation summary:")
    print(summary.to_string(index=False))
    print("\nSpecies audit:")
    print(json.dumps(species_audit, ensure_ascii=False, indent=2))
    print("\nDensity evidence policy:")
    print(policy.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R08 and R04 outputs",
    )
    args = parser.parse_args()
    main(Path(args.root))
