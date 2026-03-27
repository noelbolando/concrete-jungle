# NYC’s Building Construction

## Data Loading and Cleaning: 
We imported the cleaned and joined PLUTO/OD GeoPackage, which had ~1,082,500 records, as well as data downloaded from the Department of Building’s permitting site (~2,714,400 records). As our analysis only considers the volume of new construction and demolition, we filtered the “Job Type” to only include new buildings (NB) (~199,900 records) and added this to our import analysis, ultimately to understand the additive inputs into NYC. We kept only approved and completed permits using NYC DOB status codes which is ~180,500 records for NB. 

## Creating a BBL Code in the Filtered Dataset: 
In our construction dataframe, the Block and Lot were changed to float values, and there were two instances of typos in these columns (e.g, a block was the letter O instead of a 0, and there was an incomplete lot value). There were also 11 instances where either the Block or Lot value was incomplete, so these rows were dropped. In the cleaned PLUTO data, the code is represented as a 10-digit integer, so we needed to ensure that the bottom-up BBL was also 10-digits (and spatially accurate). We built out integer mapping (e.g., Manhattan = 1, Brooklyn = 3) based on borough codes in the PLUTO dataset, and used the following concatenation: 1 digit borough + 5 digit block + 4 digit lot (i.e., B+B+L). We noted that PLUTO data seemed to have a different 10-digit structure than other datasets (i.e., usually the borough is a two-digit code, wherein Manhattan = 10, Brooklyn = 30). The same script was applied to DM data, and all BBLs were 10-digits, so no further cleaning was needed. We identified 10 NB permits with 11-digit BBLs and dropped those from our data. Finally, we verified that all NB permits sharing a BBL had the same building class so that we could aggregate BBL duplicates. This created an 85% match across BBLs. The ~25,000 unmatched NB permits were concentrated in the early 2000s (e.g., 2001-2004), with only 9 unmatched codes from 2022 to 2023, so an underlying assumption is that these lots were either destroyed, redrawn, or that the historical permits for the lots in PLUTO no longer exist. A broad result for NB permits was 101,531 multifamily homes, 33,569 single-family homes, and 19,816 non-residential. 

## New Construction Permits Per Year Per Building Type:
<img width="660" height="297" alt="Screenshot 2026-03-27 at 4 27 04 PM" src="https://github.com/user-attachments/assets/28fac7e9-6e7c-4031-9542-fb7f7cb737aa" />

## New Construction Permits Per Year Per Borough (2000-2022):
<img width="660" height="318" alt="Screenshot 2026-03-27 at 4 27 49 PM" src="https://github.com/user-attachments/assets/ab8a0bb3-9cdb-4376-84dc-5703affb9db5" />

## New Construction Permits Per Building Type (2000-2022): 
<img width="699" height="282" alt="Screenshot 2026-03-27 at 4 28 22 PM" src="https://github.com/user-attachments/assets/95af46f0-2335-4245-8592-ce50397b62bb" />

