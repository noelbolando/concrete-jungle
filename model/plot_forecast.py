"""
plot_forecast.py

Combined figure:
  Left  — NYC building stock map coloured by policy scenario
           (blue = public / Buy Clean target, grey = private / BAU)
           dot size ∝ sqrt(GFA); public buildings rendered on top.
  Right — Two stacked panels:
           (top)    Annual embodied carbon: historical 2001–2023 →
                    BAU vs. Buy Clean forecast 2024–2033
           (bottom) Annual carbon avoided under Buy Clean, 2025–2033

Run from: model/
Output:   model/outputs/plot_forecast.png
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import contextily as ctx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (
    BUILDING_STOCK_FILE, CUFT_TO_CUM, HISTORICAL_END, HISTORICAL_START,
    NB_PERMITS_FILE, DM_PERMITS_FILE, SQFT_TO_SQM, BUY_CLEAN_START_YEAR,
)
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch
from forecast import (
    fit_gfa_regression, project_gfa, allocate_gfa,
    forecast_embodied_carbon,
)
from stock import load_nb_permits, load_dm_permits, annual_embodied_carbon

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "plot_forecast.png",
)

# colours
PRIVATE_COLOR = (0.60, 0.63, 0.65, 0.35)   # muted slate, semi-transparent
PUBLIC_COLOR  = (0.08, 0.39, 0.75, 0.75)   # vivid blue, more opaque
BAU_COLOR     = "#e53935"
BC_COLOR      = "#1565c0"
AVOIDED_COLOR = "#43a047"

BTYPE_COLORS = {
    "residential_single_family": "#4caf50",
    "residential_multifamily":   "#ff9800",
    "nonresidential":            "#e53935",
}
BTYPE_LABELS = {
    "residential_single_family": "Single-Family Res.",
    "residential_multifamily":   "Multi-Family Res.",
    "nonresidential":            "Non-Residential",
}
BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]


# ── data loading ──────────────────────────────────────────────────────────────

def load_stock_map() -> gpd.GeoDataFrame:
    """Load PLUTO stock with geometry, compute GFA and carbon."""
    print("Loading building stock for map…")
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    df  = gdf.drop(columns="geometry").copy()
    df["volume_m3"] = df["volume"] * CUFT_TO_CUM
    df["year_col"] = (
        pd.to_numeric(df["yearbuilt"], errors="coerce")
        .fillna(HISTORICAL_END).clip(lower=1900, upper=HISTORICAL_END).astype(int)
    )
    df["gfa_m2"] = compute_gfa_m2_batch(df)
    valid = df["gfa_m2"].notna() & (df["gfa_m2"] > 0) & df["ownership_type"].isin(["public", "private"])
    gdf = gdf[valid].copy()
    gdf["gfa_m2"]        = df.loc[valid, "gfa_m2"].values
    gdf["ownership_type"] = df.loc[valid, "ownership_type"].values
    print(f"  {len(gdf):,} buildings with valid geometry & ownership")
    return gdf


def load_forecast_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
        hist_carbon : annual embodied carbon 2001-2023 (long, by type)
        fc_carbon   : forecast embodied carbon 2024-2033, BAU + BuyClean (long, by type)
    """
    print("Loading NB permits for forecast…")
    nb = load_nb_permits()
    dm = load_dm_permits()

    print("Computing historical carbon (2001-2023)…")
    hist_carbon = annual_embodied_carbon(nb)

    print("Fitting GFA regression…")
    regression = fit_gfa_regression(nb)
    model = regression["model"]
    print(f"  R²={model.rvalue**2:.3f}  slope={model.slope:,.0f} m²/yr")

    print("Projecting GFA 2024-2033…")
    projected  = project_gfa(regression)
    allocated  = allocate_gfa(projected, regression)

    print("Computing BAU vs. Buy Clean forecast carbon…")
    fc_carbon  = forecast_embodied_carbon(allocated)

    return hist_carbon, fc_carbon


# ── map panel ─────────────────────────────────────────────────────────────────

