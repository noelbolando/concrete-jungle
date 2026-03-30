"""
stock.py

This script does a lot of the heavy lifting for our model.
We are organizing the stocks, inflows, and outflows per:
    1. Building type
    2. Building

Phase 1 — Historical building stock reconstruction (2001–2023).

Approach: permit-flow backcasting
    Anchor: PLUTO/OD snapshot is treated as stock at t = 2023
    For each year t from 2023 back to 2001:
        Stock(t-1) = Stock(t) - Inflow(t) + Outflow(t)
        Inflow(t)  = sum of volumes of NB permits filed in year t
        Outflow(t) = sum of volumes of DM permits filed in year t

All volumes are converted from cubic feet to cubic meters.

Key outputs:
annual_flows(nb, dm)  -> DataFrame with year, inflow_m3, outflow_m3, net_m3,
                         broken down by broad_bldg_type
backcast_stock(flows) -> DataFrame with year, running stock (m3) by building type
annual_embodied_carbon(nb) -> DataFrame with year, embodied_carbon_kgco2e by type
building_embodied_carbon(nb) -> DataFrame with one row per building: GFA, volume,
                                and embodied carbon (deterministic, median intensity)
"""

# import libraries
import geopandas as gpd
import numpy as np
import pandas as pd

# import constants
from constants import (
    CUFT_TO_CUM,
    SQFT_TO_SQM,
    HISTORICAL_START,
    HISTORICAL_END,
    NB_PERMITS_FILE,
    DM_PERMITS_FILE,
    BUILDING_STOCK_FILE,
)
# import calculations
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch

# Data loading

def load_nb_permits() -> pd.DataFrame:
    """Load and prepare NB permit data (combined permit + CO gap-fill)."""
    nb = pd.read_csv(NB_PERMITS_FILE, low_memory=False)
    nb["year"] = pd.to_datetime(nb["Pre- Filing Date"], errors="coerce").dt.year
    nb["volume_m3"] = nb["volume"] * CUFT_TO_CUM
    nb["footprint_area_m2"] = nb["footprint_area_sqft"] * SQFT_TO_SQM
    
    return nb


def load_dm_permits() -> pd.DataFrame:
    """Load and prepare demolition permit data."""
    dm = pd.read_csv(DM_PERMITS_FILE, low_memory=False)
    dm["year"] = pd.to_datetime(dm["Pre- Filing Date"], errors="coerce").dt.year
    dm["volume_m3"] = dm["volume"] * CUFT_TO_CUM
    
    return dm


def load_building_stock() -> pd.DataFrame:
    """Load PLUTO/OD building stock snapshot (2023 anchor)."""
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    gdf["volume_m3"] = gdf["volume"] * CUFT_TO_CUM
    gdf["footprint_area_m2"] = gdf["footprint_area_sqft"] * SQFT_TO_SQM
    
    return pd.DataFrame(gdf.drop(columns="geometry"))


# Annual flow aggregation
def annual_flows(
        nb: pd.DataFrame,
        dm: pd.DataFrame,
        start: int = HISTORICAL_START,
        end: int = HISTORICAL_END,
        ) -> pd.DataFrame:
    """
    Aggregate annual inflow and outflow volumes (m^3) by year and building type.
    Note: this dataframe returns inflows and outflows per buiding type, not per individual building.

    Parameters:
    nb : DataFrame  — NB permits with year, volume_m3, broad_bldg_type
    dm : DataFrame  — DM permits with year, volume_m3, broad_bldg_type

    Returns:
    DataFrame with columns:
        year, broad_bldg_type, inflow_m3, outflow_m3, net_m3
    """
    years = range(start, end + 1)
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]

    # inflow
    nb_filtered = nb[nb["year"].isin(years) & nb["broad_bldg_type"].isin(btypes)].copy()
    inflow = (
        nb_filtered.groupby(["year", "broad_bldg_type"])["volume_m3"]
        .sum()
        .reset_index()
        .rename(columns={"volume_m3": "inflow_m3"})
    )

    # outflow — prefer PLUTO volume where BIN-matched; permit volume otherwise
    dm_filtered = dm[dm["year"].isin(years)].copy()
    # broad_bldg_type in dm: prefer PLUTO column, fall back to permit column
    if "broad_bldg_type" not in dm_filtered.columns and "broad_bldg_type_permits" in dm_filtered.columns:
        dm_filtered = dm_filtered.rename(columns={"broad_bldg_type_permits": "broad_bldg_type"})
    dm_filtered = dm_filtered[dm_filtered["broad_bldg_type"].isin(btypes)]

    outflow = (
        dm_filtered.groupby(["year", "broad_bldg_type"])["volume_m3"]
        .sum()
        .reset_index()
        .rename(columns={"volume_m3": "outflow_m3"})
    )

    # full year × type grid so no gaps
    idx = pd.MultiIndex.from_product([years, btypes], names=["year", "broad_bldg_type"])
    flows = (
        pd.DataFrame(index=idx)
        .reset_index()
        .merge(inflow,  on=["year", "broad_bldg_type"], how="left")
        .merge(outflow, on=["year", "broad_bldg_type"], how="left")
        .fillna({"inflow_m3": 0, "outflow_m3": 0})
    )
    flows["net_m3"] = flows["inflow_m3"] - flows["outflow_m3"]
    
    return flows.sort_values(["year", "broad_bldg_type"]).reset_index(drop=True)


