"""
forecast.py

Phase 2 — Forecast model (2023–2033).

Approach:
    1. Fit a linear regression on annual new building GFA added (m^2),
       using NB permit data from 2001–2023.
    2. Project annual GFA for 2024–2033 with prediction intervals.
    3. Allocate projected GFA by building type using the historical type mix
       (% RS / RM / NR per year, averaged over the permit record).
    4. Apply Buy Clean policy filter:
         - From 2025 onwards, public buildings use Buy Clean GWP.
         - Private buildings remain at BAU GWP throughout.
    5. Calculate embodied carbon for each scenario using median RASMI intensities.

Key outputs
-----------
fit_gfa_regression(nb)        -> fitted OLS model + annual GFA summary
project_gfa(model, years)     -> DataFrame with projected GFA + prediction interval
forecast_embodied_carbon(nb)  -> DataFrame: year, scenario, broad_bldg_type,
                                            embodied_carbon_kgco2e
building_forecast_carbon(nb)  -> DataFrame: year, scenario, broad_bldg_type,
                                            ownership_type, gfa_m2,
                                            embodied_carbon_kgco2e
                                            (one row per simulated building)
fit_dm_regression(dm)         -> fitted OLS model + annual demolition volume summary
project_dm(dm_regression)     -> DataFrame with projected outflow volume by type
project_stock(...)            -> DataFrame: year, broad_bldg_type, stock_m3
                                            (forward projection from 2023 anchor)
"""

# import libraries
import numpy as np
import pandas as pd
from scipy import stats

# import constants
from constants import (
    HISTORICAL_START,
    HISTORICAL_END,
    FORECAST_END,
    BUY_CLEAN_START_YEAR,
    RANDOM_SEED,
    FLOOR_TO_FLOOR_M,
    RASMI_INTENSITIES,
    CEMENT_FRACTION_BY_TYPE,
    BAU_GWP_BY_TYPE,
    BUY_CLEAN_GWP_BY_TYPE,
)
# import calculations
from emissions import compute_gfa_m2_batch

BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]
OWNERSHIP_TYPES = ["public", "private"]

# Step 1: fit linear regression on annual GFA
def fit_gfa_regression(nb: pd.DataFrame) -> dict:
    """
    Fit OLS regression: annual_gfa_m2 ~ year, using historical NB permits.

    Returns a dict with:
        model       : scipy linregress result
        annual_gfa  : DataFrame(year, gfa_m2, gfa_m2_fit, residual)
        type_mix    : DataFrame(broad_bldg_type, mean_share) — historical mix
        ownership_mix : dict {broad_bldg_type: {ownership_type: share}}
    """
    btypes_valid = nb["broad_bldg_type"].isin(BTYPES)
    nb_hist = nb[
        nb["year"].between(HISTORICAL_START, HISTORICAL_END) & btypes_valid
    ].copy()

    # compute GFA per permit
    nb_hist["gfa_m2"] = compute_gfa_m2_batch(nb_hist)

    # annual total GFA
    annual = (
        nb_hist.groupby("year")["gfa_m2"]
        .sum()
        .reset_index()
        .rename(columns={"gfa_m2": "gfa_m2_total"})
        .dropna()
    )

    x = annual["year"].values.astype(float)
    y = annual["gfa_m2_total"].values

    result = stats.linregress(x, y)
    annual["gfa_m2_fit"] = result.slope * x + result.intercept
    annual["residual"]   = y - annual["gfa_m2_fit"].values

    # historical building type mix (share of annual GFA)
    annual_by_type = (
        nb_hist.groupby(["year", "broad_bldg_type"])["gfa_m2"]
        .sum()
        .reset_index()
    )
    annual_total = annual_by_type.groupby("year")["gfa_m2"].transform("sum")
    annual_by_type["share"] = annual_by_type["gfa_m2"] / annual_total
    type_mix = (
        annual_by_type.groupby("broad_bldg_type")["share"]
        .mean()
        .reindex(BTYPES, fill_value=0)
        .reset_index()
        .rename(columns={"share": "mean_share"})
    )
    # normalise so shares sum to 1
    type_mix["mean_share"] /= type_mix["mean_share"].sum()

    # ownership mix by building type (share that is public)
    ownership_mix = {}
    for btype in BTYPES:
        sub = nb_hist[nb_hist["broad_bldg_type"] == btype]
        gfa_by_own = sub.groupby("ownership_type")["gfa_m2"].sum()
        total = gfa_by_own.sum()
        ownership_mix[btype] = {
            own: gfa_by_own.get(own, 0) / total if total > 0 else 0
            for own in OWNERSHIP_TYPES
        }

    return {
        "model":         result,
        "annual_gfa":    annual,
        "type_mix":      type_mix,
        "ownership_mix": ownership_mix,
    }


