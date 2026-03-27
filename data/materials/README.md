# Building Materials

## Cement Import Data: 
To quantify the metabolism of concrete consumption in NYC, we collected cement import data from the USGS open source website. The USGS annually releases reports on the statistics on the worldwide supply of, demand for, and flow of the mineral commodities, including cement. We collected data from 2001 to 2023 in .XLSX format which includes the city-level statistics for cement imports in NYC. 

## Calculating Cement Imports: 
Our import data doesn’t differentiate between cement used for building construction versus cement consumed in other sectors (i.e., roads, bridges, etc.). Thus, while critically analyzing our data, we determined that it doesn’t make sense to use our cement import data as a proxy for cement use in the construction of new buildings. We plan to use our cement import data as an anchor for NYC’s cement consumption; linking it with the total cement intensity in our building stock to estimate the amount of cement consumed by the building sector.  

## Cement Intensity Data
Since our project proposal, we identified a source to estimate the cement intensity for different building types in NYC (source: https://github.com/TomerFishman/MaterialIntensityEstimator). This data is specific to the “OECD_USA” region. We recognize that material intensities vary significantly by region, state, and city, however, for the purpose of this project, we are assuming the following cement intensities for three building type classes in NYC: Non-Residential, Residential Multi-Family, and Residential Single-Family. 

## Calculating Cement Imports for Use in the Building Sector: 
Using this data in tandem with our joined PLUTO/OD data, we will be able to estimate how much cement is used in each building in NYC.
