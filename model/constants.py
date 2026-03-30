"""
constants.py

This script includes all fixed parameters for the NYC concrete metabolism model:
  - Unit conversion factors
  - RASMI cement intensity distributions (kg cement / m^2 GFA), by building type
  - NRMCA cement fractions (kg cement / m^3 concrete), by strength class
  - Representative strength class per building type (psi)
  - BAU GWP factors — NRMCA Eastern LCA region proxies (kgCO2e / m^3 concrete)
  - Buy Clean GWP limits — NYS guidelines (kgCO2e / m^3 concrete)
  - Policy parameters

Sources
-------
RASMI cement intensities : Fishman et al. (2024), Sci. Data 11:418
NRMCA cement fractions   : NRMCA LCA Report V3.2 (Athena, July 2022), national benchmark
Building strength class  : NYC Building Codes 2022, Chapter 19, Table 1904.3
BAU GWP factors          : NRMCA Eastern region LCA proxies values extracted from 
                           pg 65 of NRMCA LCA V3.2
Buy Clean GWP limits     : NYS OGS Buy Clean Concrete Guidelines, Figure 2,
                           effective January 1 2025
"""

# Unit conversions (US customary -> metric)
SQFT_TO_SQM = 0.092903       # ft^2 -> m^2
CUFT_TO_CUM  = 0.0283168     # ft^3 -> m^3
LBS_TO_KG   = 0.453592       # lb  -> kg

# RASMI cement intensity distributions
# Source: Fishman et al. (2024), OECD_USA region
# Units : kg cement / m^2 GFA
# Keys  : building class type used throughout the model
RASMI_INTENSITIES = {
    "nonresidential": {
        "p5":  413.0,
        "p25": 650.6,
        "p50": 989.2,
        "p75": 1347.9,
        "p95": 2178.1,
    },
    "residential_multifamily": {
        "p5":  475.8,
        "p25": 708.4,
        "p50": 958.8,
        "p75": 1265.5,
        "p95": 2098.8,
    },
    "residential_single_family": {
        "p5":  251.8,
        "p25": 461.2,
        "p50": 618.4,
        "p75": 866.0,
        "p95": 1563.2,
    },
}

# NRMCA cement fractions
# Source: NRMCA LCA Report V3.2, national benchmark
# Units : kg Portland cement / m^3 concrete  (total cementitious also listed)
CEMENT_FRACTIONS = {
    2500: {"portland_kg_m3": 210, "total_cementitious_kg_m3": 248},
    3000: {"portland_kg_m3": 234, "total_cementitious_kg_m3": 287},
    4000: {"portland_kg_m3": 282, "total_cementitious_kg_m3": 345},
    5000: {"portland_kg_m3": 342, "total_cementitious_kg_m3": 421},
    6000: {"portland_kg_m3": 362, "total_cementitious_kg_m3": 445},
    8000: {"portland_kg_m3": 427, "total_cementitious_kg_m3": 533},
}

# Representative strength class (psi) and cement fraction (kg/m^3) per building type.
# Strength class from NYC Building Codes 2022, Chapter 19, Table 1904.3
# Units : psi
REPRESENTATIVE_STRENGTH = {
    "residential_single_family": 3000,
    "residential_multifamily":   3500,
    "nonresidential":            4500,
}

CEMENT_FRACTION_BY_TYPE = {
    btype: CEMENT_FRACTIONS[psi]["total_cementitious_kg_m3"]
    for btype, psi in REPRESENTATIVE_STRENGTH.items()
}

# BAU GWP factors — NRMCA Eastern region (kgCO2e / m^3 concrete)
# Exact Eastern region values from NRMCA LCA V3.2 pg. 65
# Units: kgCO2e/m^3
BAU_GWP = {
    2500: 239.73,
    3000: 263.52,
    4000: 314.20,
    5000: 378.03,
    6000: 399.27,
    8000: 471.52,
}

BAU_GWP_BY_TYPE = {
    btype: BAU_GWP[psi]
    for btype, psi in REPRESENTATIVE_STRENGTH.items()
}

# Buy Clean GWP limits — NYS OGS guidelines (kgCO2e / m^3 concrete)
# Source: NYS OGS Buy Clean Concrete Guidelines, Figure 2 (effective 2025-01-01)
BUY_CLEAN_GWP = {
    2500: 360,
    3000: 395,
    4000: 471,
    5000: 568,
    6000: 599,
    8000: 707,
}

BUY_CLEAN_GWP_BY_TYPE = {
    btype: BUY_CLEAN_GWP[psi]
    for btype, psi in REPRESENTATIVE_STRENGTH.items()
}

# Policy parameters
BUY_CLEAN_START_YEAR = 2023   # Buy Clean applies to public buildings from this year
BREEZY_POINT_BBL = "4163500400"  # Hurricane Sandy outlier — excluded from demolition

# Monte Carlo parameters
N_SIMULATIONS = 1000
RANDOM_SEED = 42

# Model time window
HISTORICAL_START = 2001
HISTORICAL_END   = 2023
FORECAST_END     = 2033

# Floor-to-floor height assumption (used when numfloors is missing)
FLOOR_TO_FLOOR_M = 3.5  # meters

# Data paths (relative to model/)
DATA_DIR = "data"
BUILDING_STOCK_FILE  = f"{DATA_DIR}/nyc_data.5.12.gpkg"
NB_PERMITS_FILE      = f"{DATA_DIR}/nb_permits_combined.csv"
DM_PERMITS_FILE      = f"{DATA_DIR}/dm_permits_clean.csv"
CEMENT_IMPORTS_FILE  = f"{DATA_DIR}/nyc-cement-imports.csv"
