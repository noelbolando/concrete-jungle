"""
emissions.py

This script includes all emissions calculation chain for upfront embodied carbon in concrete.

Calculation chain per building:
    GFA (m^2)
    × cement_intensity (kg cement / m^2)         <- using RASMI, by building type
    ÷ cement_fraction (kg cement / m^2 concrete) <- using NRMCA LCA reults, by strength class
    × GWP_factor (kgCO2e / m^3 concrete)         <- using BAU or Buy Clean, by year/ownership
    = embodied_carbon (kgCO2e)

Backup GFA approximation (when only footprint and height are available):
    num_floors = height_m / FLOOR_TO_FLOOR_M
    GFA = footprint_area_m2 × num_floors
"""

# import libraries
import numpy as np
import pandas as pd

# import constants
from constants import (
    SQFT_TO_SQM,
    CUFT_TO_CUM,
    RASMI_INTENSITIES,
    CEMENT_FRACTION_BY_TYPE,
    BAU_GWP_BY_TYPE,
    BUY_CLEAN_GWP_BY_TYPE,
    BUY_CLEAN_START_YEAR,
    FLOOR_TO_FLOOR_M,
)

# ---
# GFA helper functions

def compute_gfa_m2(row: pd.Series) -> float:
    """
    Returns gross floor area in m^2 for a single building row.

    Priority:
    1. footprint_area_sqft × numfloors  (if both present)
    2. footprint_area_sqft × (HEIGHT_ROO_ft / FLOOR_TO_FLOOR_M / 0.3048)
       i.e. derive num_floors from roof height
    3. NaN if footprint is missing
    """
    footprint_sqft = row.get("footprint_area_sqft")
    if pd.isna(footprint_sqft) or footprint_sqft <= 0:
        
        return np.nan

    footprint_m2 = footprint_sqft * SQFT_TO_SQM

    numfloors = row.get("numfloors")
    if pd.notna(numfloors) and numfloors > 0:
        
        return footprint_m2 * numfloors

    height_ft = row.get("HEIGHT_ROO")
    if pd.notna(height_ft) and height_ft > 0:
        height_m = height_ft * 0.3048
        num_floors_est = max(1, round(height_m / FLOOR_TO_FLOOR_M))
        
        return footprint_m2 * num_floors_est

    # fallback: single-story building
    return footprint_m2


def compute_gfa_m2_batch(df: pd.DataFrame) -> pd.Series:
    """Vectorised GFA calculation for a DataFrame."""
    footprint_m2 = df["footprint_area_sqft"] * SQFT_TO_SQM

    # derive num_floors: prefer explicit, fall back to height estimate
    num_floors = df["numfloors"].copy()
    missing = num_floors.isna() | (num_floors <= 0)
    height_m = df["HEIGHT_ROO"] * 0.3048
    num_floors_from_height = (height_m / FLOOR_TO_FLOOR_M).clip(lower=1).round()
    num_floors = num_floors.where(~missing, num_floors_from_height)
    num_floors = num_floors.fillna(1)

    gfa = footprint_m2 * num_floors
    # zero out rows with bad footprint
    gfa = gfa.where(df["footprint_area_sqft"].notna() & (df["footprint_area_sqft"] > 0), np.nan)
    
    return gfa

# ---

# ---
# GWP factor selection

def select_gwp(broad_bldg_type: str, ownership_type: str, year: int) -> float:
    """
    Returns the appropriate GWP factor (kgCO2e / m^3 concrete).

    Buy Clean applies to public buildings from BUY_CLEAN_START_YEAR onwards.
    All other buildings use BAU GWP.
    """
    # TODO: right now, only considering public but we should include all in our final analysis
    if ownership_type == "public" and year >= BUY_CLEAN_START_YEAR:
        return BUY_CLEAN_GWP_BY_TYPE.get(broad_bldg_type, BAU_GWP_BY_TYPE.get(broad_bldg_type, 310))
    
    return BAU_GWP_BY_TYPE.get(broad_bldg_type, 310)


def select_gwp_batch(df: pd.DataFrame, year_col: str = "year") -> pd.Series:
    """Vectorised GWP factor selection for a DataFrame."""
    is_buy_clean = (df["ownership_type"] == "public") & (df[year_col] >= BUY_CLEAN_START_YEAR)

    gwp = pd.Series(np.nan, index=df.index)
    for btype in BAU_GWP_BY_TYPE:
        mask = df["broad_bldg_type"] == btype
        gwp = gwp.where(~mask, BAU_GWP_BY_TYPE[btype])
        buy_clean_mask = mask & is_buy_clean
        gwp = gwp.where(~buy_clean_mask, BUY_CLEAN_GWP_BY_TYPE[btype])

    return gwp

