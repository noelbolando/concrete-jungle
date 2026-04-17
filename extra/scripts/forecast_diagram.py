"""
forecast_diagram.py

Diagram of the Phase 2 forecast model structure.

Run from: model/
Output:   model/outputs/forecast_diagram.png
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "forecast_diagram.png")

C_INPUT   = "#4e79a7"
C_REG     = "#f28e2b"
C_ALLOC   = "#59a14f"
C_CARBON  = "#e15759"
C_BOX_BG  = "#f9f9f9"

def box(ax, x, y, w, h, text, color, fontsize=9.5, text_color="white"):
    rect = mpatches.FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02",
        linewidth=1.2, edgecolor=color,
        facecolor=color, alpha=0.88,
        zorder=3,
    )
    ax.add_patch(rect)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=text_color, fontweight="bold", zorder=4,
            multialignment="center")

def ghost_box(ax, x, y, w, h, text, color, fontsize=9):
    rect = mpatches.FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02",
        linewidth=1.5, edgecolor=color,
        facecolor="white", alpha=1.0,
        zorder=3,
    )
    ax.add_patch(rect)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color=color, fontweight="bold", zorder=4,
            multialignment="center")

def arrow(ax, x0, y0, x1, y1, color="#888888"):
    ax.annotate(
        "", xy=(x1, y1), xytext=(x0, y0),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.4),
        zorder=2,
    )

def main():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    # ── Input ──────────────────────────────────────────────────────────────
    box(ax, 6, 6.3, 2.2, 0.6,
        "Year  t  (2024 – 2033)",
        C_INPUT, fontsize=10)

    # ── Two regression branches ────────────────────────────────────────────
    # NB regression (left)
    arrow(ax, 4.9, 6.0, 3.2, 5.1)
    box(ax, 2.8, 4.75, 3.6, 0.65,
        "NB regression\n"
        r"$\mathrm{GFA}_t = \beta_0 + \beta_1 \cdot t$",
        C_REG, fontsize=9)

    # DM regression (right)
    arrow(ax, 7.1, 6.0, 8.8, 5.1)
    box(ax, 9.2, 4.75, 3.6, 0.65,
        "DM regression\n"
        r"$\mathrm{Vol}_t^{\,\mathrm{dem}} = \gamma_0 + \gamma_1 \cdot t$",
        C_REG, fontsize=9)

    # ── Type allocation ────────────────────────────────────────────────────
    arrow(ax, 2.8, 4.42, 2.8, 3.58)
    box(ax, 2.8, 3.25, 3.6, 0.6,
        "Type allocation\n"
        r"$\mathrm{GFA}_{t,k} = \mathrm{GFA}_t \cdot s_k$",
        C_ALLOC, fontsize=9)

    # ownership split
    arrow(ax, 2.8, 2.92, 2.8, 2.08)
    box(ax, 2.8, 1.75, 3.6, 0.6,
        "Ownership split\n"
        r"$\mathrm{GFA}_{t,k,o} = \mathrm{GFA}_{t,k} \cdot w_{k,o}$",
        C_ALLOC, fontsize=9)

    # ── Stock projection ───────────────────────────────────────────────────
    arrow(ax, 9.2, 4.42, 9.2, 3.58)
    box(ax, 9.2, 3.25, 3.6, 0.6,
        "Stock projection\n"
        r"$S_{t+1} = S_t + \mathrm{Inflow}_t - \mathrm{Outflow}_t$",
        C_ALLOC, fontsize=9)

    # ── Emissions chain ────────────────────────────────────────────────────
    # arrow from GFA allocation and DM stock to emissions
    arrow(ax, 2.8, 1.42, 5.5, 0.75)
    arrow(ax, 9.2, 2.92, 6.5, 0.75)

    box(ax, 6, 0.5, 5.8, 0.72,
        r"Embodied carbon:   $C_{t,k} = \mathrm{GFA}_{t,k}"
        r"\times I_k \div f_k \times \mathrm{GWP}_k$",
        C_CARBON, fontsize=9.5)

    # ── Legend for parameters ──────────────────────────────────────────────
    legend_items = [
        r"$s_k$  = historical mean GFA share by building type $k$",
        r"$w_{k,o}$  = historical ownership share (public / private) within type $k$",
        r"$I_k$  = RASMI cement intensity (kg cement / m² GFA), p50",
        r"$f_k$  = NRMCA cement fraction (kg cement / m³ concrete)",
        r"$\mathrm{GWP}_k$  = emissions factor (kgCO₂e / m³ concrete) — BAU or Buy Clean",
    ]
    ax.text(0.35, 2.5, "\n".join(legend_items),
            fontsize=8.2, va="top", color="#444444",
            linespacing=1.8, zorder=4)

    # section label
    ax.text(0.35, 2.65, "Parameters", fontsize=8.5, fontweight="bold",
            color="#444444", zorder=4)

    # ── Title ──────────────────────────────────────────────────────────────
    ax.set_title("Phase 2 — Forecast Model Structure", fontsize=13,
                 fontweight="bold", pad=6)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fig.savefig(OUTPUT_FILE, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
