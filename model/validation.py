"""
validation.py

This script validates the modeled annual cement demand against USGS NYC import data.

The model produces annual embodied carbon (kgCO2e). To compare against USGS
cement imports (thousand metric tons), we back-calculate modelled cement mass:

    cement_mass_kt = sum over buildings of:
        GFA_m2 × cement_intensity_p50 (kg/m²) / 1e6  [→ thousand metric tons]

This gives a proxy for construction-related cement demand from new buildings.
It is NOT a complete accounting of all cement use (excludes infrastructure,
renovation, etc.) so we expect the modelled figure to be a fraction of USGS.

Key outputs:
load_usgs_cement()      → DataFrame(year, cement_imports_kt)
modelled_cement_demand(nb) → DataFrame(year, cement_demand_kt_modelled)
compare_cement(nb)      → merged DataFrame for plotting
"""

# import libraries
import pandas as pd
import numpy as np

# import constants
from constants import (
    SQFT_TO_SQM,
    HISTORICAL_START,
    HISTORICAL_END,
    CEMENT_IMPORTS_FILE,
)
from emissions import compute_gfa_m2_batch, RASMI_INTENSITIES


BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]

# Load USGS cement imports
def load_usgs_cement() -> pd.DataFrame:
    """
    Load USGS NYC cement import data.

    Filters to Location == 'New York City', strips comma formatting from
    import values, and returns a clean year / cement_imports_kt DataFrame.
    """
    df = pd.read_csv(CEMENT_IMPORTS_FILE)
    nyc = df[df["Location"] == "New York City"][["Year", "Cement Imports (thousand metric tons)"]].copy()
    nyc = nyc.rename(columns={
        "Year": "year",
        "Cement Imports (thousand metric tons)": "cement_imports_kt",
    })
    nyc["cement_imports_kt"] = (
        nyc["cement_imports_kt"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .astype(float)
    )
    return nyc.reset_index(drop=True)


# Modelled cement demand from new construction
def modelled_cement_demand(nb: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate annual cement mass (thousand metric tons) embedded in new
    construction permits, using median RASMI intensities.

    Parameters
    ----------
    nb : NB permit DataFrame with year, broad_bldg_type,
         footprint_area_sqft, HEIGHT_ROO, numfloors

    Returns
    -------
    DataFrame: year, cement_demand_kt_modelled
    """
    nb_filtered = nb[
        nb["year"].between(HISTORICAL_START, HISTORICAL_END) &
        nb["broad_bldg_type"].isin(BTYPES) &
        nb["footprint_area_sqft"].notna() &
        (nb["footprint_area_sqft"] > 0)
    ].copy()

    nb_filtered["gfa_m2"] = compute_gfa_m2_batch(nb_filtered)

    intensity_map = {btype: RASMI_INTENSITIES[btype]["p50"] for btype in BTYPES}
    nb_filtered["cement_intensity"] = nb_filtered["broad_bldg_type"].map(intensity_map)

    # cement mass in kg → convert to thousand metric tons (/1e6)
    nb_filtered["cement_kg"] = nb_filtered["gfa_m2"] * nb_filtered["cement_intensity"]

    annual = (
        nb_filtered.groupby("year")["cement_kg"]
        .sum()
        .reset_index()
        .rename(columns={"cement_kg": "cement_demand_kg"})
    )
    annual["cement_demand_kt_modelled"] = annual["cement_demand_kg"] / 1e6
    return annual[["year", "cement_demand_kt_modelled"]]


# Compare modelled vs USGS
def compare_cement(nb: pd.DataFrame) -> pd.DataFrame:
    """
    Merge modelled cement demand with USGS imports for side-by-side comparison.

    Also computes:
        model_fraction : modelled / USGS  (how much of total imports the model captures)
        ratio_to_mean  : normalised to mean model fraction (for trend comparison)
    """
    usgs      = load_usgs_cement()
    modelled  = modelled_cement_demand(nb)

    merged = usgs.merge(modelled, on="year", how="inner")
    merged = merged.sort_values("year").reset_index(drop=True)

    merged["model_fraction"] = merged["cement_demand_kt_modelled"] / merged["cement_imports_kt"]
    mean_fraction = merged["model_fraction"].mean()
    merged["modelled_scaled"] = merged["cement_demand_kt_modelled"] / mean_fraction

    return merged


if __name__ == "__main__":
    from stock import load_nb_permits
    nb = load_nb_permits()

    comparison = compare_cement(nb)
    print("=== Modelled cement demand vs USGS NYC imports ===")
    print(comparison[["year", "cement_imports_kt", "cement_demand_kt_modelled", "model_fraction"]].to_string(index=False))
    print(f"\nMean model fraction: {comparison['model_fraction'].mean():.1%}")
    print("(Model captures new construction only — expect ~10–30% of total imports)")
