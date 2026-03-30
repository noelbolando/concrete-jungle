"""
monte_carlo.py

Phase 3 — Monte Carlo simulation.

For each forecast year (2023–2033), runs N_SIMULATIONS iterations that:
    1. Sample annual GFA from the regression prediction interval
       (draw from normal distribution centred on forecast with interval std)
    2. Allocate sampled GFA to building type × ownership using historical mix
    3. Draw cement intensity from the empirical RASMI log-normal distribution
       for each building type
    4. Apply BAU or Buy Clean GWP depending on ownership + year
    5. Sum city-wide embodied carbon for that run

Outputs p5 / p50 / p95 bands for both BAU and Buy Clean scenarios.

Key outputs:
run_monte_carlo(regression, forecast_years, n) -> dict with:
    results_bau      : DataFrame(year, run, embodied_carbon_kgco2e)
    results_buy_clean: DataFrame(year, run, embodied_carbon_kgco2e)
    summary          : DataFrame(year, scenario, p5, p50, p95)
    carbon_avoided   : DataFrame(year, avoided_p5, avoided_p50, avoided_p95,
                                 cumulative_avoided_p50)
"""

# import libraries
import numpy as np
import pandas as pd
from scipy import stats

# import constants
from constants import (
    N_SIMULATIONS,
    RANDOM_SEED,
    HISTORICAL_END,
    FORECAST_END,
    BUY_CLEAN_START_YEAR,
    RASMI_INTENSITIES,
)
from emissions import CEMENT_FRACTION_BY_TYPE, BAU_GWP_BY_TYPE, BUY_CLEAN_GWP_BY_TYPE
from forecast import fit_gfa_regression, project_gfa, allocate_gfa

BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]


# Log-normal parameter estimation from RASMI quantiles
def _fit_lognormal(btype: str) -> tuple[float, float]:
    """
    Fit log-normal (mu, sigma) to the five RASMI percentiles for a building type
    via least-squares regression on the log scale.
    """
    intensities = RASMI_INTENSITIES[btype]
    quantile_probs  = np.array([0.05, 0.25, 0.50, 0.75, 0.95])
    quantile_values = np.array([
        intensities["p5"], intensities["p25"], intensities["p50"],
        intensities["p75"], intensities["p95"],
    ])
    z_scores = stats.norm.ppf(quantile_probs)
    log_values = np.log(quantile_values)
    sigma_log, mu_log = np.polyfit(z_scores, log_values, 1)
    
    return mu_log, sigma_log

# Pre-compute log-normal parameters for each building type
LOGNORMAL_PARAMS = {btype: _fit_lognormal(btype) for btype in BTYPES}

