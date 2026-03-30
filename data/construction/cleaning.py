"""
    NYC Building Construction Data

    To describe the change of building stock in NYC, we use construction permit data to help us understand
    how much building stock increases on an annual basis.

    NYC Building Construction Permit Data: https://data.cityofnewyork.us/Housing-Development/DOB-Job-Application-Filings/ic3t-wcy2/about_data

    The data gives us floor area constructed per year by building type and borough.
"""

# import libraries 
import geopandas as gpd
import pandas as pd

# load permit data
permits = pd.read_csv(
    "/Users/nboland/Projects/concrete-jungle/data/construction/DOB_Job_Application_Filings_20260329.csv",
    low_memory=False
)

# importing footprint dataset that has BBL and volume data
pluto = gpd.read_file("/Users/nboland/Projects/concrete-jungle/model/data/nyc_data.5.12.gpkg")
print(pluto.columns.tolist())
print(pluto.shape)

# viewing permits dataset
print(permits.columns.tolist())
print(permits.shape)
print(permits["Job Type"].value_counts()) #finding where 'NB' code is

# filter out only New Buildings/NBs
nb = permits[permits["Job Type"] == "NB"].copy()
print(f"NB permits: {len(nb):,}")

# inspecting PLUTO structure to make sure BBLs join correctly
print("PLUTO BASE_BBL sample:")
print(pluto["BASE_BBL"].head(10).tolist()) #make sure all BBLs are consistently 10 digits
print(f"BASE_BBL length sample: {pluto['BASE_BBL'].astype(str).str.len().value_counts()}")

# inspect permits block/lot more carefully
print("Block dtype:", nb["Block"].dtype)
print("Lot dtype:", nb["Lot"].dtype)
print("Block sample:", nb["Block"].head(5).tolist())
print("Lot sample:", nb["Lot"].head(5).tolist())

# there was an O instead of a 0 somewhere so we need to clean that up
# check for non-numeric values in Block and Lot
print("Non-numeric Block values:")
print(nb[~nb["Block"].astype(str).str.replace('.', '', regex=False).str.isnumeric()]["Block"].unique())
print("\nNon-numeric Lot values:")
print(nb[~nb["Lot"].astype(str).str.replace('.', '', regex=False).str.isnumeric()]["Lot"].unique())

# fix the letter O → 0 in Block, then drop NaNs
nb["Block"] = nb["Block"].astype(str).str.replace(r'^O', '0', regex=True)
nb = nb.dropna(subset=["Borough", "Block", "Lot"])
print(f"NB permits after cleaning: {len(nb):,}")

# create an integer for each borough as described in https://www.nyc.gov/assets/buildings/pdf/espm_user_guide.pdf
borough_codes = {
    "MANHATTAN":     1, "MN": 1,
    "BRONX":         2, "BX": 2,
    "BROOKLYN":      3, "BK": 3,
    "QUEENS":        4, "QN": 4,
    "STATEN ISLAND": 5, "SI": 5
}

nb["boro_int"] = nb["Borough"].str.upper().str.strip().map(borough_codes)

# find the status of different permits, we will probably want to drop rows if the permit was denied/incomplete
print("Job Status values:")
print(nb["Job Status"].value_counts())

print("\nJob Status Description values:")
print(nb["Job Status Descrp"].value_counts())

# need to find a column called "Permit Status" because
# I can't find what the different "Job Status" codes mean
print([col for col in permits.columns if any(x in col.lower() for x in ["status", "permit"])])

# drop values if the permit wasn't approved using codes from https://www.nyc.gov/site/buildings/industry/permit-type-and-job-status-codes.page
# note that the status they use is '3' for suspended but in our dataset it's a '9'
approved_perm = ["P", "Q", "R", "U", "X"]

# check work and make sure the nb set only uses approved perms
nb = nb[nb["Job Status"].isin(approved_perm)].copy()
print(f"NB permits after status filter: {len(nb):,}")
print(nb["Job Status"].value_counts())

# check other non-numeric values in the Block and Lot columns (i found one
# because i received an error code, just need to fix them)
print("Non-numeric Block values:")
print(nb[~nb["Block"].astype(str).str.replace('.', '', regex=False).str.isnumeric()]["Block"].unique())
print("\nNon-numeric Lot values:")
print(nb[~nb["Lot"].astype(str).str.replace('.', '', regex=False).str.isnumeric()]["Lot"].unique())
print("Non-numeric boro_int values:")
print(nb[nb["boro_int"].isna()]["Borough"].unique())

# i can't figure out where the issue row is here lol
lotissue = nb["Block"].astype(str).str.contains(r'\.\.\.', regex=True) | \
       nb["Lot"].astype(str).str.contains(r'\.\.\.', regex=True)

print(nb[lotissue][["Borough", "Block", "Lot"]].head(10))
print(f"Rows with '...' : {lotissue.sum()}")
print("\nAll unique Borough values:")
print(nb["Borough"].unique())

# drop this one row that was causing an issue (it was like a ....28 in the lot number)
nb = nb[~lotissue].copy()
print(f"NB permits after cleaning: {len(nb):,}")

# create BBL code in the NB dataset
nb["BBL"] = (
    nb["boro_int"].astype(int).astype(str).str.zfill(1) +
    nb["Block"].astype(float).astype(int).astype(str).str.zfill(5) +
    nb["Lot"].astype(float).astype(int).astype(str).str.zfill(4)
)

# check work
print("Sample constructed BBLs:")
print(nb["BBL"].head(10).tolist()) #finding only the BBLs with 10 digits
print(f"\nBBL length check:\n{nb['BBL'].str.len().value_counts()}")

