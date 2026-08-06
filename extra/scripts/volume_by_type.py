"""
volume_by_type.py

Baseline stats and figure for building volume (m³) from the 2023 PLUTO snapshot,
broken down by broad building type.

Three-panel figure:
  A) Total stock volume by type (million m³)
  B) Per-building volume distribution — violin + box (log scale)
  C) Cumulative share of total stock volume

Run from: model/
Output:   model/outputs/volume_by_type.png
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stock import load_building_stock

TYPE_ORDER = ["residential_single_family", "residential_multifamily", "nonresidential"]
TYPE_LABELS = {
    "residential_single_family": "Single-Family\nResidential",
    "residential_multifamily":   "Multifamily\nResidential",
    "nonresidential":            "Non-Residential",
}
TYPE_COLORS = {
    "residential_single_family": "#4caf50",
    "residential_multifamily":   "#ff9800",
    "nonresidential":            "#e53935",
}

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "volume_by_type.png",
)


def volume_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Summary stats on volume_m3 grouped by broad_bldg_type."""
    rows = []
    for btype in TYPE_ORDER:
        sub = df.loc[df["broad_bldg_type"] == btype, "volume_m3"].dropna()
        rows.append({
            "building_type": TYPE_LABELS[btype],
            "count":         len(sub),
            "total_m3":      sub.sum(),
            "mean_m3":       sub.mean(),
            "median_m3":     sub.median(),
            "std_m3":        sub.std(),
            "p25_m3":        sub.quantile(0.25),
            "p75_m3":        sub.quantile(0.75),
            "p95_m3":        sub.quantile(0.95),
            "min_m3":        sub.min(),
            "max_m3":        sub.max(),
        })
    return pd.DataFrame(rows)


def _violin(ax, groups, labels, colors, log_scale=False):
    data = [np.log10(g) if log_scale else g for g in groups]
    parts = ax.violinplot(data, positions=range(len(data)), widths=0.7,
                          showextrema=False, showmedians=False)
    for pc, col in zip(parts["bodies"], colors):
        pc.set_facecolor(col)
        pc.set_alpha(0.45)
        pc.set_edgecolor("none")
    for i, (d, col) in enumerate(zip(data, colors)):
        q25, q50, q75 = np.percentile(d, [25, 50, 75])
        ax.plot([i, i], [q25, q75], color=col, lw=3, solid_capstyle="round", zorder=3)
        ax.scatter(i, q50, color="white", s=28, zorder=4, linewidths=1.5, edgecolors=col)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)


def panel_total(ax, df):
    totals = {t: df.loc[df["broad_bldg_type"] == t, "volume_m3"].sum() / 1e6
              for t in TYPE_ORDER}
    bars = ax.bar(
        range(3), [totals[t] for t in TYPE_ORDER],
        color=[TYPE_COLORS[t] for t in TYPE_ORDER],
        alpha=0.8, edgecolor="white", linewidth=1.2, width=0.55,
    )
    for bar, t in zip(bars, TYPE_ORDER):
        val = totals[t]
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(totals.values()) * 0.02,
                f"{val:.0f} M", ha="center", va="bottom", fontsize=8.5,
                fontweight="bold", color=TYPE_COLORS[t])
    ax.set_xticks(range(3))
    ax.set_xticklabels([TYPE_LABELS[t] for t in TYPE_ORDER], fontsize=9)
    ax.set_ylabel("Total Volume (million m³)", fontsize=9)
    ax.set_title("A  Total Stock Volume by Building Type", fontsize=10, fontweight="bold", loc="left")
    ax.set_ylim(0, max(totals.values()) * 1.18)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)


def panel_distribution(ax, df):
    groups = [df.loc[df["broad_bldg_type"] == t, "volume_m3"].values for t in TYPE_ORDER]
    colors = [TYPE_COLORS[t] for t in TYPE_ORDER]
    labels = [TYPE_LABELS[t] for t in TYPE_ORDER]
    _violin(ax, groups, labels, colors, log_scale=True)

    log_ticks = np.arange(1, 8)
    ax.set_yticks(log_ticks)
    ax.set_yticklabels(
        [f"{10**v/1e3:,.0f}k m³" if 10**v >= 1000 else f"{10**v:.0f} m³" for v in log_ticks],
        fontsize=8,
    )
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_ylabel("Volume per Building (log scale)", fontsize=9)
    ax.set_title("B  Per-Building Volume Distribution", fontsize=10, fontweight="bold", loc="left")

    for i, (g, col) in enumerate(zip(groups, colors)):
        med = np.median(g)
        ax.text(i, np.log10(med) + 0.12, f"med {med:,.0f} m³",
                ha="center", va="bottom", fontsize=7.5, color=col, fontweight="bold")


def panel_cumulative(ax, df):
    """CDF of per-building volume for each type (log x-axis)."""
    for t in TYPE_ORDER:
        vals = np.sort(df.loc[df["broad_bldg_type"] == t, "volume_m3"].values)
        cdf = np.arange(1, len(vals) + 1) / len(vals)
        ax.plot(vals, cdf, color=TYPE_COLORS[t], linewidth=2, label=TYPE_LABELS[t].replace("\n", " "))

    ax.set_xscale("log")
    ax.set_xlabel("Building Volume (m³, log scale)", fontsize=9)
    ax.set_ylabel("Cumulative Fraction of Buildings", fontsize=9)
    ax.set_title("C  Cumulative Volume Distribution (CDF)", fontsize=10, fontweight="bold", loc="left")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, framealpha=0.7)


def make_figure(df: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=160)
    fig.patch.set_facecolor("white")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)

    panel_total(axes[0], df)
    panel_distribution(axes[1], df)
    panel_cumulative(axes[2], df)

    total_mm3 = df["volume_m3"].sum() / 1e6
    fig.suptitle(
        f"NYC Building Stock Volume by Type — 2023 PLUTO Snapshot\n"
        f"{len(df):,} buildings · {total_mm3:,.0f} million m³ total",
        fontsize=13, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    return fig


def main():
    print("Loading building stock...")
    stock = load_building_stock()
    stock = stock[
        stock["broad_bldg_type"].isin(TYPE_ORDER) &
        stock["volume_m3"].notna() &
        (stock["volume_m3"] > 0)
    ]
    print(f"  {len(stock):,} buildings with valid volume\n")

    # print stats
    stats = volume_stats(stock)
    print("── Building Volume (m³) by Type ─────────────────────────────────────")
    for _, row in stats.iterrows():
        print(f"\n  {row['building_type'].replace(chr(10), ' ')}")
        print(f"    count:   {row['count']:>10,.0f}")
        print(f"    total:   {row['total_m3']:>10,.0f} m³  ({row['total_m3']/1e6:.2f} million m³)")
        print(f"    mean:    {row['mean_m3']:>10,.1f} m³")
        print(f"    median:  {row['median_m3']:>10,.1f} m³")
        print(f"    std:     {row['std_m3']:>10,.1f} m³")
        print(f"    p25:     {row['p25_m3']:>10,.1f} m³")
        print(f"    p75:     {row['p75_m3']:>10,.1f} m³")
        print(f"    p95:     {row['p95_m3']:>10,.1f} m³")
        print(f"    min:     {row['min_m3']:>10,.1f} m³")
        print(f"    max:     {row['max_m3']:>10,.1f} m³")
    print("\n── Total ────────────────────────────────────────────────────────────")
    total = stock["volume_m3"].sum()
    print(f"    {total:,.0f} m³  ({total/1e6:.2f} million m³)")

    # generate figure
    fig = make_figure(stock)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"\nFigure saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