# Core simulation
def run_monte_carlo(
        regression: dict,
        forecast_years: range = None,
        n: int = N_SIMULATIONS,
        seed: int = RANDOM_SEED,
        confidence: float = 0.90,
    ) -> dict:
    """
    Run Monte Carlo simulation for BAU and Buy Clean scenarios.

    Parameters:
    regression     : output of forecast.fit_gfa_regression()
    forecast_years : years to simulate (default HISTORICAL_END+1 to FORECAST_END)
    n              : number of simulation runs (default N_SIMULATIONS = 1000)
    seed           : random seed for reproducibility
    confidence     : prediction interval level used to derive GFA sampling std

    Returns:
    dict with keys: results_bau, results_buy_clean, summary, carbon_avoided
    """
    if forecast_years is None:
        forecast_years = range(HISTORICAL_END + 1, FORECAST_END + 1)

    rng = np.random.default_rng(seed)

    model       = regression["model"]
    annual_gfa  = regression["annual_gfa"]
    type_mix    = regression["type_mix"].set_index("broad_bldg_type")["mean_share"]
    ownership_mix = regression["ownership_mix"]

    # Compute prediction interval std for GFA sampling
    x_hist = annual_gfa["year"].values.astype(float)
    n_hist = len(x_hist)
    x_mean = x_hist.mean()
    sxx    = np.sum((x_hist - x_mean) ** 2)
    residual_std = np.std(annual_gfa["residual"].values, ddof=2)
    t_crit = stats.t.ppf((1 + confidence) / 2, df=n_hist - 2)

    rows_bau = []
    rows_bc  = []

    for yr in forecast_years:
        # --- GFA sampling ---
        gfa_hat  = model.slope * yr + model.intercept
        pred_se  = residual_std * np.sqrt(1 + 1 / n_hist + (yr - x_mean) ** 2 / sxx)
        # draw n GFA values from normal centred on forecast; clip at 0
        gfa_draws = np.clip(
            rng.normal(loc=gfa_hat, scale=pred_se, size=n),
            a_min=0, a_max=None
        )

        # --- per-run embodied carbon ---
        carbon_bau = np.zeros(n)
        carbon_bc  = np.zeros(n)

        for btype in BTYPES:
            type_share = type_mix.get(btype, 0)
            mu_log, sigma_log = LOGNORMAL_PARAMS[btype]
            cement_fraction   = CEMENT_FRACTION_BY_TYPE[btype]

            # intensity draws (one per simulation run)
            intensity_draws = rng.lognormal(mean=mu_log, sigma=sigma_log, size=n)

            for own in ["public", "private"]:
                own_share = ownership_mix.get(btype, {}).get(own, 0)
                gfa_segment = gfa_draws * type_share * own_share   # (n,) array

                cement_mass    = gfa_segment * intensity_draws
                concrete_vol   = cement_mass / cement_fraction

                # BAU always uses BAU GWP
                gwp_bau = BAU_GWP_BY_TYPE[btype]
                carbon_bau += concrete_vol * gwp_bau

                # Buy Clean: public from 2025 uses lower GWP; private always BAU
                if own == "public" and yr >= BUY_CLEAN_START_YEAR:
                    gwp_bc = BUY_CLEAN_GWP_BY_TYPE[btype]
                else:
                    gwp_bc = BAU_GWP_BY_TYPE[btype]
                carbon_bc += concrete_vol * gwp_bc

        for run_i in range(n):
            rows_bau.append({"year": yr, "run": run_i, "embodied_carbon_kgco2e": carbon_bau[run_i]})
            rows_bc.append( {"year": yr, "run": run_i, "embodied_carbon_kgco2e": carbon_bc[run_i]})

    results_bau = pd.DataFrame(rows_bau)
    results_bc  = pd.DataFrame(rows_bc)

    # --- summary: p5 / p50 / p95 by year ---
    def _summarise(df, scenario):
        return (
            df.groupby("year")["embodied_carbon_kgco2e"]
            .quantile([0.05, 0.50, 0.95])
            .unstack()
            .rename(columns={0.05: "p5", 0.50: "p50", 0.95: "p95"})
            .reset_index()
            .assign(scenario=scenario)
        )

    summary = pd.concat([
        _summarise(results_bau, "BAU"),
        _summarise(results_bc,  "BuyClean"),
    ], ignore_index=True)

    # --- carbon avoided: BAU - Buy Clean per run, then summarise ---
    avoided = results_bau[["year", "run", "embodied_carbon_kgco2e"]].merge(
        results_bc[["year", "run", "embodied_carbon_kgco2e"]],
        on=["year", "run"],
        suffixes=("_bau", "_bc")
    )
    avoided["avoided"] = avoided["embodied_carbon_kgco2e_bau"] - avoided["embodied_carbon_kgco2e_bc"]

    avoided_summary = (
        avoided.groupby("year")["avoided"]
        .quantile([0.05, 0.50, 0.95])
        .unstack()
        .rename(columns={0.05: "avoided_p5", 0.50: "avoided_p50", 0.95: "avoided_p95"})
        .reset_index()
    )
    # cumulative avoided (median)
    avoided_summary = avoided_summary.sort_values("year").reset_index(drop=True)
    avoided_summary["cumulative_avoided_p50"] = avoided_summary["avoided_p50"].cumsum()

    return {
        "results_bau":       results_bau,
        "results_buy_clean": results_bc,
        "summary":           summary,
        "carbon_avoided":    avoided_summary,
    }


if __name__ == "__main__":
    from stock import load_nb_permits
    from forecast import fit_gfa_regression

    print("Loading NB permits...")
    nb = load_nb_permits()

    print("Fitting regression...")
    regression = fit_gfa_regression(nb)

    print(f"Running Monte Carlo (N={N_SIMULATIONS})...")
    mc = run_monte_carlo(regression)

    print("\n=== Summary (p5 / p50 / p95 by year and scenario) ===")
    print(mc["summary"].to_string(index=False))

    print("\n=== Carbon avoided (BAU - Buy Clean) ===")
    print(mc["carbon_avoided"].to_string(index=False))
