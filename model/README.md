## Model Roadmap:

We plan to model the embodied carbon in NYC buildings from 2001-2023 and create a ten-year forecast from 2023-2033. Our historical data reconstructs annual cement flows through cement imports into the city and changes in building stock from new construction and demolition. These historical patterns will be used to calibrate a linear regression forecast model which projects future building stock trajectories. We will run our forecast under two scenarios: 

1) business-asusual
2) green cement policies

The second scenario will be calibrated by reducing the cement intensity per building type by 10-30% penetration rates which simulates low-carbon substitution goals. We plan to use a Monte Carlo simulation to propagate uncertainty through both scenarios, where each of the 1,000 runs per building will draw a cement intensity from the empirical distribution for its building class type, multiply this by gross floor area, and apply a scenario-appropriate emissions factor to yield a building-level embodied carbon estimate. Citywide totals will be summed across all buildings for each run, producing three credible intervals for both scenarios (p5, p50, and p95). We will analyze the degree of overlap between the BAU and green cement output distributions to help us understand the impact of sustainable intervention policies. Final outputs will be integrated into a UI-forward, object-based simulation model representing all NYC buildings with their embodied carbon, allowing others to use this platform for ongoing scenario analysis and policy evaluation for the building sector in NYC.

The following image provides a visual roadmap that will guide our deliverables for the first project presentation:
