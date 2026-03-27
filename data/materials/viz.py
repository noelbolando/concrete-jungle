"""
    NYC Building Materials Data

    This script produces some nice visualizations for cement imports into NYC.
"""

# import libraries
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# load data
df = pd.read_csv(
    "", # add the cement data here
    usecols=["Location", "Year", "Cement Imports (thousand metric tons)"],
)
df["Cement Imports (thousand metric tons)"] = (
    df["Cement Imports (thousand metric tons)"]
    .astype(str)
    .str.replace(",", "")
    .astype(float)
)

nyc = df[df["Location"] == "New York City"].set_index("Year")["Cement Imports (thousand metric tons)"]
nys = df[df["Location"] == "New York State"].set_index("Year")["Cement Imports (thousand metric tons)"]
rest = nys - nyc

years = nyc.index.tolist()

# pretty colors
NYC_COLOR   = "#1B4F8A"   # deep blue
REST_COLOR  = "#8BAFCF"   # light blue
LINE_COLOR  = "#E04A27"   # orange-red accent

# =============================================================================
# Figure 1 – NYC cement imports distribution (bar + trend line)
# =============================================================================
fig1, ax1 = plt.subplots(figsize=(12, 5.5))

bars = ax1.bar(years, nyc.values, color=NYC_COLOR, width=0.7, zorder=2, label="NYC imports")

# smoothed trend line (7-year rolling mean)
rolling = nyc.rolling(window=3, center=True).mean()
ax1.plot(years, rolling.values, color=LINE_COLOR, linewidth=2.2,
         linestyle="--", zorder=3, label="3-yr rolling avg")

# annotate peak and trough
peak_yr  = nyc.idxmax()
trough_yr = nyc.idxmin()
for yr, label, va in [(peak_yr, f"Peak\n{nyc[peak_yr]:,.0f}", "bottom")]:
    ax1.annotate(
        label,
        xy=(yr, nyc[yr]),
        xytext=(yr, nyc[yr] + (120 if va == "bottom" else -200)),
        ha="center", fontsize=8.5, color="black",
        arrowprops=dict(arrowstyle="-", color="grey", lw=0.8),
    )

ax1.set_xlim(years[0] - 0.6, years[-1] + 0.6)
ax1.set_ylim(0, nyc.max() * 1.25)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xticks(years)
ax1.set_xticklabels(years, rotation=45, ha="right", fontsize=9)
ax1.set_xlabel("Year", fontsize=11)
ax1.set_ylabel("Thousand metric tons", fontsize=11)
ax1.set_title("NYC Cement Imports, 2001–2023", fontsize=14, fontweight="bold", pad=12)
ax1.legend(fontsize=10)
ax1.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
ax1.spines[["top", "right"]].set_visible(False)

fig1.tight_layout()
fig1.savefig("nyc_cement_imports_distribution.png", dpi=150, bbox_inches="tight")
print("Saved: nyc_cement_imports_distribution.png")

# =============================================================================
# Figure 2 – NYC vs. Rest of NY State (stacked bars + NYC share line)
# =============================================================================
fig2, ax2 = plt.subplots(figsize=(12, 5.5))
ax2b = ax2.twinx()

x = np.arange(len(years))
w = 0.7

ax2.bar(x, rest.values,  width=w, color=REST_COLOR, label="New York State", zorder=2)
ax2.bar(x, nyc.values,   width=w, color=NYC_COLOR,  bottom=rest.values,
        label="New York City", zorder=2)

# NYC share of total
nyc_share = nyc / nys * 100
ax2b.plot(x, nyc_share.values, color=LINE_COLOR, linewidth=2.2,
          marker="o", markersize=4, zorder=3, label="NYC share (%)")
ax2b.set_ylim(0, 100)
ax2b.set_ylabel("NYC share of NY State total (%)", fontsize=11, color=LINE_COLOR)
ax2b.tick_params(axis="y", colors=LINE_COLOR)
ax2b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))

ax2.set_xlim(-0.5, len(years) - 0.5)
ax2.set_ylim(0, nys.max() * 1.2)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax2.set_xticks(x)
ax2.set_xticklabels(years, rotation=45, ha="right", fontsize=9)
ax2.set_xlabel("Year", fontsize=11)
ax2.set_ylabel("Thousand metric tons", fontsize=11)
ax2.set_title("NYC vs. New York State – Cement Imports, 2001–2023",
              fontsize=14, fontweight="bold", pad=12)
ax2.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
ax2.spines[["top", "right"]].set_visible(False)

# combined legend
handles1, labels1 = ax2.get_legend_handles_labels()
handles2, labels2 = ax2b.get_legend_handles_labels()
ax2.legend(handles1 + handles2, labels1 + labels2, fontsize=10, loc="upper right")

fig2.tight_layout()
fig2.savefig("nyc_vs_rest_nys_cement.png", dpi=150, bbox_inches="tight")
print("Saved: nyc_vs_rest_nys_cement.png")

plt.show()
