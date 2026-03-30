"""
    CO Gap-Fill for NB Permits

    The DOB job application permit data has an approval lag — permits from 2021+
    are underrepresented because many haven't cleared full approval status yet.

    This script supplements nb_permits_clean_2025.csv with new building Certificate
    of Occupancy records (2021–2025) that aren't already covered by the permit data.
    COs represent actual project completions, so they give better coverage of recent
    construction activity.

    Strategy:
    - Keep all NB permit records as-is (2001–2020 primary coverage)
    - For CO new building records not already in NB permits (by BBL):
        - Join to PLUTO via BBL first, then BIN as fallback
        - Use C_O_ISSUE_DATE as the construction date
    - Flag source column so the model can distinguish the two
"""

import geopandas as gpd
import pandas as pd

# load inputs
nb = pd.read_csv(
    "/Users/nboland/Projects/concrete-jungle/model/data/nb_permits_clean_2025.csv",
    low_memory=False
)
co = pd.read_csv(
    "/Users/nboland/Projects/concrete-jungle/model/data/DOB_NOW__Certificate_of_Occupancy_cleaned.csv",
    low_memory=False
)
pluto = gpd.read_file("/Users/nboland/Projects/concrete-jungle/model/data/nyc_data.5.12.gpkg")

print(f"NB permits loaded: {len(nb):,}")
print(f"CO records loaded: {len(co):,}")

# filter CO to new buildings only
co_nb = co[co["JOB_TYPE"].isin([
    "NEW BUILDING",
    "New Building",
    "CO - New Building with Existing Elements to Remain"
])].copy()
print(f"CO new buildings: {len(co_nb):,}")

# parse dates and normalize BBL/BIN
co_nb["year"] = pd.to_datetime(co_nb["C_O_ISSUE_DATE"], errors="coerce").dt.year
co_nb["BBL_str"] = co_nb["BBL"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
co_nb["BIN_str"] = co_nb["BIN"].astype(str).str.replace(r"\.0$", "", regex=True)

# isolate CO records whose BBL is not already in NB permits
nb_bbls = set(nb["BBL"].astype(str))
co_new = co_nb[~co_nb["BBL_str"].isin(nb_bbls)].copy()
print(f"CO new buildings not in NB permits: {len(co_new):,}")

# aggregate PLUTO to one row per BBL and per BIN
pluto_by_bbl = pluto.groupby("BASE_BBL").agg(
    broad_bldg_type=("broad_bldg_type", "first"),
    ownership_type=("ownership_type", "first"),
    bldg_type=("bldg_type", "first"),
    volume=("volume", "sum"),
    footprint_area_sqft=("footprint_area_sqft", "sum"),
    HEIGHT_ROO=("HEIGHT_ROO", "max"),
).reset_index()

pluto_by_bin = pluto.groupby("BIN").agg(
    BASE_BBL=("BASE_BBL", "first"),
    broad_bldg_type=("broad_bldg_type", "first"),
    ownership_type=("ownership_type", "first"),
    bldg_type=("bldg_type", "first"),
    volume=("volume", "sum"),
    footprint_area_sqft=("footprint_area_sqft", "sum"),
    HEIGHT_ROO=("HEIGHT_ROO", "max"),
).reset_index()
pluto_by_bin["BIN"] = pluto_by_bin["BIN"].astype(str).str.replace(r"\.0$", "", regex=True)

# --- join pass 1: BBL ---
co_bbl = co_new.merge(pluto_by_bbl, left_on="BBL_str", right_on="BASE_BBL", how="left")
bbl_hit = co_bbl["BASE_BBL"].notna()
print(f"BBL join matched: {bbl_hit.sum():,}")

# --- join pass 2: BIN fallback for unmatched ---
co_unmatched = co_bbl[~bbl_hit].copy()
co_bin = co_unmatched.drop(
    columns=["broad_bldg_type", "ownership_type", "bldg_type", "volume",
             "footprint_area_sqft", "HEIGHT_ROO", "BASE_BBL"],
    errors="ignore"
).merge(pluto_by_bin, left_on="BIN_str", right_on="BIN", how="left", suffixes=("", "_pluto"))
bin_hit = co_bin["broad_bldg_type"].notna()
print(f"BIN fallback matched: {bin_hit.sum():,}")

# combine BBL-matched and BIN-matched rows
co_bbl_matched = co_bbl[bbl_hit].copy()
co_bin_matched = co_bin[bin_hit].copy()
# fill BBL from PLUTO BIN join where we only had a BIN match
if "BASE_BBL" not in co_bin_matched.columns:
    co_bin_matched["BASE_BBL"] = co_bin_matched.get("BASE_BBL_pluto", pd.NA)

co_supplemented = pd.concat([co_bbl_matched, co_bin_matched], ignore_index=True)
print(f"Total CO supplement records: {len(co_supplemented):,}")

# build a slim supplement dataframe aligned to the model's key columns
supplement = pd.DataFrame({
    "BBL":                co_supplemented["BBL_str"],
    "Pre- Filing Date":   pd.to_datetime(co_supplemented["C_O_ISSUE_DATE"], errors="coerce").dt.strftime("%m/%d/%Y"),
    "Borough":            co_supplemented["BOROUGH"],
    "broad_bldg_type":    co_supplemented["broad_bldg_type"],
    "ownership_type":     co_supplemented["ownership_type"],
    "bldg_type":          co_supplemented["bldg_type"],
    "volume":             co_supplemented["volume"],
    "footprint_area_sqft":co_supplemented["footprint_area_sqft"],
    "HEIGHT_ROO":         co_supplemented["HEIGHT_ROO"],
    "date_source":        "co_certificate",
})

# tag existing NB permits
nb["date_source"] = "nb_permit"

# combine — keep all NB permit columns, supplement fills only key columns
combined = pd.concat([nb, supplement], ignore_index=True, sort=False)
print(f"\nCombined dataset: {len(combined):,} records")

combined["year"] = pd.to_datetime(combined["Pre- Filing Date"], errors="coerce").dt.year
print("\nAnnual counts (combined):")
print(combined.groupby(["year", "date_source"]).size().to_string())

print("\nbroad_bldg_type distribution:")
print(combined["broad_bldg_type"].value_counts())
print("\nownership_type distribution:")
print(combined["ownership_type"].value_counts())

# export
out_path = "/Users/nboland/Projects/concrete-jungle/model/data/nb_permits_combined.csv"
combined.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")
