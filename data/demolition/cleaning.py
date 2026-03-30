"""
    NYC Building Demolition Data

    To describe the change of building stock in NYC, we use demolition permit data to help us understand
    how much building stock decreases on an annual basis.

    NYC Building Construction Permit Data: https://data.cityofnewyork.us/Housing-Development/NYC-Demolition-Building/j7h9-tb8p/about_data

    The data gives us floor area demolished per year by building type and borough.
"""

# import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd

# load data
demo = pd.read_csv(
    "/Users/nboland/Projects/concrete-jungle/data/demolition/NYC_Demolition_Building_20260316 (1).csv",
    low_memory=False
)
pluto = gpd.read_file("/Users/nboland/Projects/concrete-jungle/model/data/nyc_data.5.12.gpkg")

# create a filter for only demolitions
dm = demo[demo["Job Type"] == "DM"].copy()
print(f"DM permits: {len(dm):,}") # DM permits: 80,346

# filter for only approved permits using NYC data codes
approved_demo = ["X", "E", "R", "Q"]
dm = dm[dm["Job Status"].isin(approved_demo)].copy()
print(f"DM permits after status filter: {len(dm):,}") # DM permits after status filter: 79,906

# clean up Block and Lot columns because there might be non-numerical data
dm["Block"] = dm["Block"].astype(str).str.replace(r'^O', '0', regex=True)
mask = dm["Block"].astype(str).str.contains(r'\.\.\.', regex=True) | \
       dm["Lot"].astype(str).str.contains(r'\.\.\.', regex=True)
dm = dm[~mask].copy()
dm = dm.dropna(subset=["Borough", "Block", "Lot"]).copy()
print(f"DM permits after cleaning: {len(dm):,}") # DM permits after cleaning: 79,906

# construct BBL from the three sep columns
borough_codes = {
    "MANHATTAN":     1, "MN": 1,
    "BRONX":         2, "BX": 2,
    "BROOKLYN":      3, "BK": 3,
    "QUEENS":        4, "QN": 4,
    "STATEN ISLAND": 5, "SI": 5
}
dm["boro_int"] = dm["Borough"].str.upper().str.strip().map(borough_codes)
dm["BBL"] = (
    dm["boro_int"].astype(int).astype(str).str.zfill(1) +
    dm["Block"].astype(float).astype(int).astype(str).str.zfill(5) +
    dm["Lot"].astype(float).astype(int).astype(str).str.zfill(4)
)
print(f"BBL length check:\n{dm['BBL'].str.len().value_counts()}") # 79906 that are 10-digits

# use previously outlined methodology to map the building classes/broad categories
bldg_class_map = {
    'A': 'single_family', 'B': 'two_family', 'C': 'walkup_apartment',
    'D': 'elevator_apartment', 'E': 'warehouse', 'F': 'factory_industrial',
    'G': 'garage', 'H': 'hotel', 'I': 'hospital_health', 'J': 'theatre',
    'K': 'retail_store', 'L': 'loft', 'M': 'religious', 'N': 'asylum_home',
    'O': 'office', 'P': 'public_assembly', 'Q': 'outdoor_recreation',
    'R': 'condominium', 'S': 'mixed_use_residential', 'T': 'transportation',
    'U': 'utility', 'V': 'vacant', 'W': 'educational', 'Y': 'government',
    'Z': 'miscellaneous',
}
broad_class_map = {
    'single_family': 'residential_single_family',
    'two_family': 'residential_multifamily',
    'walkup_apartment': 'residential_multifamily',
    'elevator_apartment': 'residential_multifamily',
    'condominium': 'residential_multifamily',
    'mixed_use_residential': 'residential_multifamily',
    'loft': 'residential_multifamily',
    'warehouse': 'nonresidential', 'factory_industrial': 'nonresidential',
    'garage': 'nonresidential', 'hotel': 'nonresidential',
    'hospital_health': 'nonresidential', 'theatre': 'nonresidential',
    'retail_store': 'nonresidential', 'religious': 'nonresidential',
    'asylum_home': 'nonresidential', 'office': 'nonresidential',
    'public_assembly': 'nonresidential', 'outdoor_recreation': 'nonresidential',
    'transportation': 'nonresidential', 'utility': 'nonresidential',
    'vacant': 'nonresidential', 'educational': 'nonresidential',
    'government': 'nonresidential', 'miscellaneous': 'nonresidential',
}
ownership_map = {
    'single_family': 'private', 'two_family': 'private',
    'walkup_apartment': 'private', 'elevator_apartment': 'private',
    'warehouse': 'private', 'factory_industrial': 'private',
    'garage': 'private', 'hotel': 'private', 'hospital_health': 'private',
    'theatre': 'private', 'retail_store': 'private', 'loft': 'private',
    'religious': 'private', 'asylum_home': 'private', 'office': 'private',
    'public_assembly': 'private', 'outdoor_recreation': 'public',
    'condominium': 'private', 'mixed_use_residential': 'private',
    'transportation': 'public', 'utility': 'public', 'vacant': 'public',
    'educational': 'public', 'government': 'public', 'miscellaneous': 'public',
}
dm["bldg_class_letter"] = dm["BUILDING_CLASS"].astype(str).str[0].str.upper()
dm["bldg_type_permits"] = dm["bldg_class_letter"].map(bldg_class_map)
dm["broad_bldg_type_permits"] = dm["bldg_type_permits"].map(broad_class_map)
dm["ownership_type_permits"] = dm["bldg_type_permits"].map(ownership_map)

