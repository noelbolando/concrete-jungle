"""
    NYC Building Footprint Data

    To describe the shape of building footprints in NYC and estimate the volume of building materials used in these buildings,
    we leverage two opensource datasets:
    1. Pluto Data: https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks/data_preview
    2. NYC Building Footprint Data: https://github.com/CityOfNewYork/nyc-geo-metadata/tree/main

    The Pluto data gives us information about buildings in NYC including year built, floor area, building class, and borough.
    Pluto is updated quarterly.
    Pluto is in csv/xlsx format.
   
    The NYC Building Footprint gives us information about the footprint areas of all buildings in NYC.
    NYC Building Footprint is updated weekly.

    Together, we plan to use these datasets to get the volume of each building in NYC across all building types. 
"""

# import libraries
from enum import unique
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import sys

pd.set_option('display.max_columns', None)

# pluto dataset:
pluto_csv = pd.read_csv('') # add the pluto data here
print(pluto_csv.columns)
print(pluto_csv.head())

# NYC opendata (OD) dataset:
nyc_opendata_shp = gpd.read_file('') # add the nyc opendata here
print(nyc_opendata_shp.head())

# changing coordinate system to NY state plane projection
nyc_opendata_shp = nyc_opendata_shp.to_crs(epsg=2263)
print("ARE BBL NUM UNIQUE:", nyc_opendata_shp['MAPPLUTO_B'].nunique()), len(nyc_opendata_shp)

# filtering for just the buildings -- (od = NYC Opendata)
buildings_od = nyc_opendata_shp[nyc_opendata_shp['FEATURE_CO'] == 2100].copy()
print(buildings_od.head())

# erging pluto dataset's desired columns with nycOD shapefile:
# (each tax lot sometimes goes by primary building only...?) = pluto does NOT have building class by individual building = building class by LOT
pluto_slim = pluto_csv[[
    'bbl',          # join key
    'bldgclass',    # building type
    'numbldgs',
    'yearbuilt',
    'numfloors',
]].copy()

#putting both columns to string for join
pluto_slim['bbl'] = pluto_slim['bbl'].astype(int).astype(str)
nyc_opendata_shp['MAPPLUTO_B'] = nyc_opendata_shp['MAPPLUTO_B'].astype(int).astype(str)

# joining datasets by bbl. bbl =  Borough, Block, and Lot information
bldg_merged = nyc_opendata_shp.merge(
    pluto_slim,
    left_on='MAPPLUTO_B',
    right_on='bbl',
    how='left')

print(f"Total buildings BEFORE MERGE:  {len(nyc_opendata_shp)}")
print(f"Total buildings BEFORE MERGE:  {len(bldg_merged)}")
print(f"Matched to PLUTO: {bldg_merged['bldgclass'].notna().sum()}")
print(f"No match:         {bldg_merged['bldgclass'].isna().sum()}")

# 335 buildings did not match - DROP NON MATCHES
no_match = bldg_merged['bldgclass'].isna().sum()
print(no_match)
bldg_merged = bldg_merged.dropna(subset=['bldgclass']).copy()

# num of buildings per bbl:
num_bld_check = bldg_merged['numbldgs'].value_counts().sort_index()

# checking building class types:
print(bldg_merged['bldgclass'].unique())
print(bldg_merged['bldgclass'].str[0].unique())

# making 'yearbuilt' a string
bldg_merged['yearbuilt'] = bldg_merged['yearbuilt'].astype('Int64').astype(str)

### BUILDING CLASSIFICATIONS
# link to nyc building class types: https://www.nyc.gov/assets/finance/jump/hlpbldgcode.html
# renaming the building class codes appropriately:
bldg_class_map = {
    'A': 'single_family', #Single Family #private/public
    'B': 'two_family', #Multifamily
    'C': 'walkup_apartment', #Multifamily
    'D': 'elevator_apartment', #Multifamily
    'E': 'warehouse', #Commercial
    'F': 'factory_industrial', #Commercial
    'G': 'garage', #Commercial
    'H': 'hotel', #Comeercial
    'I': 'hospital_health', #Commercial
    'J': 'theatre', #Commercial
    'K': 'retail_store', #Commercial
    'L': 'loft', #Multifamily
    'M': 'religious', #Commercial
    'N': 'asylum_home', #Commercial
    'O': 'office', #Commercial
    'P': 'public_assembly', # commercial
    'Q': 'outdoor_recreation', #Commercial
    'R': 'condominium', #Multifamily
    'S': 'mixed_use_residential', #Multifamily
    'T': 'transportation', #Transport #DROP TRANSPORT
    'U': 'utility', #nonresidential, public
    'V': 'vacant', #Nonresidential, public
    'W': 'educational', #Public --> sorted - split W8 & W6 is private?
    'Y': 'government', #Public
    'Z': 'miscellaneous' #nonresidential, public
}

# assigning building class type
bldg_merged['bldg_type'] = bldg_merged['bldgclass'].str[0].str.upper().map(bldg_class_map)
bldg_merged.head()

# DROP any rows with nan values in the bldg_type column
bldg_merged = bldg_merged.dropna(subset=['bldg_type']).copy()
# DROP all columns of transportation and  outdoor rec:
bldg_merged = bldg_merged[~bldg_merged['bldg_type'].isin(['outdoor_recreation', 'transportation'])].copy()

# NEW classification of building types:
broad_class_map = {
    'single_family': 'residential_single_family',
    'two_family': 'residential_multifamily',
    'walkup_apartment': 'residential_multifamily',
    'elevator_apartment': 'residential_multifamily',
    'condominium': 'residential_multifamily',
    'mixed_use_residential': 'residential_multifamily',
    'loft': 'residential_multifamily',
    'warehouse': 'nonresidential',
    'factory_industrial': 'nonresidential',
    'garage': 'nonresidential',
    'hotel': 'nonresidential',
    'hospital_health': 'nonresidential',
    'theatre': 'nonresidential',
    'retail_store': 'nonresidential',
    'religious': 'nonresidential',
    'asylum_home': 'nonresidential',
    'office': 'nonresidential',
    'public_assembly': 'nonresidential',
    'outdoor_recreation': 'nonresidential',
    'transportation': 'nonresidential',
    'utility': 'nonresidential',
    'vacant': 'nonresidential',
    'educational': 'nonresidential',
    'government': 'nonresidential',
    'miscellaneous': 'nonresidential',
}

bldg_merged['broad_bldg_type'] = bldg_merged['bldg_type'].map(broad_class_map)

# check distribution
print(bldg_merged['broad_bldg_type'].value_counts())

# ANOTHER CLASSIFICATION of public vs private (new column)
ownership_map = {
    'single_family': 'private',
    'two_family': 'private',
    'walkup_apartment': 'private',
    'elevator_apartment': 'private',
    'warehouse': 'private',
    'factory_industrial': 'private',
    'garage': 'private',
    'hotel': 'private',
    'hospital_health': 'private',
    'theatre': 'private',
    'retail_store': 'private',
    'loft': 'private',
    'religious': 'private',
    'asylum_home': 'private',
    'office': 'private',
    'public_assembly': 'private',
    'outdoor_recreation': 'public',
    'condominium': 'private',
    'mixed_use_residential': 'private',
    'transportation': 'public',
    'utility': 'public',
    'vacant': 'public',
    'educational': 'public',
    'government': 'public',
    'miscellaneous': 'public',
}

bldg_merged['ownership_type'] = bldg_merged['bldg_type'].map(ownership_map)

# table/stats to look at the bldg classes
print("CHECK IF CLASSIFICATION COLUMNS WORKED:::::")
print(bldg_merged.head())
check_bldg_type = bldg_merged['bldg_type'].value_counts().sort_index()

# CALCULATING VOLUME:
print(bldg_merged.crs) # --> 2263 crs is in sq ft

# getting area in square feet
bldg_merged['footprint_area_sqft'] = bldg_merged.geometry.area
# checking for negative values and dropping:
print(bldg_merged[bldg_merged['footprint_area_sqft'] < 0]['footprint_area_sqft'].describe())
print(bldg_merged[bldg_merged['footprint_area_sqft'] < 0].shape)
print(len(bldg_merged[bldg_merged['footprint_area_sqft'] < 0]))
# dropping negative volume values (theres like only 45 of them)
    # (neg volumes occur because its a GIS error):
bldg_merged = bldg_merged[bldg_merged['footprint_area_sqft'] >= 0].copy()

# Verify
print((bldg_merged['footprint_area_sqft'] < 0).sum())  # should be 0


# calculate volume (cubic feet)
bldg_merged['volume'] = bldg_merged['footprint_area_sqft'] * bldg_merged['HEIGHT_ROO']

# checking calc
print(bldg_merged[['footprint_area_sqft', 'HEIGHT_ROO', 'volume']].describe())

# seeing volume by building class type
print(bldg_merged.groupby('broad_bldg_type')['footprint_area_sqft'].sum())

# any buildings with 0 volume check:
print((bldg_merged['volume'] == 0).sum()) # --> approx 700 with 0 volume -> drop?
print(len(bldg_merged))
print(bldg_merged['volume'].describe())
# types of buildings with 0 volume
print("BUILDING TYPES VOLUME OF 0 ", bldg_merged[bldg_merged['volume'] == 0].groupby('bldg_type').size())

#### STATS OF COMPLETE DATASET:
print("STATS OF COMPLETE DATASET")

bldg_merged.groupby('bldg_type').agg(
    count=('volume', 'count'),
    mean_volume=('volume', 'mean'),
    median_volume=('volume', 'median'),
    mean_footprint=('footprint_area_sqft', 'mean'),
    mean_height=('HEIGHT_ROO', 'mean')
).round(2)

# avg and sum volume per building type
print("MEAN VOLUME BY BUILDING TYPE: ", bldg_merged.groupby('bldg_type')['volume'].mean(),
      "SUM VOLUME PER BUILDING TYPE: ", bldg_merged.groupby('bldg_type')['volume'].sum())

# count of buildings per year built:
print("COUNT BUILDINGS PER YR BUILD", bldg_merged.groupby('yearbuilt')['bldg_type'].count())

year_counts = bldg_merged.groupby('yearbuilt')['bldg_type'].count()
print(year_counts)

# Get last 50 years (1976 to 2025)
year_counts = bldg_merged.groupby('yearbuilt')['bldg_type'].count()
year_counts_50 = year_counts[year_counts.index.astype(int) >= 1976]
year_counts_50.plot(kind='bar', figsize=(20, 6))
plt.title('Number of Buildings Built (Last 50 Years)')
plt.xlabel('Year Built')
plt.ylabel('Number of Buildings')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

## handle NAN values:
print(bldg_merged.isna().sum())
print(pluto_slim.isna().sum())
# num of floors data has a lot of values missing, so shouldnt rely on that

## question-- what should be removed for further cleaning??

## does the number of buildings per BBL match the OD?
        # --> cross check with number of ODs found in each bbl

# see what volume is for an outdoor space: consider excluding
print(bldg_merged[bldg_merged['bldg_type'] == 'outdoor_recreation']['volume'].describe())
# mean of calculated outdoor rec value:  1.609449e+05 --> thats kind of high... no?

# saving df to csv:
bldg_merged.to_file("nyc_data.5.12.gpkg", driver="GPKG")
len(bldg_merged)
