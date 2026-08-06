# Data Files

This project draws on public datasets spanning municipal permitting records, tax lot data, building codes, and census demographics to reconstruct concrete accumulation across NYC's five boroughs (2012–2024).

|Category| Description | Source | 
|---|---|---|
| Building Footprint| Provides granular data on newly constructed buildings across NYC, including building dimensions (floor area, building height, number of floors) | [NYC Footprint Data](https://github.com/CityOfNewYork/nyc-geo-metadata/tree/main) |
| Construction | Provides the number of floors per building and building classifications within each Borough-Block-Lot (BBL) of NYC | [NYC Open Data](https://data.cityofnewyork.us/Housing-Development/DOB-Job-Application-Filings/ic3t-wcy2/about_data) |
| Building Footprint | Used as a proxy for concrete volume (m3), calculated using the building height and footprint area fields| [NYC MapHub](https://nycmaps-nyc.hub.arcgis.com/datasets/nyc::building/about) |
| Concrete Impact | Provides the Global Warming Potential (GWP) for ready-mix concrete in the US Eastern Region, rated by compression strength | [NRMCA LCA Benchmark for Ready-Mixed Concrete](https://www.nrmca.org/wp-content/uploads/2020/10/NRMCA_REGIONAL_BENCHMARK_April2020.pdf) |
| Concrete Impact | Provides the maximum GWP for ready-mix concrete in New York State under new guidelines, rated by compression strength | [New York State Buy Clean Concrete Guidelines](https://ogs.ny.gov/new-york-state-buy-clean-concrete-guidelines) |
| Socioeconomic Indicator | Used the American Census Survey median household income across all 1,760 matched tracts in our project (NYC’s five boroughs) | [American Census Survey, Table S1903](https://data.census.gov/table?q=S1903) |
| Socioeconomic Indicator | Map of NYC's Census tracts visualized, clipped to the shoreline so as not to account for census tracts that intersect with waterways | [2020 NYC Census Tracts](https://data.cityofnewyork.us/City-Government/2020-Census-Tracts/63ge-mke6/about_data) |
| Building Footprint | Section 404.2 details the minimum reinforcement for a suspended concrete slab | [NY State Standard for Residential Construction in High Wind Regions 2014](https://up.codes/viewer/new_york/icc-600-2014/chapter/4/buildings-with-concrete-or-masonry-exterior-walls#404.2) |
| Building Footprint | Section 1904.3 details the minimum compression strength per type of concrete construction | [NYC Building Code 2022](https://up.codes/viewer/new_york_city/nyc-building-code-2022/chapter/19/concrete#19) |

## Pipeline
Permits were joined to PLUTO and footprint data to derive per-building dimensions, then classified into three building types — non-residential (NR), multi-family residential (MFR), and single-family residential (SFR). Concrete slab volume was calculated from footprint area × slab thickness × floor count, and converted to embodied carbon using GWP factors weighted by compression strength under both BAU and Buy Clean scenarios. Sample: 17,764 new buildings (2012–2024), matched to 1,760 census tracts (~75% of NYC tracts with construction activity).

<p align="center">
  <img width="441" height="368" alt="Screenshot 2026-08-06 at 10 06 36 AM" src="https://github.com/user-attachments/assets/c8787e4f-d6be-4581-8875-a72af47c2f85" />
</p>

## Key limitations:
- No outflow tracking (demolitions not included — inflow-only MFA)
- PLUTO building classifications apply at the BBL level, not per individual structure
- Floor counts partially extrapolated where missing
- Permit approval doesn't guarantee actual construction completion
- Census tract boundaries may have shifted slightly over the 12-year window