# Step 2 — project GFA with prediction intervals
def project_gfa(
        regression: dict,
        forecast_years: range = None,
        confidence: float = 0.90,
    ) -> pd.DataFrame:
    """
    Project annual GFA (m²) for forecast years with prediction intervals.

    Uses the standard OLS prediction interval formula:
        ŷ ± t * se * sqrt(1 + 1/n + (x - x̄)² / Sxx)

    Parameters:
    regression     : output of fit_gfa_regression()
    forecast_years : iterable of years to project (default 2024–FORECAST_END)
    confidence     : prediction interval confidence level (default 0.90)

    Returns:
    DataFrame: year, gfa_m2_forecast, gfa_m2_lower, gfa_m2_upper
    """
    if forecast_years is None:
        forecast_years = range(HISTORICAL_END + 1, FORECAST_END + 1)

    model       = regression["model"]
    annual_gfa  = regression["annual_gfa"]

    x_hist = annual_gfa["year"].values.astype(float)
    y_hist = annual_gfa["gfa_m2_total"].values
    n = len(x_hist)
    x_mean = x_hist.mean()
    sxx = np.sum((x_hist - x_mean) ** 2)
    se = model.stderr  # standard error of slope; use residual std for prediction
    residual_std = np.std(annual_gfa["residual"].values, ddof=2)

    t_crit = stats.t.ppf((1 + confidence) / 2, df=n - 2)

    rows = []
    for yr in forecast_years:
        y_hat = model.slope * yr + model.intercept
        pred_se = residual_std * np.sqrt(1 + 1 / n + (yr - x_mean) ** 2 / sxx)
        margin = t_crit * pred_se
        rows.append({
            "year":             yr,
            "gfa_m2_forecast":  max(0, y_hat),
            "gfa_m2_lower":     max(0, y_hat - margin),
            "gfa_m2_upper":     max(0, y_hat + margin),
        })

    return pd.DataFrame(rows)

# Step 3 — allocate projected GFA by buiding type and ownership (private vs. public)
def allocate_gfa(projected: pd.DataFrame, regression: dict) -> pd.DataFrame:
    """
    Allocate total projected annual GFA to building type × ownership.

    Returns a long DataFrame:
        year, broad_bldg_type, ownership_type,
        gfa_m2, gfa_m2_lower, gfa_m2_upper
    """
    type_mix      = regression["type_mix"].set_index("broad_bldg_type")["mean_share"]
    ownership_mix = regression["ownership_mix"]

    rows = []
    for _, row in projected.iterrows():
        for btype in BTYPES:
            type_share = type_mix.get(btype, 0)
            for own in OWNERSHIP_TYPES:
                own_share = ownership_mix.get(btype, {}).get(own, 0)
                share = type_share * own_share
                rows.append({
                    "year":            int(row["year"]),
                    "broad_bldg_type": btype,
                    "ownership_type":  own,
                    "gfa_m2":          row["gfa_m2_forecast"] * share,
                    "gfa_m2_lower":    row["gfa_m2_lower"] * share,
                    "gfa_m2_upper":    row["gfa_m2_upper"] * share,
                })
    
    return pd.DataFrame(rows)

# Step 4 — embodied carbon for BAU and Buy Clean scenarios
def forecast_embodied_carbon(
        allocated_gfa: pd.DataFrame,
    ) -> pd.DataFrame:
    """
    Calculate embodied carbon for BAU and Buy Clean scenarios.

    Buy Clean applies to public buildings from BUY_CLEAN_START_YEAR.
    Uses median RASMI cement intensities.

    Returns a long DataFrame:
        year, scenario, broad_bldg_type, ownership_type,
        gfa_m2, embodied_carbon_kgco2e
    """
    rows = []
    for scenario in ["BAU", "BuyClean"]:
        for _, row in allocated_gfa.iterrows():
            yr      = row["year"]
            btype   = row["broad_bldg_type"]
            own     = row["ownership_type"]
            gfa     = row["gfa_m2"]

            intensity       = RASMI_INTENSITIES[btype]["p50"]
            cement_fraction = CEMENT_FRACTION_BY_TYPE[btype]

            if scenario == "BAU":
                gwp = BAU_GWP_BY_TYPE[btype]
            else:
                # Buy Clean: public buildings from 2025; private always BAU
                if own == "public" and yr >= BUY_CLEAN_START_YEAR:
                    gwp = BUY_CLEAN_GWP_BY_TYPE[btype]
                else:
                    gwp = BAU_GWP_BY_TYPE[btype]

            cement_mass    = gfa * intensity
            concrete_vol   = cement_mass / cement_fraction
            carbon         = concrete_vol * gwp

            rows.append({
                "year":                     yr,
                "scenario":                 scenario,
                "broad_bldg_type":          btype,
                "ownership_type":           own,
                "gfa_m2":                   gfa,
                "embodied_carbon_kgco2e":   carbon,
            })

    return pd.DataFrame(rows)

