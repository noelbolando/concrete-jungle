"""
main.py

This script orchestrates all three phases and produces output charts.

Output charts
-------------
1. Historical stock     — annual concrete stock (m^3) by building type, 2001–2023
2. Historical carbon    — annual embodied carbon (kgCO2e) from new construction, 2001–2023
3. Scenario comparison  — BAU vs Buy Clean embodied carbon 2024–2033,
                          with p5/p50/p95 Monte Carlo bands
4. Carbon avoided       — annual and cumulative kgCO2e avoided under Buy Clean, 2025–2033
5. Validation           — modelled cement demand vs USGS NYC imports, 2001–2023

Run from the model/ directory:
    python main.py
"""

# import libraries
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# import functions
from stock      import run_phase1
from forecast   import run_phase2
from monte_carlo import run_monte_carlo
from validation  import compare_cement

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BTYPE_LABELS = {
    "residential_single_family": "Residential — Single Family",
    "residential_multifamily":   "Residential — Multifamily",
    "nonresidential":            "Non-Residential",
}
BTYPE_COLORS = {
    "residential_single_family": "#4e79a7",
    "residential_multifamily":   "#f28e2b",
    "nonresidential":            "#59a14f",
}
SCENARIO_COLORS = {"BAU": "#e15759", "BuyClean": "#4e79a7"}

# Create Chart 1: Historical building stock
def plot_stock(stock_ts: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 5))
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]

    for btype in btypes:
        sub = stock_ts[stock_ts["broad_bldg_type"] == btype].sort_values("year")
        ax.plot(
            sub["year"], sub["stock_m3"] / 1e6,
            label=BTYPE_LABELS[btype],
            color=BTYPE_COLORS[btype],
            linewidth=2,
        )

    ax.set_title("NYC Concrete Building Stock (2001–2023)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Building Volume (million m³)")
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "01_historical_stock.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")

# Create Chart 2: Historical embodied carbon
def plot_historical_carbon(carbon_ts: pd.DataFrame):
    btypes = ["residential_single_family", "residential_multifamily", "nonresidential"]
    pivot = carbon_ts.pivot(index="year", columns="broad_bldg_type", values="embodied_carbon_kgco2e")
    pivot = pivot[btypes] / 1e9  # → MtCO₂e (billion kgCO₂e)

    fig, ax = plt.subplots(figsize=(12, 5))
    pivot.plot.bar(
        ax=ax,
        stacked=True,
        color=[BTYPE_COLORS[b] for b in btypes],
        legend=True,
        width=0.8,
    )
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, [BTYPE_LABELS[b] for b in btypes])
    ax.set_title("Annual Embodied Carbon — New Construction (2001–2023)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Embodied Carbon (MtCO₂e)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2f}"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_historical_carbon.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")

# Create Chart 3: Scenario comparison with Monte Carlo bands
def plot_scenario_comparison(mc_summary: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 6))

    for scenario, color in SCENARIO_COLORS.items():
        sub = mc_summary[mc_summary["scenario"] == scenario].sort_values("year")
        label = "Business as Usual" if scenario == "BAU" else "Buy Clean (public, 2025+)"
        ax.plot(sub["year"], sub["p50"] / 1e9, color=color, linewidth=2.5, label=f"{label} — median")
        ax.fill_between(
            sub["year"], sub["p5"] / 1e9, sub["p95"] / 1e9,
            color=color, alpha=0.15, label=f"{label} — p5/p95",
        )

    ax.axvline(x=2025, color="grey", linestyle="--", linewidth=1, alpha=0.7, label="Buy Clean start (2025)")
    ax.set_title("BAU vs Buy Clean — Annual Embodied Carbon (2024–2033)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Embodied Carbon (MtCO₂e)")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2f}"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_scenario_comparison.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")