# find the 11-digit BBLs (there were 10 that appeared from previous step)
eleven = nb[nb["BBL"].str.len() == 11]
print(eleven[["Borough", "Block", "Lot", "BBL"]].head(10))

# confirm there are no 11-digit BBLs in PLUTO
print(f"PLUTO BASE_BBL length check:")
print(pluto["BASE_BBL"].astype(str).str.len().value_counts()) #yay that worked

# check if those specific blocks exist in PLUTO (there are 101 records of these blocks in Queens)
queens_blocks = [1231.0, 15897.0, 15589.0, 12355.0]
print(pluto[pluto["BASE_BBL"].astype(str).str.startswith("4")]["BASE_BBL"].astype(str).str[1:6].astype(int).isin([int(b) for b in queens_blocks]).sum())
for block in queens_blocks:
    block_str = str(int(block)).zfill(5)
    matches = pluto[pluto["BASE_BBL"].astype(str).str[1:6] == block_str]
    print(f"\nBlock {int(block)} in PLUTO ({len(matches)} matches):")
    print(matches[["BASE_BBL", "bldgclass", "broad_bldg_type"]].head(5))
queensmatches = pluto[pluto["BASE_BBL"].astype(str).str.startswith("4") &
                pluto["BASE_BBL"].astype(str).str[1:6].str.lstrip("0") == "1231"]
print(queensmatches[["BASE_BBL"]].head(10))
# What is the max lot number in all of PLUTO?
pluto["lot_digits"] = pluto["BASE_BBL"].astype(str).str[6:]
print("\nLot portion length distribution:")
print(pluto["lot_digits"].str.len().value_counts())
print("\nMax lot value in PLUTO:")
print(pluto["lot_digits"].astype(int).max())

# finally running the join
# drop 11-digit BBLs
nb = nb[nb["BBL"].str.len() == 10].copy()
print(f"NB permits after BBL cleanup: {len(nb):,}")

# join
joined = nb.merge(
    pluto[["BASE_BBL", "bldgclass", "bldg_type", "broad_bldg_type",
           "volume", "footprint_area_sqft", "numfloors", "HEIGHT_ROO"]],
    left_on="BBL",
    right_on="BASE_BBL",
    how="left"
)

# diagnostics
total = len(joined)
bbl_matched = joined["BASE_BBL"].notna().sum()
print(f"Matched: {bbl_matched:,} / {total:,} ({bbl_matched/total*100:.1f}%)")
print(f"Unmatched: {total - bbl_matched:,}")
print("\nBuilding class distribution:")
print(joined["broad_bldg_type"].value_counts())

# check for duplicate BBLs in PLUTO
print(f"Total PLUTO records: {len(pluto):,}")
print(f"Unique BBLs in PLUTO: {pluto['BASE_BBL'].nunique():,}")

dupes = pluto[pluto.duplicated(subset="BASE_BBL", keep=False)]
print(f"\nPLUTO records with duplicate BBLs: {len(dupes):,}")
print("\nExample - multiple structures on same BBL:")
print(dupes[["BASE_BBL", "bldgclass", "broad_bldg_type", "volume"]].head(10))

# see if permits match to structures with different building classes on same BBL
dupes = pluto[pluto.duplicated(subset="BASE_BBL", keep=False)]
print(dupes.groupby("BASE_BBL")["bldgclass"].nunique().value_counts()) #there is only one instance of a building class being different across the lot

# check the date range of NB permits
print("Date column null counts:")
print(nb[["Pre- Filing Date", "Fully Permitted", "Approved", "SIGNOFF_DATE"]].isna().sum())

# pivoting back to data aggregation and will do the data filtering after creating an intermediate file
# aggregate PLUTO to one row per BBL
pluto_agg = pluto.groupby("BASE_BBL").agg(
    bldgclass=("bldgclass", "first"),
    bldg_type=("bldg_type", "first"),
    broad_bldg_type=("broad_bldg_type", "first"),
    ownership_type=("ownership_type", "first"),
    volume=("volume", "sum"),
    footprint_area_sqft=("footprint_area_sqft", "sum"),
    numfloors=("numfloors", "max"),
    HEIGHT_ROO=("HEIGHT_ROO", "max")
).reset_index()

# join
joined = nb.merge(
    pluto_agg,
    left_on="BBL",
    right_on="BASE_BBL",
    how="left"
)

# run diagnostics
total = len(joined)
bbl_matched = joined["BASE_BBL"].notna().sum()
print(f"Matched: {bbl_matched:,} / {total:,} ({bbl_matched/total*100:.1f}%)")
print(f"Unmatched: {total - bbl_matched:,}")
print(f"\nBuilding class distribution:")
print(joined["broad_bldg_type"].value_counts())

# check the unmatched rows
unmatched = joined[joined["BASE_BBL"].isna()]
print("Unmatched permits by borough:")
print(unmatched["Borough"].value_counts())

# checking whether the unmatched values are concentrated in a borough
print("\nUnmatched permits by year:")
print(pd.to_datetime(unmatched["Pre- Filing Date"]).dt.year.value_counts().sort_index()) #brooklyn has the most
print("Unmatched permits by year:")
print(pd.to_datetime(unmatched["Pre- Filing Date"]).dt.year.value_counts().sort_index()) #unmatched records are mostly historical permits, could be demolished, merged, subdivided, or renumbered over the past 20+ years

# export before date filtering
out_path = "/Users/nboland/Projects/concrete-jungle/model/data/nb_permits_clean_2025.csv"
joined.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")