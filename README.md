# The Concrete Jungle: A Dynamic Material Flow and Agent-Based Analysis of Embodied Carbon in New York City's Built Environment

- EAS 501.074: Sustainable Urban Systems
- University of Michigan School for the Environment and Sustainability

## Research Question: 
If New York City (NYC) mandates “Buy Clean concrete” standards across all building construction activities across the city, how much embodied carbon could be avoided relative to a business-as-usual (BAU) baseline over 2023-2033?

## Sustainability Intervention: 
Using these cleaned datasets, we plan to model the “Buy Clean” policy as the sustainability intervention for reducing embodied carbon across the building sector in NYC. We found that other US cities have implemented similar policies to reduce the consumption of regular concrete, replacing it with green concrete instead. Honolulu started using low-carbon concrete in 2019 by adding on the injection of recycled CO2 from industrial emitters. Houston set their own “Green Action Plan” to reduce greenhouse gas emissions by 80% by 2050, with a focus on the promotion of sustainable building practices. For our intervention, we plan to model the use of green concrete under three penetration scenarios ranging from 10-30% lower CO2 emissions compared to standard concrete, without offsets. Thus, our sustainability intervention will focus on comparing CO2 emissions from conventional concrete used in single-family residential, multifamily residential, and nonresidential buildings, with a forecast of emissions under the adoption of green concrete alternatives in NYC. 

## Roadmap: 
We plan to model the embodied carbon in NYC buildings from 2001-2023 and create a ten-year forecast from 2023-2033. Our historical data reconstructs annual cement flows through cement imports into the city and changes in building stock from new construction and demolition. These historical patterns will be used to calibrate a linear regression forecast model which projects future building stock trajectories. We will run our forecast under two scenarios: 

1) business as usual
2) green cement policies 

The second scenario will be calibrated by reducing the cement intensity per building type by 10-30% penetration rates which simulates low-carbon substitution goals. We plan to use a Monte Carlo simulation to propagate uncertainty through both scenarios, where each of the 1,000 runs per building will draw a cement intensity from the empirical distribution for its building class type, multiply this by gross floor area, and apply a scenario-appropriate emissions factor to yield a building-level embodied carbon estimate. Citywide totals will be summed across all buildings for each run, producing three credible intervals for both scenarios (p5, p50, and p95). We will analyze the degree of overlap between the BAU and green cement output distributions to help us understand the impact of sustainable intervention policies. Final outputs will be integrated into a UI-forward, object-based simulation model representing all NYC buildings with their embodied carbon, allowing others to use this platform for ongoing scenario analysis and policy evaluation for the building sector in NYC. 

<img width="541" height="625" alt="Screenshot 2026-03-27 at 4 45 46 PM" src="https://github.com/user-attachments/assets/a02a17b9-2343-4b50-8ae8-fb14d13c14f8" />
