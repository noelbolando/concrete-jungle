"""
carbon_by_ownership.py

Analysis: how does embodied carbon in concrete vary by ownership type (public vs. private)?

Four-panel figure:
  A) Total stock carbon by ownership (MtCO₂e)
  B) Per-building carbon distribution — violin + box (log scale)
  C) Carbon intensity distribution (kgCO₂e / m² GFA) — violin + box
  D) Building type composition of carbon stock within each ownership class

Run from: model/
Output:   model/outputs/carbon_by_ownership.png
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
)
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "carbon_by_ownership.png",
)

OWN_ORDER  = ["private", "public"]
OWN_LABELS = {"private": "Private", "public": "Public"}
OWN_COLORS = {"private": "#546e7a", "public":  "#1565c0"}  # slate-grey / deep blue

TYPE_ORDER  = ["residential_single_family", "residential_multifamily", "nonresidential"]
TYPE_LABELS = {
    "residential_single_family": "Single-Family Res.",
    "residential_multifamily":   "Multi-Family Res.",
    "nonresidential":            "Non-Residential",
}
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
        & df["ownership_type"].isin(OWN_ORDER)
        & df["broad_bldg_type"].isin(TYPE_ORDER)
        & df["gfa_m2"].notna()
        & (df["gfa_m2"] > 0)
    )
    df = df[valid].copy()
    df["carbon_intensity"] = df["embodied_carbon_kgco2e"] / df["gfa_m2"]
    print(f"  {len(df):,} buildings with valid estimate")
    return df


# ── shared violin helper ──────────────────────────────────────────────────────

def _violin(ax, groups: list, labels: list, colors: list, log_scale: bool = False):
    data = [np.log10(g) if log_scale else g for g in groups]

    parts = ax.violinplot(data, positions=range(len(data)), widths=0.6,
                          showextrema=False, showmedians=False)
    for pc, col in zip(parts["bodies"], colors):
        pc.set_facecolor(col)
        pc.set_alpha(0.40)
        pc.set_edgecolor("none")

    for i, (d, col) in enumerate(zip(data, colors)):
        q25, q50, q75 = np.percentile(d, [25, 50, 75])
        ax.plot([i, i], [q25, q75], color=col, lw=4, solid_capstyle="round", zorder=3)
        ax.scatter(i, q50, color="white", s=36, zorder=4, linewidths=1.8,
                   edgecolors=col)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=11)


# ── panels ────────────────────────────────────────────────────────────────────

def panel_total_carbon(ax, df: pd.DataFrame):
    totals = {o: df.loc[df["ownership_type"] == o, "embodied_carbon_kgco2e"].sum() / 1e9
              for o in OWN_ORDER}
    counts = {o: (df["ownership_type"] == o).sum() for o in OWN_ORDER}

    bars = ax.bar(
        range(2),
        [totals[o] for o in OWN_ORDER],
        color=[OWN_COLORS[o] for o in OWN_ORDER],
        alpha=0.82, edgecolor="white", linewidth=1.2, width=0.45,
    )
    for bar, o in zip(bars, OWN_ORDER):
        val = totals[o]
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(totals.values()) * 0.02,
                f"{val:.0f} Mt\n({counts[o]:,} bldgs)",
                ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=OWN_COLORS[o], linespacing=1.4)

    ax.set_xticks(range(2))
    ax.set_xticklabels([OWN_LABELS[o] for o in OWN_ORDER], fontsize=11)
    ax.set_ylabel("Total Embodied Carbon (MtCO₂e)", fontsize=9)
    ax.set_title("A  Total Stock Carbon by Ownership", fontsize=10, fontweight="bold", loc="left")
    ax.set_ylim(0, max(totals.values()) * 1.25)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)


def panel_per_building(ax, df: pd.DataFrame):
    groups = [df.loc[df["ownership_type"] == o, "embodied_carbon_kgco2e"].values
              for o in OWN_ORDER]
    colors = [OWN_COLORS[o] for o in OWN_ORDER]
    labels = [OWN_LABELS[o] for o in OWN_ORDER]

    _violin(ax, groups, labels, colors, log_scale=True)

    log_ticks = np.arange(1, 10)
    ax.set_yticks(log_ticks)
    ax.set_yticklabels([f"{10**v/1e3:,.0f} t" if 10**v >= 1000 else f"{10**v:.0f} kg"
                        for v in log_ticks], fontsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_ylabel("Embodied Carbon per Building (log scale)", fontsize=9)
    ax.set_title("B  Per-Building Carbon Distribution", fontsize=10, fontweight="bold", loc="left")

    for i, (g, col) in enumerate(zip(groups, colors)):
        med_t = np.median(g) / 1000
        ax.text(i, np.log10(np.median(g)) + 0.18,
                f"med {med_t:,.0f} t",
                ha="center", va="bottom", fontsize=8.5, color=col, fontweight="bold")


def panel_intensity(ax, df: pd.DataFrame):
    groups = [df.loc[df["ownership_type"] == o, "carbon_intensity"].values
              for o in OWN_ORDER]
    colors = [OWN_COLORS[o] for o in OWN_ORDER]
    labels = [OWN_LABELS[o] for o in OWN_ORDER]

    _violin(ax, groups, labels, colors, log_scale=False)

    ax.set_ylabel("Carbon Intensity (kgCO₂e / m² GFA)", fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_title("C  Carbon Intensity per Unit Floor Area", fontsize=10, fontweight="bold", loc="left")

    p99 = np.percentile(df["carbon_intensity"].values, 99.5)
    ax.set_ylim(0, p99 * 1.15)

    for i, (g, col) in enumerate(zip(groups, colors)):
        med = np.median(g)
        ax.text(i, med + p99 * 0.03,
                f"med {med:.0f}",
                ha="center", va="bottom", fontsize=8.5, color=col, fontweight="bold")


def panel_type_composition(ax, df: pd.DataFrame):
    """Stacked bar: share of total carbon by building type within each ownership class."""
    # MtCO₂e per ownership × type
    pivot = (
        df.groupby(["ownership_type", "broad_bldg_type"])["embodied_carbon_kgco2e"]
        .sum()
        .unstack(fill_value=0)
        / 1e9  # → MtCO₂e
    )
    # reindex to ensure consistent order
    pivot = pivot.reindex(index=OWN_ORDER, columns=TYPE_ORDER, fill_value=0)

    bottom = np.zeros(2)
    for t in TYPE_ORDER:
        vals = pivot[t].values
        bars = ax.bar(
            range(2), vals, bottom=bottom,
            color=TYPE_COLORS[t], alpha=0.82,
            edgecolor="white", linewidth=0.8, width=0.45,
            label=TYPE_LABELS[t],
        )
        # label each segment if large enough
        for i, (v, b) in enumerate(zip(vals, bottom)):
            if v > 0.5:  # skip tiny slivers
                ax.text(i, b + v / 2, f"{v:.0f} Mt",
                        ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        bottom += vals

    ax.set_xticks(range(2))
    ax.set_xticklabels([OWN_LABELS[o] for o in OWN_ORDER], fontsize=11)
    ax.set_ylabel("Embodied Carbon (MtCO₂e)", fontsize=9)
    ax.set_title("D  Carbon Stock Breakdown by Building Type", fontsize=10,
                 fontweight="bold", loc="left")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, framealpha=0.7, loc="upper right")


# ── main figure ───────────────────────────────────────────────────────────────

def make_figure(df: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(12, 10), dpi=160)
    fig.patch.set_facecolor("white")

    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.32,
                          left=0.09, right=0.97, top=0.91, bottom=0.07)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    for ax in [ax_a, ax_b, ax_c, ax_d]:
        ax.spines[["top", "right"]].set_visible(False)

    panel_total_carbon(ax_a, df)
    panel_per_building(ax_b, df)
    panel_intensity(ax_c, df)
    panel_type_composition(ax_d, df)

    n = len(df)
    total_mt = df["embodied_carbon_kgco2e"].sum() / 1e9
    fig.suptitle(
        f"Embodied Carbon in NYC's Building Stock — Public vs. Private Ownership\n"
        f"{n:,} buildings · {total_mt:,.0f} MtCO₂e total",
        fontsize=13, fontweight="bold", y=0.975,
    )
    return fig


def main():
    df = load_and_calc()

    print("\n── Summary by ownership type ─────────────────────────────────────")
    for o in OWN_ORDER:
        sub = df[df["ownership_type"] == o]
        print(
            f"  {OWN_LABELS[o]:<10}"
            f"  n={len(sub):>7,}"
            f"  total={sub['embodied_carbon_kgco2e'].sum()/1e9:>7.1f} MtCO₂e"
            f"  median/bldg={sub['embodied_carbon_kgco2e'].median()/1e3:>8.1f} tCO₂e"
            f"  median intensity={sub['carbon_intensity'].median():>7.1f} kgCO₂e/m²"
        )
    print()

    fig = make_figure(df)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6
    print(f"Figure saved → {OUTPUT_FILE}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