def draw_map(ax, gdf: gpd.GeoDataFrame):
    gdf_wm = gdf.to_crs("EPSG:3857")
    cents  = gdf_wm.geometry.centroid

    x   = cents.x.values
    y   = cents.y.values
    own = gdf["ownership_type"].values
    gfa = gdf["gfa_m2"].values

    sizes = np.clip(np.sqrt(gfa) * 0.025, 0.3, 5.0)

    is_private = own == "private"
    is_public  = own == "public"

    # private first (background), public on top
    ax.scatter(x[is_private], y[is_private],
               c=[PRIVATE_COLOR], s=sizes[is_private],
               linewidths=0, rasterized=True)
    ax.scatter(x[is_public], y[is_public],
               c=[PUBLIC_COLOR], s=sizes[is_public] * 2.5,
               linewidths=0, rasterized=True, zorder=3)

    ctx.add_basemap(ax, crs="EPSG:3857",
                    source=ctx.providers.CartoDB.PositronNoLabels, zoom=12, alpha=0.5)
    ctx.add_basemap(ax, crs="EPSG:3857",
                    source=ctx.providers.CartoDB.PositronOnlyLabels, zoom=12, alpha=0.85)
    ax.set_axis_off()

    # legend
    n_pub  = is_public.sum()
    n_priv = is_private.sum()
    legend_elements = [
        mpatches.Patch(facecolor=PUBLIC_COLOR[:3] + (0.85,), edgecolor="none",
                       label=f"Public — Buy Clean eligible  ({n_pub:,})"),
        mpatches.Patch(facecolor=PRIVATE_COLOR[:3] + (0.65,), edgecolor="none",
                       label=f"Private — BAU  ({n_priv:,})"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=8.5,
              framealpha=0.88, edgecolor="#cccccc", handlelength=1.2)

    ax.set_title(
        "NYC Building Stock — Policy Classification\n"
        "Blue = Public (Buy Clean, 2025+) · Grey = Private (BAU)",
        fontsize=10, fontweight="bold", pad=6,
    )


# ── forecast chart panel ──────────────────────────────────────────────────────

def draw_forecast(ax_fc, ax_av, hist_carbon: pd.DataFrame, fc_carbon: pd.DataFrame):
    """Top: historical + forecast line chart. Bottom: avoided carbon bars."""

    # ── aggregate to annual totals ──────────────────────────────
    hist_ann = (
        hist_carbon.groupby("year")["embodied_carbon_kgco2e"]
        .sum()
        .reset_index()
        .sort_values("year")
    )
    fc_bau = (
        fc_carbon[fc_carbon["scenario"] == "BAU"]
        .groupby("year")["embodied_carbon_kgco2e"].sum()
        .reset_index().sort_values("year")
    )
    fc_bc  = (
        fc_carbon[fc_carbon["scenario"] == "BuyClean"]
        .groupby("year")["embodied_carbon_kgco2e"].sum()
        .reset_index().sort_values("year")
    )

    # unit: MtCO₂e
    hist_y  = hist_ann["embodied_carbon_kgco2e"].values / 1e9
    bau_y   = fc_bau["embodied_carbon_kgco2e"].values / 1e9
    bc_y    = fc_bc["embodied_carbon_kgco2e"].values / 1e9
    hist_x  = hist_ann["year"].values
    fc_x    = fc_bau["year"].values

    # bridge historical → forecast (connect at 2023 value)
    bridge_x = np.array([HISTORICAL_END, fc_x[0]])
    bridge_y = np.array([hist_y[-1], bau_y[0]])

    # ── top panel: carbon trajectory ───────────────────────────
    # historical stacked area by building type
    hist_pivot = (
        hist_carbon.pivot(index="year", columns="broad_bldg_type",
                          values="embodied_carbon_kgco2e")
        .reindex(columns=BTYPES, fill_value=0) / 1e9
    )
    hist_pivot.plot.area(ax=ax_fc, stacked=True,
                         color=[BTYPE_COLORS[b] for b in BTYPES],
                         alpha=0.35, linewidth=0, legend=False)

    # grey shading for historical region
    ax_fc.axvspan(HISTORICAL_START, HISTORICAL_END,
                  color="#f5f5f5", alpha=0.0, zorder=0)

    # bridge dashed
    ax_fc.plot(bridge_x, bridge_y, color="#999999", lw=1.2, ls="--", zorder=4)

    # BAU forecast
    ax_fc.plot(fc_x, bau_y, color=BAU_COLOR, lw=2.5, label="BAU forecast", zorder=5)
    ax_fc.plot(fc_x[-1:], bau_y[-1:], "o", color=BAU_COLOR, ms=5, zorder=6)

    # Buy Clean forecast
    ax_fc.plot(fc_x, bc_y, color=BC_COLOR, lw=2.5, ls="--",
               label="Buy Clean forecast", zorder=5)
    ax_fc.plot(fc_x[-1:], bc_y[-1:], "o", color=BC_COLOR, ms=5, zorder=6)

    # shaded avoided region
    ax_fc.fill_between(fc_x, bc_y, bau_y, color=AVOIDED_COLOR,
                       alpha=0.20, label="Carbon avoided")

    # policy start line
    ax_fc.axvline(BUY_CLEAN_START_YEAR, color="#888888", lw=1.0, ls=":",
                  label=f"Buy Clean start ({BUY_CLEAN_START_YEAR})")

    # annotation: historical vs. forecast separator
    ax_fc.axvline(HISTORICAL_END + 0.5, color="#aaaaaa", lw=0.8, ls="-", alpha=0.6)
    ax_fc.text(HISTORICAL_END - 1.5, ax_fc.get_ylim()[1] if ax_fc.get_ylim()[1] > 0 else 0.4,
               "Historical", ha="right", va="top", fontsize=7.5, color="#666666")
    ax_fc.text(HISTORICAL_END + 1.5, 0.02,
               "Forecast →", ha="left", va="bottom", fontsize=7.5, color="#666666")

    ax_fc.set_xlim(HISTORICAL_START - 0.5, fc_x[-1] + 0.5)
    ax_fc.set_ylabel("Annual Embodied Carbon\n(MtCO₂e)", fontsize=8.5)
    ax_fc.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}"))
    ax_fc.legend(fontsize=7.5, framealpha=0.85, loc="upper left", ncol=2)
    ax_fc.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax_fc.set_axisbelow(True)
    ax_fc.spines[["top", "right"]].set_visible(False)
    ax_fc.set_title("Annual Embodied Carbon: Historical & Forecast",
                    fontsize=9.5, fontweight="bold", loc="left")

    # build type legend for stacked area
    type_patches = [mpatches.Patch(facecolor=BTYPE_COLORS[b], alpha=0.5,
                                   label=BTYPE_LABELS[b]) for b in BTYPES]
    ax_fc.legend(handles=type_patches + ax_fc.get_legend_handles_labels()[0][:-3],
                 fontsize=7, framealpha=0.85, loc="upper left", ncol=2,
                 title="Historical (stacked)  |  Forecast (lines)", title_fontsize=6.5)

    # ── bottom panel: BAU − BuyClean difference ────────────────
    diff       = bau_y - bc_y          # positive = BAU emits more; negative = BAU emits less
    diff_years = fc_x[fc_x >= BUY_CLEAN_START_YEAR]
    diff_vals  = diff[fc_x >= BUY_CLEAN_START_YEAR]

    bar_colors = [AVOIDED_COLOR if v >= 0 else "#e53935" for v in diff_vals]
    bars = ax_av.bar(diff_years, diff_vals,
                     color=bar_colors, alpha=0.80,
                     edgecolor="white", linewidth=0.8, width=0.65)

    # cumulative line on twin axis
    ax_av2 = ax_av.twinx()
    cumul = np.cumsum(diff_vals)
    line_color = AVOIDED_COLOR if cumul[-1] >= 0 else "#e53935"
    ax_av2.plot(diff_years, cumul, color=line_color,
                lw=2.0, ls="--", marker="o", ms=4, label="Cumulative")
    ax_av2.set_ylabel("Cumulative (MtCO₂e)", fontsize=7.5, color=line_color)
    ax_av2.tick_params(axis="y", labelcolor=line_color, labelsize=7)
    ax_av2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}"))
    ax_av2.spines[["top"]].set_visible(False)

    abs_max = max(abs(diff_vals).max(), 1e-6)
    for bar, val in zip(bars, diff_vals):
        offset = abs_max * 0.06 * (1 if val >= 0 else -1)
        va = "bottom" if val >= 0 else "top"
        if abs(val) > abs_max * 0.05:
            ax_av.text(bar.get_x() + bar.get_width() / 2, val + offset,
                       f"{val*1000:.1f} kt",
                       ha="center", va=va, fontsize=6.5,
                       color=bar.get_facecolor(), fontweight="bold")

    ax_av.axhline(0, color="#999999", lw=0.8)
    ax_av.set_xlim(HISTORICAL_START - 0.5, fc_x[-1] + 0.5)
    y_pad = abs_max * 1.45
    ax_av.set_ylim(-y_pad, y_pad)
    ax_av.set_ylabel("Annual Difference\nBAU − Buy Clean (MtCO₂e)", fontsize=8.5)
    ax_av.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.3f}"))
    ax_av.yaxis.grid(True, linestyle="--", alpha=0.35)
    ax_av.set_axisbelow(True)
    ax_av.spines[["top", "right"]].set_visible(False)
    ax_av.set_title("Annual Carbon Difference — BAU minus Buy Clean (2025–2033)\n"
                    "Green = BAU emits more · Red = Buy Clean emits more",
                    fontsize=9.5, fontweight="bold", loc="left")
    ax_av.set_xlabel("Year", fontsize=8.5)

    # grey out pre-policy years
    ax_av.axvspan(HISTORICAL_START - 1, BUY_CLEAN_START_YEAR - 0.5,
                  color="#f0f0f0", alpha=0.5, zorder=0)
    ax_av.text((HISTORICAL_START + BUY_CLEAN_START_YEAR) / 2, 0,
               "No policy\neffect", ha="center", va="center",
               fontsize=7, color="#aaaaaa")


