# NYC’s Building Demolition 

## Data Loading and Cleaning: 
We imported the cleaned and joined PLUTO/OD GeoPackage, which had ~1,082,500 records, as well as data downloaded from the Department of Building’s permitting site (~2,714,400 records). As our analysis we consider the volume of demolition by filtering our raw data to “Job Type” and filtering for demolition data, represented by the “DM” code, resulting in ~80,300 records. We kept only approved and completed permits using NYC DOB status codes ~ 79,900 for DM data. 

## Creating a BBL Code in the Filtered Dataset: 
In our demolition dataframe, the Block and Lot were changed to float values, and there were two instances of typos in these columns (e.g, a block was the letter O instead of a 0, and there was an incomplete lot value). There were also 11 instances where either the Block or Lot value was incomplete, so these rows were dropped. In the cleaned PLUTO data, the code is represented as a 10-digit integer, so we needed to ensure that the bottom-up BBL was also 10-digits (and spatially accurate). We built out integer mapping (e.g., Manhattan = 1, Brooklyn = 3) based on borough codes in the PLUTO dataset, and used the following concatenation: 1 digit borough + 5 digit block + 4 digit lot (i.e., B+B+L). We noted that PLUTO data seemed to have a different 10-digit structure than other datasets (i.e., usually the borough is a two-digit code, wherein Manhattan = 10, Brooklyn = 30). The same script was applied to DM data, and all BBLs were 10-digits, so no further cleaning was needed. We identified 10 NB permits with 11-digit BBLs and dropped those from our data.

## Applying Building Classifications: 
For DM data, we used the classification columns from the previous footprint script to assign either a multifamily home, single-family home, or non-residential classification, which will eventually be a proxy to get the volume of concrete outflows.
