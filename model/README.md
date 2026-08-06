# Modeling

The core of this project is a two-stage model: (1) estimating historical embodied carbon from concrete in new NYC construction, and (2) forecasting how a Buy Clean Concrete policy would change that trajectory relative to business-as-usual.

## 1. Concrete Volume Estimation

For each of the 17,764 buildings in our dataset, concrete slab volume was calculated from building dimensions:

Volume_c (m³) = Building_area (m²) × Concrete_thickness (m) × N_floors

Slab thickness was derived from NYC Building Code minimum reinforcement standards (§404.2), and floor counts were pulled from PLUTO, with missing values extrapolated using average floor height per building. This gave us a per-building concrete volume that could be aggregated by borough, building type (NR/MFR/SFR), and census tract.

## 2. Embodied Carbon Calculation

Volume was converted to embodied carbon by pairing it with Global Warming Potential (GWP) benchmarks:

E_c (kgCO₂e) = V_c (m³) × GWP_c (kgCO₂e/m³)

GWP values were sourced from two benchmarks, both indexed by concrete compression strength:

BAU scenario — NRMCA's LCA benchmark for ready-mix concrete (Eastern U.S. region)
Buy Clean scenario — NYS's official maximum GWP limits under the Buy Clean Concrete guidelines

Compression strength requirements were mapped to each building type using NYS Building Code §1904.3, allowing us to assign the correct GWP rate to every building in both scenarios.

## 3. Forecasting (2024–2033)

Historical construction activity (2012–2024) was projected forward using a linear regression model of new construction volume by building type and income tract, extending the dataset through 2033. This forecast was then run through both GWP scenarios to produce two emissions trajectories: BAU and a 50% Buy Clean intervention.

## 4. Sensitivity Analysis

To separate the two forces driving future emissions, we decomposed the forecast into:

Volume effect — the change in emissions attributable purely to growth in construction activity
GWP effect — the change in emissions attributable purely to cleaner concrete chemistry (holding construction volume at 2024 levels)

This decomposition revealed that GWP reductions dominate early in the forecast window, but construction volume growth overtakes it as the primary driver by the end of the decade — the mechanism behind our finding that Buy Clean emissions exceed the 2024 baseline by ~2030 even with the policy in place.

## 5. Policy Scenario Design

Based on the crossover point identified in the sensitivity analysis, we modeled a phased Buy Clean policy (loosely modeled on the Montreal Protocol's HFC phase-down schedule): a flat 50% GWP reduction through 2029, followed by an additional 7% reduction every five years through 2050. This tiered structure was designed to counteract the volume effect once it becomes the dominant emissions driver, rather than relying on a single static GWP cap.