# Step 5 — per-building forecast embodied carbon
def building_forecast_carbon(
        allocated_gfa: pd.DataFrame,
        nb: pd.DataFrame,
        rng: np.random.Generator = None,
    ) -> pd.DataFrame:
    """
    Distribute projected annual GFA into simulated individual buildings,
    using historical NB permit GFA distributions by building type as the
    size pool. Applies the same BAU / Buy Clean carbon chain as
    forecast_embodied_carbon().

    Parameters:
    allocated_gfa : output of allocate_gfa()
    nb            : NB permit DataFrame (source of historical GFA pool)
    rng           : numpy random Generator; defaults to RANDOM_SEED

    Returns:
    DataFrame with one row per simulated building:
        year, scenario, broad_bldg_type, ownership_type,
        gfa_m2, embodied_carbon_kgco2e
    """
    if rng is None:
        rng = np.random.default_rng(RANDOM_SEED)

    # Build historical GFA pool per building type from NB permits
    nb_hist = nb[
        nb["year"].between(HISTORICAL_START, HISTORICAL_END) &
        nb["broad_bldg_type"].isin(BTYPES) &
        nb["footprint_area_sqft"].notna() &
        (nb["footprint_area_sqft"] > 0)
    ].copy()
    nb_hist["gfa_m2"] = compute_gfa_m2_batch(nb_hist)
    nb_hist = nb_hist[nb_hist["gfa_m2"].notna() & (nb_hist["gfa_m2"] > 0)]

    gfa_pools = {
        btype: nb_hist[nb_hist["broad_bldg_type"] == btype]["gfa_m2"].values
        for btype in BTYPES
    }

    rows = []
    for scenario in ["BAU", "BuyClean"]:
        for _, row in allocated_gfa.iterrows():
            yr    = int(row["year"])
            btype = row["broad_bldg_type"]
            own   = row["ownership_type"]
            target_gfa = row["gfa_m2"]

            pool = gfa_pools.get(btype)
            if target_gfa <= 0 or pool is None or len(pool) == 0:
                continue

            if scenario == "BAU":
                gwp = BAU_GWP_BY_TYPE[btype]
            else:
                if own == "public" and yr >= BUY_CLEAN_START_YEAR:
                    gwp = BUY_CLEAN_GWP_BY_TYPE[btype]
                else:
                    gwp = BAU_GWP_BY_TYPE[btype]

            intensity       = RASMI_INTENSITIES[btype]["p50"]
            cement_fraction = CEMENT_FRACTION_BY_TYPE[btype]

            cumulative = 0.0
            while cumulative < target_gfa:
                gfa = float(rng.choice(pool))
                gfa = min(gfa, target_gfa - cumulative)  # cap last building
                cumulative += gfa

                carbon = (gfa * intensity / cement_fraction) * gwp
                rows.append({
                    "year":                   yr,
                    "scenario":               scenario,
                    "broad_bldg_type":        btype,
                    "ownership_type":         own,
                    "gfa_m2":                 gfa,
                    "embodied_carbon_kgco2e": carbon,
                })

    return pd.DataFrame(rows)