# Backcast stock reconstruction
def backcast_stock(
    flows: pd.DataFrame,
    building_stock: pd.DataFrame,
    anchor_year: int = HISTORICAL_END,
) -> pd.DataFrame:
    """
    Reconstruct annual building stock by backcasting from the 2023 PLUTO anchor.

        Stock(t-1) = Stock(t) - Inflow(t) + Outflow(t)

    Parameters:
    flows          : output of annual_flows()
    building_stock : 2023 PLUTO snapshot
    anchor_year    : year of the PLUTO snapshot (default 2023)

    Returns:
    DataFrame with columns: year, broad_bldg_type, stock_m3
    """
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]

    # anchor stock from PLUTO (sum volume by building type)
    anchor = (
        building_stock.groupby("broad_bldg_type")["volume_m3"]
        .sum()
        .reindex(btypes, fill_value=0)
        .to_dict()
    )

    years = sorted(flows["year"].unique())
    records = []

    # start at anchor year
    current_stock = dict(anchor)
    records.append({"year": anchor_year, **{f"stock_{b}": current_stock.get(b, 0) for b in btypes}})

    # backcast: walk backwards
    for year in sorted(years, reverse=True):
        year_flows = flows[flows["year"] == year].set_index("broad_bldg_type")
        for btype in btypes:
            inflow  = year_flows.loc[btype, "inflow_m3"]  if btype in year_flows.index else 0
            outflow = year_flows.loc[btype, "outflow_m3"] if btype in year_flows.index else 0
            current_stock[btype] = max(0, current_stock[btype] - inflow + outflow)
        records.append({"year": year - 1, **{f"stock_{b}": current_stock[b] for b in btypes}})

    stock_df = pd.DataFrame(records).sort_values("year").reset_index(drop=True)

    # melt to long format
    stock_long = stock_df.melt(id_vars="year", var_name="broad_bldg_type", value_name="stock_m3")
    stock_long["broad_bldg_type"] = stock_long["broad_bldg_type"].str.replace("stock_", "")
    
    return stock_long.sort_values(["year", "broad_bldg_type"]).reset_index(drop=True)


# Annual embodied carbon from new construction
def annual_embodied_carbon(
    nb: pd.DataFrame,
    start: int = HISTORICAL_START,
    end: int = HISTORICAL_END,
) -> pd.DataFrame:
    """
    Calculate annual upfront embodied carbon from new construction
    using median RASMI intensities and BAU/Buy Clean GWP by year + ownership.

    Parameters
    ----------
    nb : NB permit DataFrame with year, broad_bldg_type, ownership_type,
         footprint_area_sqft, HEIGHT_ROO, numfloors

    Returns
    -------
    DataFrame with columns: year, broad_bldg_type, embodied_carbon_kgco2e
    """
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]

    nb_filtered = nb[
        nb["year"].between(start, end) &
        nb["broad_bldg_type"].isin(btypes) &
        nb["footprint_area_sqft"].notna() &
        (nb["footprint_area_sqft"] > 0)
    ].copy()

    nb_filtered["embodied_carbon_kgco2e"] = calc_embodied_carbon_batch(
        nb_filtered, year_col="year"
    )

    carbon = (
        nb_filtered.groupby(["year", "broad_bldg_type"])["embodied_carbon_kgco2e"]
        .sum()
        .reset_index()
    )

    # full grid
    idx = pd.MultiIndex.from_product(
        [range(start, end + 1), btypes], names=["year", "broad_bldg_type"]
    )
    carbon = (
        pd.DataFrame(index=idx)
        .reset_index()
        .merge(carbon, on=["year", "broad_bldg_type"], how="left")
        .fillna({"embodied_carbon_kgco2e": 0})
    )
    
    return carbon.sort_values(["year", "broad_bldg_type"]).reset_index(drop=True)


