"""
plot_all_buildings.py

This script produces a static matplotlib figure of embodied carbon for every building in the NYC
PLUTO stock (~1M buildings). Uses contextily for a basemap tile and an NYC shapefile to define city boundaries.

Run from: model/
Output:   model/outputs/plot_all_buildings.png
"""

# import libraries
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as mcm
from matplotlib.colorbar import ColorbarBase
import geopandas as gpd
import contextily as ctx
from shapely.geometry import box as shapely_box

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import BUILDING_STOCK_FILE, CUFT_TO_CUM, HISTORICAL_END
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch

_MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(_MODEL_DIR, "outputs", "plot_all_buildings.png")
BOROUGH_BOUNDARIES_FILE = os.path.join(_MODEL_DIR, "data", "nybb_26a", "nybb.shp")
FALLBACK_YEAR = HISTORICAL_END


def load_and_calc() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    print(f"  {len(gdf):,} buildings loaded")

    df = gdf.drop(columns="geometry").copy()
    df["volume_m3"] = df["volume"] * CUFT_TO_CUM
    df["year_col"] = (
        __import__("pandas").to_numeric(df["yearbuilt"], errors="coerce")
        .fillna(FALLBACK_YEAR).clip(lower=1900, upper=FALLBACK_YEAR).astype(int)
    )

    print("Calculating embodied carbon…")
    df["gfa_m2"] = compute_gfa_m2_batch(df)
    df["embodied_carbon_kgco2e"] = calc_embodied_carbon_batch(df, year_col="year_col")

    valid = df["embodied_carbon_kgco2e"].notna() & (df["embodied_carbon_kgco2e"] > 0)
    gdf = gdf[valid].copy()
    gdf["embodied_carbon_kgco2e"] = df.loc[valid, "embodied_carbon_kgco2e"].values
    gdf["gfa_m2"] = df.loc[valid, "gfa_m2"].values
    print(f"  {len(gdf):,} buildings with valid estimate")
    return gdf


def _load_nyc_boundary() -> gpd.GeoSeries:
    """Return a single dissolved NYC polygon in Web Mercator."""
    boroughs = gpd.read_file(BOROUGH_BOUNDARIES_FILE).to_crs("EPSG:3857")
    return boroughs.dissolve()


def make_figure(gdf: gpd.GeoDataFrame) -> plt.Figure:
    nyc = _load_nyc_boundary()
    nyc_poly = nyc.geometry.iloc[0]

    gdf_wm = gdf.to_crs("EPSG:3857")
    centroids = gdf_wm.geometry.centroid

    x = centroids.x.values
    y = centroids.y.values
    carbon = gdf["embodied_carbon_kgco2e"].values

    # log-normalize for colour mapping
    log_c = np.log10(np.clip(carbon, 1, None))
    vmin, vmax = np.percentile(log_c, 2), np.percentile(log_c, 98)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap("RdYlGn_r")   # green=low, red=high

    colors = cmap(norm(log_c))
    sizes = np.clip(np.sqrt(gdf["gfa_m2"].values) * 0.03, 0.2, 4.0)
    fig, ax = plt.subplots(figsize=(14, 16), dpi=200)
    ax.set_facecolor("none")

    # Draw dots sorted by carbon so high-carbon buildings render on top
    order = np.argsort(log_c)
    ax.scatter(
        x[order], y[order],
        c=colors[order],
        s=sizes[order],
        linewidths=0,
        alpha=0.6,
        rasterized=True,
    )

    ctx.add_basemap(
        ax,
        crs="EPSG:3857",
        source=ctx.providers.CartoDB.PositronNoLabels,
        zoom=12,
        alpha=0.6,
    )

    # Clip view to NYC boundary bounds
    minx, miny, maxx, maxy = nyc_poly.bounds
    padding = 1500  # metres
    ax.set_xlim(minx - padding, maxx + padding)
    ax.set_ylim(miny - padding, maxy + padding)

    # White-out everything outside the borough boundaries
    big = shapely_box(minx - 200_000, miny - 200_000, maxx + 200_000, maxy + 200_000)
    outside = big.difference(nyc_poly)
    gpd.GeoSeries([outside], crs="EPSG:3857").plot(ax=ax, color="none", zorder=5)

    # Draw borough boundary outlines on top of the mask
    nyc.boundary.plot(ax=ax, color="#aaaaaa", linewidth=0.5, zorder=6)

    ax.set_axis_off()
    ax.set_title(
        "Embodied Carbon in New York City's Built Environment (2026)",
        fontsize=16, fontweight="bold", pad=8,
    )

    # colorbar — placed snug below the axes using its actual position
    pos = ax.get_position()
    cbar_height = 0.018
    cbar_gap = 0.02
    cbar_ax = fig.add_axes([
        pos.x0 + pos.width * 0.1,
        pos.y0 - cbar_gap - cbar_height,
        pos.width * 0.8,
        cbar_height,
    ])
    cb = ColorbarBase(
        cbar_ax,
        cmap=cmap,
        norm=norm,
        orientation="horizontal",
    )
    # ticks
    all_tick_log10_kg = np.arange(np.floor(vmin), np.ceil(vmax) + 1)
    tick_vals = [v for v in all_tick_log10_kg if vmin <= v <= vmax]
    def _fmt(log10_kg):
        t = 10 ** log10_kg / 1000
        return f"{t:,.0f} t"
    tick_labs = [_fmt(v) for v in tick_vals]
    cb.set_ticks(tick_vals)
    cb.set_ticklabels(tick_labs)
    # labels
    cb.set_label("Embodied Carbon (tCO₂e per building, log scale)", fontsize=10)
    cbar_ax.tick_params(labelsize=9)

    return fig


def main():
    gdf = load_and_calc()
    fig = make_figure(gdf)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)
    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6


if __name__ == "__main__":
    main()
