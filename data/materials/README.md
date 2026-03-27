# Building Materials

## Cement Import Data: 
To quantify the metabolism of concrete consumption in NYC, we collected cement import data from the USGS open source website. The USGS annually releases reports on the statistics on the worldwide supply of, demand for, and flow of the mineral commodities, including cement. We collected data from 2001 to 2023 in .XLSX format which includes the city-level statistics for cement imports in NYC. 

## Calculating Cement Imports: 
Our import data doesn’t differentiate between cement used for building construction versus cement consumed in other sectors (i.e., roads, bridges, etc.). Thus, while critically analyzing our data, we determined that it doesn’t make sense to use our cement import data as a proxy for cement use in the construction of new buildings. We plan to use our cement import data as an anchor for NYC’s cement consumption; linking it with the total cement intensity in our building stock to estimate the amount of cement consumed by the building sector.  

## Cement Intensity Data
Since our project proposal, we identified a source to estimate the cement intensity for different building types in NYC (source: https://github.com/TomerFishman/MaterialIntensityEstimator). This data is specific to the “OECD_USA” region. We recognize that material intensities vary significantly by region, state, and city, however, for the purpose of this project, we are assuming the following cement intensities for three building type classes in NYC: Non-Residential, Residential Multi-Family, and Residential Single-Family. 

## Calculating Cement Imports for Use in the Building Sector: 
Using this data in tandem with our joined PLUTO/OD data, we will be able to estimate how much cement is used in each building in NYC.

## Files:
|Directory | Filename | Source | Category | 
|---|---|---|---|
| USGS-data | ds140-cement-2021.xlsx | (USGS)[https://www.usgs.gov/media/files/cement-historical-statistics-data-series-140] | National Cement Consumption - Validation Only |
| USGS-data | US-Cement-Annual-Yearbook-2023.pdf | (ACA)[https://www.cement.org/wp-content/uploads/2024/07/Sample_US-Cement-Annual-Yearbook.pdf] | National Cement Production - Validation Only | 
| pluto-data | Primary_Land_Use_Tax_Lot_Output_(Pluto)_20260312.csv | (NYC Open Data)[https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks/data_preview] | Building Stock Inventory |
| DOB-application-data | DOB_Job_Application_Filings_20260316.csv | (NYC Open Data)[https://data.cityofnewyork.us/Housing-Development/DOB-Job-Application-Filings/ic3t-wcy2/about_data] | Construction Inflow | 
| DOB-occupancy-data | DOB_NOW__Certificate_of_Occupancy_20260312.csv | (NYC Open Data)[https://data.cityofnewyork.us/Housing-Development/DOB-NOW-Certificate-of-Occupancy/pkdm-hqz6/about_data] | Construction Inflow - Validation Only |
| DOB-demolition-data | *** | (NYC Open Data)[https://data.cityofnewyork.us/Housing-Development/NYC-Demolition-Building/j7h9-tb8p/about_data] | Demolition | 
| USGS-data | myb1-2002-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2003-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2004-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2005-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2006-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2007-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2008-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2009-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2010-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2011-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| myb1-2012-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2013-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2014-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2015-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2016-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2017-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2018-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2019-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2020-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2021-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2022-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2023-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
| USGS-data | myb1-2023-cemen.xls | (USGS)[https://www.usgs.gov/centers/national-minerals-information-center/cement-statistics-and-information] | Cement Imports |
