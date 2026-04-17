"""
carbon_by_type.py

Analysis: how does embodied carbon in concrete vary by building type class?

Four-panel figure:
  A) Total stock carbon by type (MtCO₂e)
  B) Per-building carbon distribution — violin + box (log scale)
  C) Carbon intensity distribution (kgCO₂e / m² GFA) — violin + box
  D) RASMI cement intensity uncertainty bands (p5–p95) by type

Run from: model/
Output:   model/outputs/carbon_by_type.png
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (
    BUILDING_STOCK_FILE, CUFT_TO_CUM, HISTORICAL_END,
    RASMI_INTENSITIES, BAU_GWP_BY_TYPE, CEMENT_FRACTION_BY_TYPE,
)
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "carbon_by_type.png",
)

TYPE_LABELS = {
    "residential_single_family": "Single-Family\nResidential",
    "residential_multifamily":   "Multi-Family\nResidential",
    "nonresidential":            "Non-Residential",
}
TYPE_ORDER = ["residential_single_family", "residential_multifamily", "nonresidential"]

# Palette consistent with the map (green → amber → red)
TYPE_COLORS = {
    "residential_single_family": "#4caf50",
    "residential_multifamily":   "#ff9800",
    "nonresidential":            "#e53935",
}


# ── data loading ──────────────────────────────────────────────────────────────

def load_and_calc() -> pd.DataFrame:
    print("Loading building stock…")
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    print(f"  {len(gdf):,} buildings loaded")

    df = gdf.drop(columns="geometry").copy()
    df["volume_m3"] = df["volume"] * CUFT_TO_CUM
    df["year_col"] = (
        pd.to_numeric(df["yearbuilt"], errors="coerce")
        .fillna(HISTORICAL_END).clip(lower=1900, upper=HISTORICAL_END).astype(int)
    )

    print("Calculating embodied carbon…")
    df["gfa_m2"] = compute_gfa_m2_batch(df)
    df["embodied_carbon_kgco2e"] = calc_embodied_carbon_batch(df, year_col="year_col")

    valid = (
        df["embodied_carbon_kgco2e"].notna()
        & (df["embodied_carbon_kgco2e"] > 0)
        & df["broad_bldg_type"].isin(TYPE_ORDER)
        & df["gfa_m2"].notna()
        & (df["gfa_m2"] > 0)
    )
    df = df[valid].copy()
    df["carbon_intensity"] = df["embodied_carbon_kgco2e"] / df["gfa_m2"]  # kgCO₂e / m²
    print(f"  {len(df):,} buildings with valid estimate")
    return df


# ── panel helpers ─────────────────────────────────────────────────────────────

def _violin(ax, groups: list[np.ndarray], labels: list[str], colors: list[str],
            log_scale: bool = False):
    """Draw a styled violin + inner box on ax for each group."""
    data = [np.log10(g) if log_scale else g for g in groups]

    parts = ax.violinplot(data, positions=range(len(data)), widths=0.7,
                          showextrema=False, showmedians=False)
    for pc, col in zip(parts["bodies"], colors):
        pc.set_facecolor(col)
        pc.set_alpha(0.45)
        pc.set_edgecolor("none")

    # overlay box (IQR) and median
    for i, (d, col) in enumerate(zip(data, colors)):
        q25, q50, q75 = np.percentile(d, [25, 50, 75])
        ax.plot([i, i], [q25, q75], color=col, lw=3, solid_capstyle="round", zorder=3)
        ax.scatter(i, q50, color="white", s=28, zorder=4, linewidths=1.5,
                   edgecolors=col)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)


def panel_total_carbon(ax, df: pd.DataFrame):
    """Bar chart of total stock carbon (MtCO₂e) by type."""
    totals = {t: df.loc[df["broad_bldg_type"] == t, "embodied_carbon_kgco2e"].sum() / 1e9
              for t in TYPE_ORDER}  # kt → Mt: /1e6 then kg → t: /1e3  → /1e9 total

    bars = ax.bar(
        range(3),
        [totals[t] for t in TYPE_ORDER],
        color=[TYPE_COLORS[t] for t in TYPE_ORDER],
        alpha=0.8, edgecolor="white", linewidth=1.2,
        width=0.55,
    )
    for bar, t in zip(bars, TYPE_ORDER):
        val = totals[t]
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                f"{val:.0f} Mt", ha="center", va="bottom", fontsize=8.5,
                fontweight="bold", color=TYPE_COLORS[t])

    ax.set_xticks(range(3))
    ax.set_xticklabels([TYPE_LABELS[t] for t in TYPE_ORDER], fontsize=9)
    ax.set_ylabel("Total Embodied Carbon (MtCO₂e)", fontsize=9)
    ax.set_title("A  Total Stock Carbon by Building Type", fontsize=10, fontweight="bold", loc="left")
    ax.set_ylim(0, max(totals.values()) * 1.18)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)


def panel_per_building(ax, df: pd.DataFrame):
    """Violin of per-building embodied carbon (log scale)."""
    groups = [df.loc[df["broad_bldg_type"] == t, "embodied_carbon_kgco2e"].values
              for t in TYPE_ORDER]
    colors = [TYPE_COLORS[t] for t in TYPE_ORDER]
    labels = [TYPE_LABELS[t] for t in TYPE_ORDER]

    _violin(ax, groups, labels, colors, log_scale=True)

    # y-axis: log10 scale ticks → human-readable labels
    log_ticks = np.arange(1, 10)
    ax.set_yticks(log_ticks)
    ax.set_yticklabels([f"{10**v/1e3:,.0f} t" if 10**v >= 1000 else f"{10**v:.0f} kg"
                        for v in log_ticks], fontsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_ylabel("Embodied Carbon per Building (log scale)", fontsize=9)
    ax.set_title("B  Per-Building Carbon Distribution", fontsize=10, fontweight="bold", loc="left")

    # annotate medians
    for i, (g, col) in enumerate(zip(groups, colors)):
        med_t = np.median(g) / 1000
        ax.text(i, np.log10(np.median(g)) + 0.15, f"med {med_t:,.0f} t",
                ha="center", va="bottom", fontsize=7.5, color=col, fontweight="bold")


def panel_intensity(ax, df: pd.DataFrame):
    """Violin of carbon intensity (kgCO₂e / m² GFA)."""
    groups = [df.loc[df["broad_bldg_type"] == t, "carbon_intensity"].values
              for t in TYPE_ORDER]
    colors = [TYPE_COLORS[t] for t in TYPE_ORDER]
    labels = [TYPE_LABELS[t] for t in TYPE_ORDER]

    _violin(ax, groups, labels, colors, log_scale=False)

    ax.set_ylabel("Carbon Intensity (kgCO₂e / m² GFA)", fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_title("C  Carbon Intensity per Unit Floor Area", fontsize=10, fontweight="bold", loc="left")

    for i, (g, col) in enumerate(zip(groups, colors)):
        med = np.median(g)
        ax.text(i, med + max(np.percentile(g, 98) for g in groups) * 0.03,
                f"med {med:.0f}", ha="center", va="bottom",
                fontsize=7.5, color=col, fontweight="bold")

    # clip y-axis at 99th percentile across all types to avoid outlier stretch
    p99 = max(np.percentile(df["carbon_intensity"].values, 99.5), 1)
    ax.set_ylim(0, p99 * 1.15)


def panel_rasmi_bands(ax):
    """Horizontal range bars showing RASMI cement intensity uncertainty by type."""
    percentiles = ["p5", "p25", "p50", "p75", "p95"]
    y_pos = {t: i for i, t in enumerate(TYPE_ORDER)}

    for t in TYPE_ORDER:
        intensities = RASMI_INTENSITIES[t]
        vals = [intensities[p] for p in percentiles]
        p5, p25, p50, p75, p95 = vals
        col = TYPE_COLORS[t]
        y = y_pos[t]

        # 90% range
        ax.barh(y, p95 - p5, left=p5, height=0.35,
                color=col, alpha=0.25, edgecolor="none")
        # IQR
        ax.barh(y, p75 - p25, left=p25, height=0.35,
                color=col, alpha=0.55, edgecolor="none")
        # median tick
        ax.plot([p50, p50], [y - 0.22, y + 0.22], color=col, lw=2.5, zorder=3)
        ax.text(p50, y + 0.24, f"{p50:.0f}", ha="center", va="bottom",
                fontsize=7.5, color=col, fontweight="bold")

    ax.set_yticks(list(y_pos.values()))
    ax.set_yticklabels([TYPE_LABELS[t] for t in TYPE_ORDER], fontsize=9)
    ax.set_xlabel("Cement Intensity (kg cement / m² GFA)", fontsize=9)
    ax.set_title("D  RASMI Cement Intensity Uncertainty (p5–p95)", fontsize=10,
                 fontweight="bold", loc="left")
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_ylim(-0.55, len(TYPE_ORDER) - 0.45)

    # legend
    light = mpatches.Patch(color="grey", alpha=0.25, label="p5–p95 (90%)")
    dark  = mpatches.Patch(color="grey", alpha=0.55, label="p25–p75 (IQR)")
    ax.legend(handles=[dark, light], fontsize=8, framealpha=0.7, loc="lower right")


# ── main figure ───────────────────────────────────────────────────────────────

def make_figure(df: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(14, 11), dpi=160)
    fig.patch.set_facecolor("none")

    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.32,
                          left=0.08, right=0.97, top=0.91, bottom=0.07)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    for ax in [ax_a, ax_b, ax_c, ax_d]:
        ax.spines[["top", "right"]].set_visible(False)

    panel_total_carbon(ax_a, df)
    panel_per_building(ax_b, df)
    panel_intensity(ax_c, df)
    panel_rasmi_bands(ax_d)

    n_buildings = len(df)
    total_mt = df["embodied_carbon_kgco2e"].sum() / 1e9
    fig.suptitle(
        f"Embodied Carbon in NYC's Building Stock — by Building Type Class\n"
        f"{n_buildings:,} buildings · {total_mt:,.0f} MtCO₂e total",
        fontsize=13, fontweight="bold", y=0.975,
    )

    return fig


def main():
    df = load_and_calc()

    # summary to stdout
    print("\n── Summary by building type ──────────────────────────────────────")
    for t in TYPE_ORDER:
        sub = df[df["broad_bldg_type"] == t]
        print(
            f"  {TYPE_LABELS[t].replace(chr(10), ' '):<30}"
            f"  n={len(sub):>7,}"
            f"  total={sub['embodied_carbon_kgco2e'].sum()/1e9:>7.1f} MtCO₂e"
            f"  median/bldg={sub['embodied_carbon_kgco2e'].median()/1e3:>8.1f} tCO₂e"
            f"  median intensity={sub['carbon_intensity'].median():>7.1f} kgCO₂e/m²"
        )
    print()

    fig = make_figure(df)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", transparent=True)
    plt.close(fig)
    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6
    print(f"Figure saved → {OUTPUT_FILE}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