# Per-building embodied carbon from new construction
def building_embodied_carbon(
        nb: pd.DataFrame,
        start: int = HISTORICAL_START,
        end: int = HISTORICAL_END,
    ) -> pd.DataFrame:
    """
    Calculate upfront embodied carbon (A1–A3) at the individual building level
    using median RASMI intensities and BAU/Buy Clean GWP by year + ownership.

    Parameters:
    nb : NB permit DataFrame with year, broad_bldg_type, ownership_type,
         footprint_area_sqft, HEIGHT_ROO, numfloors, BASE_BBL

    Returns:
    DataFrame with one row per building and columns:
        BASE_BBL, year, broad_bldg_type, ownership_type,
        footprint_area_m2, gfa_m2, volume_m3, embodied_carbon_kgco2e
    """
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]

    nb_filtered = nb[
        nb["year"].between(start, end) &
        nb["broad_bldg_type"].isin(btypes) &
        nb["footprint_area_sqft"].notna() &
        (nb["footprint_area_sqft"] > 0)
    ].copy()

    nb_filtered["gfa_m2"] = compute_gfa_m2_batch(nb_filtered)
    nb_filtered["embodied_carbon_kgco2e"] = calc_embodied_carbon_batch(
        nb_filtered, year_col="year"
    )

    keep = ["BASE_BBL", "year", "broad_bldg_type", "ownership_type",
            "footprint_area_m2", "gfa_m2", "volume_m3", "embodied_carbon_kgco2e"]
    # only include columns that exist (BASE_BBL may be absent in some data slices)
    keep = [c for c in keep if c in nb_filtered.columns]

    return nb_filtered[keep].reset_index(drop=True)


# Convenience: run all Phase 1 outputs
def run_phase1(output_dir: str = None):
    """
    Load data and return all Phase 1 outputs.

    Parameters
    ----------
    output_dir : str, optional
        If provided, each DataFrame is saved as a CSV in this directory.
        Files written:
            nb_permits.csv, dm_permits.csv, building_stock.csv,
            flows.csv, stock_ts.csv, carbon_ts.csv, building_carbon.csv
    """
    import os

    print("Loading data...")
    nb = load_nb_permits()
    dm = load_dm_permits()
    stock = load_building_stock()

    print("Computing annual flows...")
    flows = annual_flows(nb, dm)

    print("Backcasting stock...")
    stock_ts = backcast_stock(flows, stock)

    print("Computing annual embodied carbon...")
    carbon_ts = annual_embodied_carbon(nb)

    print("Computing per-building embodied carbon...")
    building_carbon = building_embodied_carbon(nb)

    results = {
        "nb": nb,
        "dm": dm,
        "building_stock": stock,
        "flows": flows,
        "stock_ts": stock_ts,
        "carbon_ts": carbon_ts,
        "building_carbon": building_carbon,
    }

    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        exports = {
            "nb_permits.csv":       nb,
            "dm_permits.csv":       dm,
            "building_stock.csv":   stock,
            "flows.csv":            flows,
            "stock_ts.csv":         stock_ts,
            "carbon_ts.csv":        carbon_ts,
            "building_carbon.csv":  building_carbon,
        }
        for filename, df in exports.items():
            path = os.path.join(output_dir, filename)
            df.to_csv(path, index=False)
            print(f"  Saved {path}")

    return results


if __name__ == "__main__":
    results = run_phase1(output_dir="outputs/phase1")
    print("\n=== Annual flows (first 10 rows) ===")
    print(results["flows"].head(10))
    print("\n=== Stock timeseries (first 10 rows) ===")
    print(results["stock_ts"].head(10))
    print("\n=== Embodied carbon timeseries (first 10 rows) ===")
    print(results["carbon_ts"].head(10))