# Step 6 — demolition regression and outflow projection
def fit_dm_regression(dm: pd.DataFrame) -> dict:
    """
    Fit OLS regression: annual_volume_m3 ~ year, using historical DM permits.

    Returns a dict with:
        model      : scipy linregress result
        annual_vol : DataFrame(year, volume_m3_total, volume_m3_fit, residual)
        type_mix   : dict {broad_bldg_type: mean_volume_share}
    """
    dm_hist = dm[dm["year"].between(HISTORICAL_START, HISTORICAL_END)].copy()
    if "broad_bldg_type" not in dm_hist.columns and "broad_bldg_type_permits" in dm_hist.columns:
        dm_hist = dm_hist.rename(columns={"broad_bldg_type_permits": "broad_bldg_type"})
    dm_hist = dm_hist[dm_hist["broad_bldg_type"].isin(BTYPES)]

    annual = (
        dm_hist.groupby("year")["volume_m3"]
        .sum()
        .reset_index()
        .rename(columns={"volume_m3": "volume_m3_total"})
        .dropna()
    )

    x = annual["year"].values.astype(float)
    y = annual["volume_m3_total"].values

    result = stats.linregress(x, y)
    annual["volume_m3_fit"] = result.slope * x + result.intercept
    annual["residual"]      = y - annual["volume_m3_fit"].values

    # historical type mix (mean share of annual demolition volume)
    annual_by_type = (
        dm_hist.groupby(["year", "broad_bldg_type"])["volume_m3"]
        .sum()
        .reset_index()
    )
    annual_total = annual_by_type.groupby("year")["volume_m3"].transform("sum")
    annual_by_type["share"] = annual_by_type["volume_m3"] / annual_total
    type_mix_raw = (
        annual_by_type.groupby("broad_bldg_type")["share"]
        .mean()
        .reindex(BTYPES, fill_value=0)
        .to_dict()
    )
    total = sum(type_mix_raw.values())
    type_mix = {k: v / total for k, v in type_mix_raw.items()} if total > 0 else type_mix_raw

    return {
        "model":      result,
        "annual_vol": annual,
        "type_mix":   type_mix,
    }


def project_dm(
        dm_regression: dict,
        forecast_years: range = None,
        onfidence: float = 0.90,
    ) -> pd.DataFrame:
    """
    Project annual demolition volume (m³) for forecast years with prediction intervals.

    Uses the same OLS prediction interval formula as project_gfa().

    Returns DataFrame: year, broad_bldg_type,
                       volume_m3_forecast, volume_m3_lower, volume_m3_upper
    """
    if forecast_years is None:
        forecast_years = range(HISTORICAL_END + 1, FORECAST_END + 1)

    model      = dm_regression["model"]
    annual_vol = dm_regression["annual_vol"]
    type_mix   = dm_regression["type_mix"]

    x_hist = annual_vol["year"].values.astype(float)
    n = len(x_hist)
    x_mean = x_hist.mean()
    sxx = np.sum((x_hist - x_mean) ** 2)
    residual_std = np.std(annual_vol["residual"].values, ddof=2)
    t_crit = stats.t.ppf((1 + confidence) / 2, df=n - 2)

    rows = []
    for yr in forecast_years:
        y_hat = model.slope * yr + model.intercept
        pred_se = residual_std * np.sqrt(1 + 1 / n + (yr - x_mean) ** 2 / sxx)
        margin = t_crit * pred_se
        for btype in BTYPES:
            share = type_mix.get(btype, 0)
            rows.append({
                "year":               yr,
                "broad_bldg_type":    btype,
                "volume_m3_forecast": max(0, y_hat) * share,
                "volume_m3_lower":    max(0, y_hat - margin) * share,
                "volume_m3_upper":    max(0, y_hat + margin) * share,
            })

    return pd.DataFrame(rows)


# Step 7 — forward stock projection
def project_stock(
        allocated_gfa: pd.DataFrame,
        dm_projected: pd.DataFrame,
        building_stock: pd.DataFrame,
        anchor_year: int = HISTORICAL_END,
    ) -> pd.DataFrame:
    """
    Project building stock forward from the 2023 PLUTO anchor.

        Stock(t+1) = Stock(t) + Inflow(t) - Outflow(t)

    Inflow volume is derived from projected GFA:
        inflow_volume_m3 = gfa_m2 × FLOOR_TO_FLOOR_M

    Parameters:
    allocated_gfa  : output of allocate_gfa() — projected GFA by year/type/ownership
    dm_projected   : output of project_dm() — projected outflow volume by year/type
    building_stock : 2023 PLUTO snapshot (anchor)
    anchor_year    : year of the PLUTO snapshot (default 2023)

    Returns:
    DataFrame: year, broad_bldg_type, stock_m3
    """
    # anchor stock from PLUTO
    anchor = (
        building_stock.groupby("broad_bldg_type")["volume_m3"]
        .sum()
        .reindex(BTYPES, fill_value=0)
        .to_dict()
    )

    # projected inflow volume by year/type (GFA × floor-to-floor height)
    inflow = (
        allocated_gfa.groupby(["year", "broad_bldg_type"])["gfa_m2"]
        .sum()
        .reset_index()
        .assign(volume_m3=lambda df: df["gfa_m2"] * FLOOR_TO_FLOOR_M)
        .set_index(["year", "broad_bldg_type"])["volume_m3"]
    )

    # projected outflow volume by year/type
    outflow = (
        dm_projected.set_index(["year", "broad_bldg_type"])["volume_m3_forecast"]
    )

    forecast_years = sorted(allocated_gfa["year"].unique())
    records = [{"year": anchor_year, **{f"stock_{b}": anchor[b] for b in BTYPES}}]
    current_stock = dict(anchor)

    for yr in forecast_years:
        for btype in BTYPES:
            inflow_vol  = inflow.get((yr, btype), 0)
            outflow_vol = outflow.get((yr, btype), 0)
            current_stock[btype] = max(0, current_stock[btype] + inflow_vol - outflow_vol)
        records.append({"year": yr, **{f"stock_{b}": current_stock[b] for b in BTYPES}})

    stock_df = pd.DataFrame(records).sort_values("year").reset_index(drop=True)
    stock_long = stock_df.melt(id_vars="year", var_name="broad_bldg_type", value_name="stock_m3")
    stock_long["broad_bldg_type"] = stock_long["broad_bldg_type"].str.replace("stock_", "")

    return stock_long.sort_values(["year", "broad_bldg_type"]).reset_index(drop=True)