# ---

# Single-building emissions (deterministic, median intensity)
def calc_embodied_carbon(
        gfa_m2: float,
        broad_bldg_type: str,
        ownership_type: str,
        year: int,
        intensity_percentile: str = "p50",
        ) -> float:
    """
    Calculate embodied carbon (kgCO2e) for a single building using the
    median (or specified percentile) RASMI cement intensity.

    Parameters
    ----------
    gfa_m2 : float
        Gross floor area in m^2.
    broad_bldg_type : str
        One of 'residential_single_family', 'residential_multifamily', 'nonresidential'.
    ownership_type : str
        'public' or 'private'.
    year : int
        Construction year (used to select BAU vs Buy Clean GWP).
    intensity_percentile : str
        Which RASMI percentile to use (default 'p50').
    """
    intensities = RASMI_INTENSITIES.get(broad_bldg_type)
    if intensities is None or pd.isna(gfa_m2):
        
        return np.nan

    cement_intensity = intensities[intensity_percentile]         # kg cement / m^2
    cement_fraction  = CEMENT_FRACTION_BY_TYPE[broad_bldg_type]  # kg cement / m^3
    gwp              = select_gwp(broad_bldg_type, ownership_type, year)

    cement_mass_kg      = gfa_m2 * cement_intensity          # kg cement
    concrete_volume_m3  = cement_mass_kg / cement_fraction   # m^3 concrete
    embodied_carbon_kg  = concrete_volume_m3 * gwp           # kgCO2e

    return embodied_carbon_kg


# Batch emissions (deterministic, median intensity)
def calc_embodied_carbon_batch(df: pd.DataFrame, year_col: str = "year") -> pd.Series:
    """
    Vectorised embodied carbon calculation using median RASMI intensities.

    Expects columns: footprint_area_sqft, HEIGHT_ROO, numfloors (optional),
                     broad_bldg_type, ownership_type, and a year column.

    Returns a Series of kgCO2e values aligned to df.index.
    """
    gfa_m2 = compute_gfa_m2_batch(df)

    # cement intensity (p50) mapped by building type
    intensity_map = {btype: v["p50"] for btype, v in RASMI_INTENSITIES.items()}
    cement_intensity = df["broad_bldg_type"].map(intensity_map)

    # cement fraction by building type
    cement_fraction = df["broad_bldg_type"].map(CEMENT_FRACTION_BY_TYPE)

    # GWP factor
    gwp = select_gwp_batch(df, year_col=year_col)

    cement_mass_kg     = gfa_m2 * cement_intensity
    concrete_volume_m3 = cement_mass_kg / cement_fraction
    embodied_carbon    = concrete_volume_m3 * gwp

    return embodied_carbon

# Monte Carlo emissions for a single building class
def calc_embodied_carbon_mc(
        gfa_m2_values: np.ndarray,
        broad_bldg_type: str,
        ownership_type: str,
        year: int,
        n_simulations: int,
        rng: np.random.Generator,
        ) -> np.ndarray:
    """
    Run Monte Carlo embodied carbon for an array of GFA values (one cohort).

    Cement intensity is drawn from the empirical RASMI distribution using
    log-normal interpolation between the p5/p25/p50/p75/p95 percentiles.

    Returns an array of shape (n_simulations,) with total kgCO1e per run.
    """
    intensities = RASMI_INTENSITIES[broad_bldg_type]
    cement_fraction = CEMENT_FRACTION_BY_TYPE[broad_bldg_type]
    gwp = select_gwp(broad_bldg_type, ownership_type, year)

    # Fit log-normal to the five RASMI quantiles via least-squares on log scale
    quantile_probs  = np.array([0.05, 0.25, 0.50, 0.75, 0.95])
    quantile_values = np.array([
        intensities["p5"], intensities["p25"], intensities["p50"],
        intensities["p75"], intensities["p95"],
    ])
    log_values = np.log(quantile_values)
    # fit mean and std of log-normal
    from scipy.stats import norm as _norm
    z_scores = _norm.ppf(quantile_probs)
    mu_log, sigma_log = np.polyfit(z_scores, log_values, 1)[::-1]

    # draw intensity samples
    intensity_draws = rng.lognormal(mean=mu_log, sigma=sigma_log, size=n_simulations)

    total_gfa = np.nansum(gfa_m2_values)
    if total_gfa == 0:
        return np.zeros(n_simulations)

    cement_mass     = total_gfa * intensity_draws            # kg cement
    concrete_vol    = cement_mass / cement_fraction          # m^3 concrete
    embodied_carbon = concrete_vol * gwp                     # kgCO2e

    return embodied_carbon
