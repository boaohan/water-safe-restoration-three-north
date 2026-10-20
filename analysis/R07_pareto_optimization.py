# -*- coding: utf-8 -*-
"""
R07_pareto_optimization.py

Revised four-objective Pareto optimization for the canonical 58-unit workflow.

Inputs
------
- R06_CandidateLibrary.csv
- R02_ClassYear_With_LAIcapPred.csv

Scientific design
-----------------
Only R05 gates 3–5 enter optimization. Gates 0–2 were already translated to
direct conservative management in R06_DirectManagement.csv.

Four objectives:
1) maximize sand-fixation benefit
2) maximize ecological stability / empirical plausibility
3) minimize water pressure
4) minimize GDE risk

Unlike the rejected workflow, all four objectives contain candidate-specific
terms. Class-level environmental variables are used as background context, but
they are never the sole driver of within-ClassCode Pareto ranking.

Independent Dynamic World / WorldCover data are NOT used in these objectives;
they remain external validation evidence.

Usage
-----
python R07_pareto_optimization.py --root "build/run"
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

EPS = 1e-12
RANDOM_SEED = 42
N_RANDOM_WEIGHTS = 1000

W_BASE = np.array([0.25, 0.25, 0.25, 0.25], dtype=float)


def robust_minmax(s, q_low=0.05, q_high=0.95, reverse=False):
    x = pd.to_numeric(s, errors="coerce").astype(float)

    lo = x.quantile(q_low)
    hi = x.quantile(q_high)

    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out = pd.Series(np.zeros(len(x)), index=x.index, dtype=float)
    else:
        out = (x.clip(lo, hi) - lo) / (hi - lo)

    if reverse:
        out = 1.0 - out

    return out.fillna(0.0)


def neutral_minmax_array(x, maximize=True):
    """
    Local 0-1 normalization for Pareto-front compromise scoring.
    Constant objectives receive a neutral score of 0.5.
    """
    x = np.asarray(x, dtype=float)
    lo = np.nanmin(x)
    hi = np.nanmax(x)

    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo <= EPS:
        return np.full(len(x), 0.5, dtype=float)

    z = (x - lo) / (hi - lo)

    if not maximize:
        z = 1.0 - z

    return z


def shannon_diversity_3(q_tree, q_shrub, q_herb):
    q = np.column_stack([q_tree, q_shrub, q_herb]).astype(float)

    logq = np.zeros_like(q)
    mask = q > 0
    logq[mask] = np.log(q[mask])

    h = -(q * logq).sum(axis=1)

    return np.clip(h / np.log(3.0), 0.0, 1.0)


def moderate_use_score(u, optimum=0.75):
    u = np.asarray(u, dtype=float)

    return np.clip(
        1.0 - np.abs(u - optimum) / max(optimum, EPS),
        0.0,
        1.0,
    )


def pareto_front_mask(obj1_max, obj2_max, obj3_min, obj4_min):
    """
    Vectorized nondominated-front detection.

    All objectives are converted internally to minimization:
      [-obj1, -obj2, obj3, obj4]
    """
    z = np.column_stack(
        [
            -np.asarray(obj1_max, dtype=float),
            -np.asarray(obj2_max, dtype=float),
            np.asarray(obj3_min, dtype=float),
            np.asarray(obj4_min, dtype=float),
        ]
    )

    # dominates[j, i] = candidate j dominates candidate i
    better_equal = (
        z[:, None, :] <= z[None, :, :] + EPS
    ).all(axis=2)

    strictly_better = (
        z[:, None, :] < z[None, :, :] - EPS
    ).any(axis=2)

    dominates = better_equal & strictly_better

    dominated = dominates.any(axis=0)

    return ~dominated


def crowding_distance(front):
    """
    NSGA-style crowding distance on the four raw objectives.
    """
    n = len(front)

    if n == 0:
        return np.array([], dtype=float)

    if n <= 2:
        return np.full(n, np.inf, dtype=float)

    # Convert all to maximization for ordering.
    vals = np.column_stack(
        [
            front["obj1_sand_benefit"].to_numpy(float),
            front["obj2_eco_stability"].to_numpy(float),
            -front["obj3_water_pressure"].to_numpy(float),
            -front["obj4_gde_risk"].to_numpy(float),
        ]
    )

    dist = np.zeros(n, dtype=float)

    for k in range(vals.shape[1]):
        x = vals[:, k]
        order = np.argsort(x)

        dist[order[0]] = np.inf
        dist[order[-1]] = np.inf

        xmin = x[order[0]]
        xmax = x[order[-1]]

        if xmax - xmin <= EPS:
            continue

        for pos in range(1, n - 1):
            i = order[pos]
            prev_v = x[order[pos - 1]]
            next_v = x[order[pos + 1]]

            if not np.isinf(dist[i]):
                dist[i] += (next_v - prev_v) / (xmax - xmin)

    return dist


def choose_best(front, weights):
    """
    Choose best compromise within one Pareto front.
    """
    s1 = neutral_minmax_array(
        front["obj1_sand_benefit"],
        maximize=True,
    )

    s2 = neutral_minmax_array(
        front["obj2_eco_stability"],
        maximize=True,
    )

    s3 = neutral_minmax_array(
        front["obj3_water_pressure"],
        maximize=False,
    )

    s4 = neutral_minmax_array(
        front["obj4_gde_risk"],
        maximize=False,
    )

    score_matrix = np.column_stack([s1, s2, s3, s4])
    score = score_matrix @ np.asarray(weights, dtype=float)

    max_score = np.nanmax(score)
    tied = np.where(
        np.isclose(score, max_score, atol=1e-12)
    )[0]

    if len(tied) == 1:
        pos = int(tied[0])
    else:
        sub = front.iloc[tied].copy()
        sub["_score"] = score[tied]

        # Deterministic tie-break:
        # more Pareto spread, then lower water/GDE pressure,
        # then higher sand benefit.
        sub = sub.sort_values(
            [
                "crowding_distance",
                "obj3_water_pressure",
                "obj4_gde_risk",
                "obj1_sand_benefit",
                "CandidateID",
            ],
            ascending=[
                False,
                True,
                True,
                False,
                True,
            ],
        )

        chosen_id = sub.iloc[0]["CandidateID"]
        pos = int(
            np.where(
                front["CandidateID"].to_numpy() == chosen_id
            )[0][0]
        )

    return pos, score, score_matrix


def weighted_mean(x, w):
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)

    ok = np.isfinite(x) & np.isfinite(w) & (w >= 0)
    x = x[ok]
    w = w[ok]

    if len(x) == 0 or w.sum() <= 0:
        return np.nan

    return float(np.average(x, weights=w))


def main(root: Path):
    root = root.expanduser().resolve()

    candidate_path = root / "R06_CandidateLibrary.csv"
    panel_path = root / "R02_ClassYear_With_LAIcapPred.csv"

    missing = [
        str(p)
        for p in [candidate_path, panel_path]
        if not p.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required files:\n"
            + "\n".join(missing)
        )

    cand = pd.read_csv(candidate_path)
    panel = pd.read_csv(panel_path)

    # -----------------------------------------------------------------
    # 1. Class-level observed background from 2005–2024 annual panel
    # -----------------------------------------------------------------
    class_bg = (
        panel
        .groupby("ClassCode", as_index=False)
        .agg(
            NDVI_mean=("NDVI_gs", "mean"),
            NDVI_std=("NDVI_gs", "std"),
            NPP_mean=("NPP_kgC_m2", "mean"),
            NPP_std=("NPP_kgC_m2", "std"),
            WUE_mean=("WUE_kgC_m2_per_mm", "mean"),
            WUE_std=("WUE_kgC_m2_per_mm", "std"),

            AET_P_mean=("AET_P", "mean"),
            PET_P_mean=("PET_P", "mean"),
            Soil_mean=("Soil_mm", "mean"),

            WindRisk_mean=("WindErosionRisk", "mean"),
            Bare_mean=("BareSoilFrac", "mean"),
            SandConnectivity_mean=("SandConnectivity", "mean"),

            FVC_nat_mean=("FVC_nat", "mean"),
            LAI_nat_mean_ref=("LAI_nat_mean", "mean"),

            NaturalRefAreaShare=("NaturalRefAreaShare", "first"),
            GWSA_trend=("GWSA_trend", "first"),
        )
    )

    # -----------------------------------------------------------------
    # 2. Real ecological-background index
    # -----------------------------------------------------------------
    ndvi_mean_n = robust_minmax(
        class_bg["NDVI_mean"]
    )
    ndvi_std_n = robust_minmax(
        class_bg["NDVI_std"]
    )

    npp_mean_n = robust_minmax(
        class_bg["NPP_mean"]
    )
    npp_std_n = robust_minmax(
        class_bg["NPP_std"]
    )

    wue_mean_n = robust_minmax(
        class_bg["WUE_mean"]
    )
    wue_std_n = robust_minmax(
        class_bg["WUE_std"]
    )

    class_bg["eco_background_real"] = (
        ndvi_mean_n
        * (
            0.50
            * npp_mean_n
            * (1.0 - npp_std_n)
            + 0.25
            * wue_mean_n
            * (1.0 - wue_std_n)
            + 0.25
            * ndvi_mean_n
            * (1.0 - ndvi_std_n)
        )
    ).clip(0.0, 1.0)

    # -----------------------------------------------------------------
    # 3. Water-stress background
    # -----------------------------------------------------------------
    class_bg["GWSA_decline"] = (
        -class_bg["GWSA_trend"]
    ).clip(lower=0.0)

    hydro_parts = [
        robust_minmax(class_bg["AET_P_mean"]),
        robust_minmax(class_bg["PET_P_mean"]),
        robust_minmax(
            class_bg["Soil_mean"],
            reverse=True,
        ),
        robust_minmax(class_bg["GWSA_decline"]),
    ]

    class_bg["hydro_stress_base"] = np.vstack(
        [x.to_numpy(float) for x in hydro_parts]
    ).mean(axis=0)

    # -----------------------------------------------------------------
    # 4. Sand-fixation demand background
    # -----------------------------------------------------------------
    sand_parts = [
        robust_minmax(class_bg["WindRisk_mean"]),
        robust_minmax(class_bg["Bare_mean"]),
        robust_minmax(
            class_bg["SandConnectivity_mean"]
        ),
    ]

    class_bg["sand_demand_base"] = np.vstack(
        [x.to_numpy(float) for x in sand_parts]
    ).mean(axis=0)

    # -----------------------------------------------------------------
    # 5. Join candidate library
    # -----------------------------------------------------------------
    work = cand.merge(
        class_bg,
        on="ClassCode",
        how="left",
        validate="many_to_one",
    )

    if work[
        [
            "eco_background_real",
            "hydro_stress_base",
            "sand_demand_base",
        ]
    ].isna().any().any():
        raise RuntimeError(
            "Missing class-level background values after merge."
        )

    # -----------------------------------------------------------------
    # 6. Candidate-specific derived variables
    # -----------------------------------------------------------------
    work["V_utilization"] = (
        work["V_target"]
        / work["V_hydro"].replace(0, np.nan)
    ).clip(0.0, 1.2).fillna(0.0)

    work["LAI_utilization"] = (
        work["LAI_target"]
        / work["LAI_safe"].replace(0, np.nan)
    ).clip(0.0, 1.2).fillna(0.0)

    work["structure_diversity"] = shannon_diversity_3(
        work["q_tree"],
        work["q_shrub"],
        work["q_herb"],
    )

    mean_use = (
        work["V_utilization"]
        + work["LAI_utilization"]
    ) / 2.0

    work["moderate_use"] = moderate_use_score(
        mean_use,
        optimum=0.75,
    )

    # Natural-reference similarity:
    # use observed natural FVC / LAI envelope, but down-weight it
    # when natural-reference support is weak.
    v_similarity = (
        1.0
        - (
            np.abs(
                work["V_target"]
                - work["FVC_nat_mean"]
            )
            / np.maximum(
                work["V_hydro"],
                0.10,
            )
        ).clip(0.0, 1.0)
    )

    lai_similarity = (
        1.0
        - (
            np.abs(
                work["LAI_target"]
                - work["LAI_nat_mean_ref"]
            )
            / np.maximum(
                work["LAI_safe"],
                0.20,
            )
        ).clip(0.0, 1.0)
    )

    raw_nat_similarity = (
        v_similarity
        + lai_similarity
    ) / 2.0

    ref_support_weight = (
        work["NaturalRefAreaShare"]
        / 0.20
    ).clip(0.0, 1.0)

    work["natural_reference_similarity"] = (
        ref_support_weight
        * raw_nat_similarity
        + (
            1.0
            - ref_support_weight
        )
        * 0.50
    )

    work["tree_canopy_burden"] = (
        work["LAI_tree"]
        / work["LAI_safe"].replace(0, np.nan)
    ).clip(0.0, 1.2).fillna(0.0)

    # -----------------------------------------------------------------
    # 7. Revised four candidate-specific objectives
    # -----------------------------------------------------------------

    # Objective 1 — maximize sand-fixation benefit.
    #
    # High vegetation occupancy and LAI increase protective function;
    # three-layer structural diversity provides an additional but modest
    # roughness / structural-complexity term.
    #
    # Sand demand is a positive class-level multiplier only; it does not
    # by itself create artificial within-class candidate differences.
    work["obj1_sand_benefit"] = (
        (
            0.50 * work["V_utilization"]
            + 0.30 * work["LAI_utilization"]
            + 0.20 * work["structure_diversity"]
        )
        * (
            0.60
            + 0.40 * work["sand_demand_base"]
        )
    ).clip(0.0, 1.5)

    # Objective 2 — maximize ecological stability / empirical plausibility.
    #
    # 45%: observed long-term NDVI/NPP/WUE stability background
    # 35%: similarity to natural-reference FVC + LAI envelope
    # 20%: moderate use of available LAI/occupancy space
    work["obj2_eco_stability"] = (
        0.45
        * work["eco_background_real"]
        + 0.35
        * work["natural_reference_similarity"]
        + 0.20
        * work["moderate_use"]
    ).clip(0.0, 1.0)

    # Objective 3 — minimize water pressure.
    #
    # Background hydro stress is combined with candidate-specific
    # utilization of the safe vertical and horizontal capacity.
    work["obj3_water_pressure"] = (
        0.35
        * work["hydro_stress_base"]
        + 0.325
        * work["LAI_utilization"]
        + 0.325
        * work["V_utilization"]
    ).clip(0.0, 1.5)

    # Objective 4 — minimize GDE risk.
    #
    # The class-level GDE risk R_gde is modulated by candidate LAI,
    # occupancy utilization, and tree-canopy burden.
    work["obj4_gde_risk"] = (
        work["R_gde"]
        * (
            0.40
            + 0.30
            * work["LAI_utilization"]
            + 0.15
            * work["V_utilization"]
            + 0.15
            * work["tree_canopy_burden"]
        )
    ).clip(0.0, 1.5)

    # -----------------------------------------------------------------
    # 8. Pareto front + equal-weight best compromise
    # -----------------------------------------------------------------
    scored_frames = []
    pareto_frames = []
    best_rows = []
    range_rows = []
    weight_rows = []

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    random_weights = rng.dirichlet(
        np.ones(4),
        size=N_RANDOM_WEIGHTS,
    )

    fixed_weight_scenarios = {
        "equal": np.array([0.25, 0.25, 0.25, 0.25]),
        "sand_first": np.array([0.40, 0.20, 0.20, 0.20]),
        "stability_first": np.array([0.20, 0.40, 0.20, 0.20]),
        "water_first": np.array([0.20, 0.20, 0.40, 0.20]),
        "gde_first": np.array([0.20, 0.20, 0.20, 0.40]),
    }

    for class_code, g in work.groupby(
        "ClassCode",
        sort=True,
    ):
        g = g.copy().reset_index(drop=True)

        front_mask = pareto_front_mask(
            g["obj1_sand_benefit"],
            g["obj2_eco_stability"],
            g["obj3_water_pressure"],
            g["obj4_gde_risk"],
        )

        g["is_pareto_front"] = (
            front_mask.astype(int)
        )

        g["pareto_rank"] = np.where(
            front_mask,
            1,
            np.nan,
        )

        front = g.loc[
            front_mask
        ].copy().reset_index(drop=True)

        front["crowding_distance"] = crowding_distance(
            front
        )

        # Baseline equal-weight best compromise.
        best_pos, base_score, score_matrix = choose_best(
            front,
            W_BASE,
        )

        front["score_sand_local"] = score_matrix[:, 0]
        front["score_stability_local"] = score_matrix[:, 1]
        front["score_water_security_local"] = score_matrix[:, 2]
        front["score_gde_safety_local"] = score_matrix[:, 3]
        front["best_compromise_score"] = base_score

        best = front.iloc[
            best_pos
        ].copy()

        best["is_best_compromise"] = 1

        # Push front information back to all candidates.
        front_lookup = front[
            [
                "CandidateID",
                "crowding_distance",
                "score_sand_local",
                "score_stability_local",
                "score_water_security_local",
                "score_gde_safety_local",
                "best_compromise_score",
            ]
        ]

        g = g.merge(
            front_lookup,
            on="CandidateID",
            how="left",
        )

        g["is_best_compromise"] = (
            g["CandidateID"]
            == best["CandidateID"]
        ).astype(int)

        scored_frames.append(g)
        pareto_frames.append(front)
        best_rows.append(best)

        # Pareto ranges.
        range_rows.append({
            "ClassCode": int(class_code),
            "n_candidates": int(len(g)),
            "n_pareto": int(len(front)),
            "q_tree_min": float(front["q_tree"].min()),
            "q_tree_max": float(front["q_tree"].max()),
            "q_shrub_min": float(front["q_shrub"].min()),
            "q_shrub_max": float(front["q_shrub"].max()),
            "q_herb_min": float(front["q_herb"].min()),
            "q_herb_max": float(front["q_herb"].max()),
            "V_target_min": float(front["V_target"].min()),
            "V_target_max": float(front["V_target"].max()),
            "LAI_target_min": float(front["LAI_target"].min()),
            "LAI_target_max": float(front["LAI_target"].max()),
            "f_open_min": float(front["f_open"].min()),
            "f_open_max": float(front["f_open"].max()),
        })

        # Weight sensitivity.
        baseline_structure = str(
            best["LifeFormStructure"]
        )

        baseline_tree_present = bool(
            best["q_tree"] > 0
        )

        # Fixed scenarios.
        for scenario, weights in fixed_weight_scenarios.items():
            pos, _, _ = choose_best(
                front,
                weights,
            )

            chosen = front.iloc[pos]

            weight_rows.append({
                "ClassCode": int(class_code),
                "Scenario": scenario,
                "CandidateID": chosen["CandidateID"],
                "LifeFormStructure": chosen["LifeFormStructure"],
                "q_tree": float(chosen["q_tree"]),
                "q_shrub": float(chosen["q_shrub"]),
                "q_herb": float(chosen["q_herb"]),
                "V_target": float(chosen["V_target"]),
                "LAI_target": float(chosen["LAI_target"]),
                "matches_equal_candidate": bool(
                    chosen["CandidateID"]
                    == best["CandidateID"]
                ),
                "matches_equal_structure": bool(
                    str(chosen["LifeFormStructure"])
                    == baseline_structure
                ),
            })

        # 1000 random Dirichlet weight combinations.
        random_selected = []

        # Reuse local objective-score matrix.
        for ridx, weights in enumerate(
            random_weights,
            start=1,
        ):
            score = score_matrix @ weights
            pos = int(
                np.argmax(score)
            )

            chosen = front.iloc[pos]

            random_selected.append({
                "CandidateID": chosen["CandidateID"],
                "LifeFormStructure": chosen["LifeFormStructure"],
                "q_tree": float(chosen["q_tree"]),
                "V_target": float(chosen["V_target"]),
                "LAI_target": float(chosen["LAI_target"]),
                "tree_present": bool(chosen["q_tree"] > 0),
            })

        random_df = pd.DataFrame(
            random_selected
        )

        weight_rows.append({
            "ClassCode": int(class_code),
            "Scenario": "Dirichlet1000_summary",
            "CandidateID": "",
            "LifeFormStructure": "",
            "q_tree": float(random_df["q_tree"].median()),
            "q_shrub": np.nan,
            "q_herb": np.nan,
            "V_target": float(random_df["V_target"].median()),
            "LAI_target": float(random_df["LAI_target"].median()),
            "matches_equal_candidate": float(
                (
                    random_df["CandidateID"]
                    == best["CandidateID"]
                ).mean()
            ),
            "matches_equal_structure": float(
                (
                    random_df["LifeFormStructure"]
                    == baseline_structure
                ).mean()
            ),
            "matches_equal_tree_presence": float(
                (
                    random_df["tree_present"]
                    == baseline_tree_present
                ).mean()
            ),
            "q_tree_p05": float(
                random_df["q_tree"].quantile(0.05)
            ),
            "q_tree_p95": float(
                random_df["q_tree"].quantile(0.95)
            ),
            "V_target_p05": float(
                random_df["V_target"].quantile(0.05)
            ),
            "V_target_p95": float(
                random_df["V_target"].quantile(0.95)
            ),
            "LAI_target_p05": float(
                random_df["LAI_target"].quantile(0.05)
            ),
            "LAI_target_p95": float(
                random_df["LAI_target"].quantile(0.95)
            ),
        })

    scored = pd.concat(
        scored_frames,
        ignore_index=True,
    )

    pareto = pd.concat(
        pareto_frames,
        ignore_index=True,
    )

    best_df = pd.DataFrame(
        best_rows
    ).sort_values(
        "ClassCode"
    )

    pareto_ranges = pd.DataFrame(
        range_rows
    ).sort_values(
        "ClassCode"
    )

    weight_sensitivity = pd.DataFrame(
        weight_rows
    ).sort_values(
        [
            "ClassCode",
            "Scenario",
        ]
    )

    # -----------------------------------------------------------------
    # 9. Summaries
    # -----------------------------------------------------------------
    best_summary = (
        best_df
        .groupby(
            [
                "GDE_Level",
                "EligibilityGateCode",
                "LifeFormStructure",
            ],
            as_index=False,
        )
        .agg(
            n_ClassCode=("ClassCode", "size"),
            Area_km2=("Area_km2", "sum"),
            median_q_tree=("q_tree", "median"),
            median_q_shrub=("q_shrub", "median"),
            median_q_herb=("q_herb", "median"),
            median_V_target=("V_target", "median"),
            median_LAI_target=("LAI_target", "median"),
            median_f_open=("f_open", "median"),
        )
    )

    dirichlet_summary = weight_sensitivity[
        weight_sensitivity["Scenario"]
        == "Dirichlet1000_summary"
    ].copy()

    # Area-weighted structure consistency.
    area_lookup = best_df[
        [
            "ClassCode",
            "Area_km2",
        ]
    ]

    dirichlet_summary = dirichlet_summary.merge(
        area_lookup,
        on="ClassCode",
        how="left",
        validate="one_to_one",
    )

    area_weighted_structure_consistency = weighted_mean(
        dirichlet_summary["matches_equal_structure"],
        dirichlet_summary["Area_km2"],
    )

    area_weighted_tree_presence_consistency = weighted_mean(
        dirichlet_summary["matches_equal_tree_presence"],
        dirichlet_summary["Area_km2"],
    )

    # -----------------------------------------------------------------
    # 10. QA
    # -----------------------------------------------------------------
    qa = {
        "candidate_rows": int(len(scored)),
        "optimized_classcodes": int(
            scored["ClassCode"].nunique()
        ),
        "pareto_rows": int(len(pareto)),
        "pareto_classcodes": int(
            pareto["ClassCode"].nunique()
        ),
        "best_rows": int(len(best_df)),
        "best_unique_classcodes": int(
            best_df["ClassCode"].nunique()
        ),
        "duplicate_best_classcodes": int(
            best_df["ClassCode"]
            .duplicated()
            .sum()
        ),
        "missing_objective_values": int(
            scored[
                [
                    "obj1_sand_benefit",
                    "obj2_eco_stability",
                    "obj3_water_pressure",
                    "obj4_gde_risk",
                ]
            ]
            .isna()
            .sum()
            .sum()
        ),
        "min_pareto_solutions_per_class": int(
            pareto_ranges["n_pareto"].min()
        ),
        "median_pareto_solutions_per_class": float(
            pareto_ranges["n_pareto"].median()
        ),
        "max_pareto_solutions_per_class": int(
            pareto_ranges["n_pareto"].max()
        ),
        "area_weighted_Dirichlet1000_structure_consistency": float(
            area_weighted_structure_consistency
        ),
        "area_weighted_Dirichlet1000_tree_presence_consistency": float(
            area_weighted_tree_presence_consistency
        ),
        "best_structure_counts": {
            str(k): int(v)
            for k, v in best_df[
                "LifeFormStructure"
            ]
            .value_counts()
            .to_dict()
            .items()
        },
    }

    # -----------------------------------------------------------------
    # 11. Export
    # -----------------------------------------------------------------
    out_scored = root / "R07_ScoredCandidates.csv"
    out_pareto = root / "R07_ParetoFront.csv"
    out_best = root / "R07_BestCompromise.csv"
    out_ranges = root / "R07_ParetoRanges_ByClass.csv"
    out_bg = root / "R07_ClassBackgroundMetrics.csv"
    out_best_summary = root / "R07_BestSummary.csv"
    out_weight = root / "R07_WeightSensitivity.csv"
    out_qa = root / "R07_QA.json"
    out_readme = root / "R07_README.txt"

    scored.to_csv(
        out_scored,
        index=False,
        encoding="utf-8-sig",
    )

    pareto.to_csv(
        out_pareto,
        index=False,
        encoding="utf-8-sig",
    )

    best_df.to_csv(
        out_best,
        index=False,
        encoding="utf-8-sig",
    )

    pareto_ranges.to_csv(
        out_ranges,
        index=False,
        encoding="utf-8-sig",
    )

    class_bg.to_csv(
        out_bg,
        index=False,
        encoding="utf-8-sig",
    )

    best_summary.to_csv(
        out_best_summary,
        index=False,
        encoding="utf-8-sig",
    )

    weight_sensitivity.to_csv(
        out_weight,
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
{json.dumps(qa, ensure_ascii=False, indent=2)}
""".strip()

    out_readme.write_text(
        readme,
        encoding="utf-8",
    )

    print("\nR07 completed successfully.")

    print("\nQA:")
    print(
        json.dumps(
            qa,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\nBest structures:")
    print(
        best_df[
            "LifeFormStructure"
        ]
        .value_counts()
        .to_string()
    )

    print("\nBest q_tree by GDE Level:")
    print(
        best_df
        .groupby("GDE_Level")[
            "q_tree"
        ]
        .describe()
        .to_string()
    )

    print("\nCreated:")
    for p in [
        out_scored,
        out_pareto,
        out_best,
        out_ranges,
        out_bg,
        out_best_summary,
        out_weight,
        out_qa,
        out_readme,
    ]:
        print(" -", p.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--root",
        required=True,
        help="Folder containing R06 candidate library and R02 panel",
    )

    args = parser.parse_args()

    main(
        Path(args.root)
    )