# Create Chart 4: How much Carbon was avoided?
def plot_carbon_avoided(carbon_avoided: pd.DataFrame):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    sub = carbon_avoided[carbon_avoided["year"] >= 2025].copy()

    # annual avoided
    ax1.bar(sub["year"], sub["avoided_p50"] / 1e9, color="#59a14f", alpha=0.85, label="Median avoided")
    ax1.fill_between(
        sub["year"], sub["avoided_p5"] / 1e9, sub["avoided_p95"] / 1e9,
        color="#59a14f", alpha=0.25, label="p5/p95 range",
    )
    ax1.set_title("Annual Carbon Avoided — Buy Clean (2025–2033)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Avoided Carbon (MtCO₂e)")
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3)

    # cumulative avoided
    ax2.plot(sub["year"], sub["cumulative_avoided_p50"] / 1e9, color="#59a14f", linewidth=2.5)
    ax2.set_title("Cumulative Carbon Avoided — Buy Clean (2025–2033)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Cumulative Avoided Carbon (MtCO₂e)")
    ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "04_carbon_avoided.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")

# Create Chart 5: Validate the modelled cement vs USGS (to check cement imports)
def plot_validation(comparison: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(comparison["year"], comparison["cement_imports_kt"],
            color="#4e79a7", linewidth=2, marker="o", markersize=4, label="USGS NYC cement imports")
    ax.plot(comparison["year"], comparison["modelled_scaled"],
            color="#f28e2b", linewidth=2, linestyle="--", marker="s", markersize=4,
            label="Modelled demand (scaled to mean fraction)")
    ax.plot(comparison["year"], comparison["cement_demand_kt_modelled"],
            color="#59a14f", linewidth=1.5, linestyle=":", marker="^", markersize=4,
            label="Modelled demand (raw)")

    mean_frac = comparison["model_fraction"].mean()
    ax.set_title(
        f"Modelled Cement Demand vs USGS NYC Imports (2001–2023)\n"
        f"Model captures ~{mean_frac:.1%} of total imports (new construction only)",
        fontsize=13, fontweight="bold",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Cement (thousand metric tons)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "05_validation.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# Output Tables
def print_avoided_table(carbon_avoided: pd.DataFrame):
    sub = carbon_avoided[carbon_avoided["year"] >= 2025].copy()
    sub = sub.assign(
        avoided_p5_MtCO2e  = sub["avoided_p5"]  / 1e9,
        avoided_p50_MtCO2e = sub["avoided_p50"] / 1e9,
        avoided_p95_MtCO2e = sub["avoided_p95"] / 1e9,
        cumulative_MtCO2e  = sub["cumulative_avoided_p50"] / 1e9,
    )
    print("\n=== Carbon Avoided Table (MtCO₂e) ===")
    print(sub[["year", "avoided_p5_MtCO2e", "avoided_p50_MtCO2e", "avoided_p95_MtCO2e",
               "cumulative_MtCO2e"]].to_string(index=False, float_format="{:.4f}".format))

# don't touch main
def main():
    print("=" * 60)
    print("NYC Concrete Metabolism Model")
    print("=" * 60)

    # Phase 1 — historical
    print("\n[Phase 1] Historical stock reconstruction (2001–2023)")
    p1 = run_phase1()

    # Phase 2 — forecast
    print("\n[Phase 2] Forecast (2024–2033)")
    p2 = run_phase2(p1["nb"])

    # Phase 3 — Monte Carlo
    from constants import N_SIMULATIONS
    print(f"\n[Phase 3] Monte Carlo simulation (N={N_SIMULATIONS})")
    mc = run_monte_carlo(p2["regression"])

    # Validation
    print("\n[Validation] Cement demand vs USGS")
    comparison = compare_cement(p1["nb"])

    # Charts
    print("\n[Charts] Generating output charts...")
    plot_stock(p1["stock_ts"])
    plot_historical_carbon(p1["carbon_ts"])
    plot_scenario_comparison(mc["summary"])
    plot_carbon_avoided(mc["carbon_avoided"])
    plot_validation(comparison)

    # Print avoided carbon table
    print_avoided_table(mc["carbon_avoided"])

    print(f"\nAll outputs saved to ./{OUTPUT_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()