# ── main ──────────────────────────────────────────────────────────────────────

def make_figure(gdf: gpd.GeoDataFrame,
                hist_carbon: pd.DataFrame,
                fc_carbon: pd.DataFrame) -> plt.Figure:

    fig = plt.figure(figsize=(18, 10), dpi=160)
    fig.patch.set_facecolor("white")

    gs = gridspec.GridSpec(
        2, 2,
        figure=fig,
        width_ratios=[1.15, 1],
        height_ratios=[1.1, 0.9],
        left=0.01, right=0.98,
        top=0.93, bottom=0.06,
        hspace=0.38, wspace=0.10,
    )

    ax_map = fig.add_subplot(gs[:, 0])   # map spans both rows on left
    ax_fc  = fig.add_subplot(gs[0, 1])   # top-right: forecast
    ax_av  = fig.add_subplot(gs[1, 1])   # bottom-right: avoided

    draw_map(ax_map, gdf)
    draw_forecast(ax_fc, ax_av, hist_carbon, fc_carbon)

    n_pub  = (gdf["ownership_type"] == "public").sum()
    n_priv = (gdf["ownership_type"] == "private").sum()

    fc_bau_total = fc_carbon[fc_carbon["scenario"] == "BAU"]["embodied_carbon_kgco2e"].sum() / 1e9
    fc_bc_total  = fc_carbon[fc_carbon["scenario"] == "BuyClean"]["embodied_carbon_kgco2e"].sum() / 1e9
    sign   = "higher" if fc_bc_total > fc_bau_total else "lower"
    diff_t = abs(fc_bc_total - fc_bau_total)
    fig.suptitle(
        f"NYC Embodied Carbon Forecast — BAU vs. Buy Clean (2024–2033)\n"
        f"{n_pub:,} public buildings eligible · "
        f"BAU {fc_bau_total:.1f} MtCO₂e · "
        f"Buy Clean {fc_bc_total:.1f} MtCO₂e · "
        f"Buy Clean is {diff_t*1000:.1f} ktCO₂e {sign} than BAU",
        fontsize=12, fontweight="bold", y=0.985,
    )
    return fig


def main():
    gdf                     = load_stock_map()
    hist_carbon, fc_carbon  = load_forecast_data()

    print("Building figure…")
    fig = make_figure(gdf, hist_carbon, fc_carbon)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6

    fc_bau = fc_carbon[fc_carbon["scenario"] == "BAU"]["embodied_carbon_kgco2e"].sum() / 1e9
    fc_bc  = fc_carbon[fc_carbon["scenario"] == "BuyClean"]["embodied_carbon_kgco2e"].sum() / 1e9
    print(f"\nFigure saved → {OUTPUT_FILE}  ({size_mb:.1f} MB)")
    print(f"Forecast totals 2024-2033:")
    print(f"  BAU       : {fc_bau:.3f} MtCO₂e")
    print(f"  Buy Clean : {fc_bc:.3f} MtCO₂e")
    print(f"  Avoided   : {(fc_bau - fc_bc)*1000:.2f} ktCO₂e")


if __name__ == "__main__":
    main()
