"""
plot_forecast_comparison.py

Two static PNG maps of forecast new construction embodied carbon (2024–2033):
  - plot_forecast_bau.png      — BAU scenario
  - plot_forecast_buyclean.png — Buy Clean (all buildings) scenario

Uses a hexbin heatmap (sum of embodied carbon per cell) so the geographic
concentration of forecast carbon is visible as a continuous gradient across
the city. Colour scale and hex grid are identical across both maps so the
two outputs are directly comparable.

Run from: model/
Outputs:  model/outputs/plot_forecast_bau.png
          model/outputs/plot_forecast_buyclean.png
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colorbar import ColorbarBase
import geopandas as gpd
import contextily as ctx
from shapely.geometry import box as shapely_box

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (
    BUILDING_STOCK_FILE, CUFT_TO_CUM, SQFT_TO_SQM, RANDOM_SEED,
)
from stock import load_nb_permits, load_dm_permits
from forecast import run_phase2
from model.scripts.map_forecast_comparison import build_location_pools, assign_locations

_MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
BOROUGH_BOUNDARIES_FILE  = os.path.join(_MODEL_DIR, "data", "nybb_26a", "nybb.shp")
CENTROIDS_CACHE_FILE     = os.path.join(_MODEL_DIR, "data", "nb_centroids_cache.csv")
BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]

HEXBIN_GRIDSIZE = 60   # ~600 m cells across NYC


def _load_nyc_boundary() -> gpd.GeoDataFrame:
    return gpd.read_file(BOROUGH_BOUNDARIES_FILE).to_crs("EPSG:3857").dissolve()


def _to_web_mercator(df):
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")


def _approx_cell_sums(x, y, carbon, n_cells, extent):
    """
    Fast approximate cell sums using a square grid.
    Used only to calibrate the shared LogNorm — avoids creating
    temporary matplotlib figures.
    """
    x0, x1, y0, y1 = extent
    sums, _, _ = np.histogram2d(
        x, y,
        bins=n_cells,
        range=[[x0, x1], [y0, y1]],
        weights=carbon,
    )
    return sums[sums > 0]


def make_figure(df, title, norm, cmap, nyc, outside, extent) -> plt.Figure:
    gdf_wm = _to_web_mercator(df)
    x      = gdf_wm.geometry.x.values
    y      = gdf_wm.geometry.y.values
    carbon = df["embodied_carbon_kgco2e"].values

    minx, miny, maxx, maxy = extent
    padding = 1500

    fig, ax = plt.subplots(figsize=(14, 16), dpi=200)
    ax.set_facecolor("#f5f5f0")
    ax.set_xlim(minx - padding, maxx + padding)
    ax.set_ylim(miny - padding, maxy + padding)

    ctx.add_basemap(
        ax,
        crs="EPSG:3857",
        source=ctx.providers.CartoDB.PositronNoLabels,
        zoom=12,
        alpha=0.6,
    )

    ax.hexbin(
        x, y,
        C=carbon,
        reduce_C_function=np.sum,
        gridsize=HEXBIN_GRIDSIZE,
        extent=(minx - padding, maxx + padding, miny - padding, maxy + padding),
        cmap=cmap,
        norm=norm,
        mincnt=1,
        alpha=0.75,
        linewidths=0.1,
        zorder=3,
    )

    gpd.GeoSeries([outside], crs="EPSG:3857").plot(ax=ax, color="white", zorder=5)
    nyc.boundary.plot(ax=ax, color="#aaaaaa", linewidth=0.5, zorder=6)

    ax.set_axis_off()
    ax.set_title(title, fontsize=16, fontweight="bold", pad=8)

    # Colorbar — same placement logic as plot_all_buildings
    pos         = ax.get_position()
    cbar_height = 0.018
    cbar_gap    = 0.02
    cbar_ax = fig.add_axes([
        pos.x0 + pos.width * 0.1,
        pos.y0 - cbar_gap - cbar_height,
        pos.width * 0.8,
        cbar_height,
    ])
    cb = ColorbarBase(cbar_ax, cmap=cmap, norm=norm, orientation="horizontal")
    log_vmin    = np.log10(norm.vmin)
    log_vmax    = np.log10(norm.vmax)
    tick_powers = np.arange(np.floor(log_vmin), np.ceil(log_vmax) + 1)
    tick_vals   = [10**p for p in tick_powers if log_vmin <= p <= log_vmax]
    cb.set_ticks(tick_vals)
    cb.set_ticklabels([f"{v / 1000:,.0f} t" for v in tick_vals])
    cb.set_label("Embodied Carbon (tCO\u2082e per cell, log scale)", fontsize=10)
    cbar_ax.tick_params(labelsize=9)

    return fig



def main():
    rng = np.random.default_rng(RANDOM_SEED)

    # Load permits (fast — CSV only)
    print("Loading permits…")
    nb = load_nb_permits()
    dm = load_dm_permits()

    # Load PLUTO once — extract both building_stock and centroid cache together
    # so we never load the GeoPackage more than once per run.
    if os.path.exists(CENTROIDS_CACHE_FILE):
        print(f"Loading centroid cache… (skipping PLUTO GeoPackage)")
        coords = pd.read_csv(CENTROIDS_CACHE_FILE, dtype={"BASE_BBL": str})
        print("Loading building stock from PLUTO…")
        gdf = gpd.read_file(BUILDING_STOCK_FILE)
        gdf["volume_m3"]         = gdf["volume"] * CUFT_TO_CUM
        gdf["footprint_area_m2"] = gdf["footprint_area_sqft"] * SQFT_TO_SQM
        building_stock = pd.DataFrame(gdf.drop(columns="geometry"))
        del gdf
    else:
        print("Loading PLUTO GeoPackage… (~30–60s, builds centroid cache for future runs)")
        gdf = gpd.read_file(BUILDING_STOCK_FILE)
        gdf["volume_m3"]         = gdf["volume"] * CUFT_TO_CUM
        gdf["footprint_area_m2"] = gdf["footprint_area_sqft"] * SQFT_TO_SQM
        building_stock = pd.DataFrame(gdf.drop(columns="geometry"))

        cents  = gpd.GeoSeries(gdf.geometry.centroid, crs=gdf.crs).to_crs("EPSG:4326")
        coords = pd.DataFrame({
            "BASE_BBL": gdf["BASE_BBL"].astype(str).str.replace(r"\.0$", "", regex=True),
            "lon":      cents.x.round(5),
            "lat":      cents.y.round(5),
        }).drop_duplicates("BASE_BBL")
        coords.to_csv(CENTROIDS_CACHE_FILE, index=False)
        print(f"  Centroid cache saved → {CENTROIDS_CACHE_FILE}")
        del gdf

    # Build NB permit location pool from cached centroids
    nb["BASE_BBL_str"] = nb["BASE_BBL"].astype(str).str.replace(r"\.0$", "", regex=True)
    nb_loc = nb.merge(coords, left_on="BASE_BBL_str", right_on="BASE_BBL", how="inner")
    nb_loc = nb_loc[
        nb_loc["broad_bldg_type"].isin(BTYPES) &
        nb_loc["lon"].notna() & nb_loc["lat"].notna()
    ]
    location_pools = build_location_pools(nb_loc[["broad_bldg_type", "lon", "lat"]])
    print(f"  {len(nb_loc):,} NB permits with centroid coordinates")

    # Phase 2 directly — no need to run all of Phase 1
    print("\nRunning Phase 2 (forecast 2024–2033)…")
    p2 = run_phase2(nb, dm, building_stock)

    building_carbon = p2["building_carbon"]
    bau_df = building_carbon[building_carbon["scenario"] == "BAU"].copy().reset_index(drop=True)
    bc_df  = building_carbon[building_carbon["scenario"] == "BuyClean"].copy().reset_index(drop=True)

    print("Assigning locations…")
    bau_df = assign_locations(bau_df, location_pools, rng)
    bc_df  = assign_locations(bc_df,  location_pools, np.random.default_rng(RANDOM_SEED))

    print("Loading NYC boundary…")
    nyc      = _load_nyc_boundary()
    nyc_poly = nyc.geometry.iloc[0]
    minx, miny, maxx, maxy = nyc_poly.bounds
    big      = shapely_box(minx - 200_000, miny - 200_000, maxx + 200_000, maxy + 200_000)
    outside  = big.difference(nyc_poly)
    extent   = (minx, maxx, miny, maxy)
    padding  = 1500

    # Shared LogNorm from approximate cell sums across both datasets
    print("Computing shared colour scale…")
    bau_wm = _to_web_mercator(bau_df)
    bc_wm  = _to_web_mercator(bc_df)
    hex_extent = (minx - padding, maxx + padding, miny - padding, maxy + padding)
    bau_cells = _approx_cell_sums(
        bau_wm.geometry.x.values, bau_wm.geometry.y.values,
        bau_df["embodied_carbon_kgco2e"].values, HEXBIN_GRIDSIZE, hex_extent,
    )
    bc_cells = _approx_cell_sums(
        bc_wm.geometry.x.values, bc_wm.geometry.y.values,
        bc_df["embodied_carbon_kgco2e"].values, HEXBIN_GRIDSIZE, hex_extent,
    )
    all_cells = np.concatenate([bau_cells, bc_cells])
    norm = mcolors.LogNorm(
        vmin=float(np.percentile(all_cells, 5)),
        vmax=float(np.percentile(all_cells, 95)),
    )
    cmap = plt.get_cmap("RdYlGn_r")

    os.makedirs(os.path.join(_MODEL_DIR, "outputs"), exist_ok=True)

    outputs = [
        (bau_df, "Embodied Carbon in NYC Forecast New Construction — BAU (2024–2033)",       "plot_forecast_bau.png"),
        (bc_df,  "Embodied Carbon in NYC Forecast New Construction — Buy Clean (2024–2033)",  "plot_forecast_buyclean.png"),
    ]

    for df, title, filename in outputs:
        print(f"\nRendering {filename}…")
        fig = make_figure(df, title, norm, cmap, nyc, outside, extent)
        out_path = os.path.join(_MODEL_DIR, "outputs", filename)
        fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        size_mb = os.path.getsize(out_path) / 1e6
        print(f"  Saved → {out_path}  ({size_mb:.1f} MB)")

    bau_total = bau_df["embodied_carbon_kgco2e"].sum() / 1e6
    bc_total  =  bc_df["embodied_carbon_kgco2e"].sum() / 1e6
    print(f"\nBAU total      : {bau_total:,.0f} ktCO\u2082e")
    print(f"Buy Clean total: {bc_total:,.0f} ktCO\u2082e")
    print(f"Avoided        : {bau_total - bc_total:,.0f} ktCO\u2082e")


if __name__ == "__main__":
    main()