# Convenience: run all Phase 2 outputs
def run_phase2(nb: pd.DataFrame, dm: pd.DataFrame, building_stock: pd.DataFrame) -> dict:
    """Fit regressions, project GFA and demolitions, project stock, and return forecast embodied carbon."""
    print("Fitting GFA regression...")
    regression = fit_gfa_regression(nb)
    model = regression["model"]
    print(
        f"  slope={model.slope:,.0f} m²/yr  intercept={model.intercept:,.0f}  "
        f"R²={model.rvalue**2:.3f}  p={model.pvalue:.4f}"
    )

    print("Fitting demolition regression...")
    dm_regression = fit_dm_regression(dm)
    dm_model = dm_regression["model"]
    print(
        f"  slope={dm_model.slope:,.0f} m³/yr  intercept={dm_model.intercept:,.0f}  "
        f"R²={dm_model.rvalue**2:.3f}  p={dm_model.pvalue:.4f}"
    )

    print("Projecting GFA...")
    projected = project_gfa(regression)

    print("Projecting demolition volume...")
    dm_projected = project_dm(dm_regression)

    print("Allocating GFA by type/ownership...")
    allocated = allocate_gfa(projected, regression)

    print("Projecting stock forward...")
    stock_forecast = project_stock(allocated, dm_projected, building_stock)

    print("Computing forecast embodied carbon (by type)...")
    carbon_forecast = forecast_embodied_carbon(allocated)

    print("Computing forecast embodied carbon (by building)...")
    building_carbon = building_forecast_carbon(allocated, nb)

    return {
        "regression":       regression,
        "dm_regression":    dm_regression,
        "projected_gfa":    projected,
        "dm_projected":     dm_projected,
        "allocated_gfa":    allocated,
        "stock_forecast":   stock_forecast,
        "carbon_forecast":  carbon_forecast,
        "building_carbon":  building_carbon,
    }


if __name__ == "__main__":
    from stock import load_nb_permits, load_dm_permits, load_building_stock
    nb            = load_nb_permits()
    dm            = load_dm_permits()
    building_stock = load_building_stock()
    results = run_phase2(nb, dm, building_stock)

    print("\n=== Projected GFA (2024–2033) ===")
    print(results["projected_gfa"].to_string(index=False))

    print("\n=== Projected stock (2023–2033) ===")
    stock_pivot = (
        results["stock_forecast"]
        .pivot(index="year", columns="broad_bldg_type", values="stock_m3")
        .reset_index()
    )
    print(stock_pivot.to_string(index=False))

    print("\n=== Forecast embodied carbon — totals by year/scenario ===")
    summary = (
        results["carbon_forecast"]
        .groupby(["year", "scenario"])["embodied_carbon_kgco2e"]
        .sum()
        .reset_index()
    )
    print(summary.to_string(index=False))

    print("\n=== Per-building forecast — simulated building count by year/scenario ===")
    bldg_summary = (
        results["building_carbon"]
        .groupby(["year", "scenario"])
        .agg(n_buildings=("gfa_m2", "count"), total_carbon=("embodied_carbon_kgco2e", "sum"))
        .reset_index()
    )
    print(bldg_summary.to_string(index=False))