print("\nBroad building type distribution:")
#residential_multifamily      42512
#nonresidential               21877
#residential_single_family    15428
print(dm["broad_bldg_type_permits"].value_counts())
#residential_multifamily      42512
#nonresidential               21877
#residential_single_family    15428
print("\nOwnership type distribution:")
print(dm["ownership_type_permits"].value_counts())
# private    68592
# public     11225

# joining with PLUTO data
# NOTE: BBL 4163500400 (Breezy Point, Queens) is a cooperative where 1,877
# individual SFH share one BBL. Inflates Queens SFH volume due to Hurricane Sandy rebuilds.
joined_demo = dm.merge(
    pluto[["BIN", "BASE_BBL", "bldgclass", "bldg_type", "broad_bldg_type",
           "volume", "footprint_area_sqft", "numfloors", "HEIGHT_ROO"]],
    left_on="Bin #",
    right_on="BIN",
    how="left"
)

# check data
total = len(joined_demo)
bin_matched = joined_demo["BIN"].notna().sum()
print(f"\nMatched: {bin_matched:,} / {total:,} ({bin_matched/total*100:.1f}%)") #48,341 / 79,906 (60.5%)
print(f"Unmatched: {total - bin_matched:,}") # Unmatched: 31,565
print(f"\nBuilding class distribution (from PLUTO):")
print(joined_demo["broad_bldg_type"].value_counts())

# broad_bldg_type
# residential_multifamily      29984
# residential_single_family    11399
# nonresidential                6958

# consolidate broad_bldg_type and ownership_type:
# prefer PLUTO values where the BIN matched, fall back to permit-derived values
joined_demo["broad_bldg_type"] = joined_demo["broad_bldg_type"].fillna(
    joined_demo["broad_bldg_type_permits"]
)
joined_demo["ownership_type"] = joined_demo["bldg_type"].map({
    'single_family': 'private', 'two_family': 'private',
    'walkup_apartment': 'private', 'elevator_apartment': 'private',
    'warehouse': 'private', 'factory_industrial': 'private',
    'garage': 'private', 'hotel': 'private', 'hospital_health': 'private',
    'theatre': 'private', 'retail_store': 'private', 'loft': 'private',
    'religious': 'private', 'asylum_home': 'private', 'office': 'private',
    'public_assembly': 'private', 'outdoor_recreation': 'public',
    'condominium': 'private', 'mixed_use_residential': 'private',
    'transportation': 'public', 'utility': 'public', 'vacant': 'public',
    'educational': 'public', 'government': 'public', 'miscellaneous': 'public',
}).fillna(joined_demo["ownership_type_permits"])

# exclude Breezy Point outlier (BBL 4163500400):
# cooperative where 1,877 SFH share one BBL — Hurricane Sandy rebuilds inflate Queens SFH volume
joined_demo = joined_demo[joined_demo["BBL"] != "4163500400"].copy()
print(f"\nAfter Breezy Point exclusion: {len(joined_demo):,}")

print("\nFinal broad_bldg_type distribution:")
print(joined_demo["broad_bldg_type"].value_counts())
print("\nFinal ownership_type distribution:")
print(joined_demo["ownership_type"].value_counts())
print(f"\nVolume nulls (unmatched BINs): {joined_demo['volume'].isna().sum():,}")

# export
out_path = "/Users/nboland/Projects/concrete-jungle/model/data/dm_permits_clean.csv"
joined_demo.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")
