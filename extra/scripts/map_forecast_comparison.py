"""
map_forecast_comparison.py

Interactive map comparing embodied carbon in forecast new construction (2024–2033)
under two scenarios:
  - BAU:       all buildings use NRMCA Eastern region GWP throughout
  - Buy Clean: all buildings use NYS OGS Buy Clean GWP limits from BUY_CLEAN_START_YEAR

Each simulated building is placed at a location sampled from historical NB permit
centroids (matched to PLUTO via BASE_BBL, by building type), giving a realistic
geographic distribution of new construction activity.

Toggle between BAU and Buy Clean with the buttons in the top panel.
The colour scale is shared across both scenarios so carbon values are directly
comparable.

Run from: model/
Output:   model/outputs/map_forecast_comparison.html
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (
    BUILDING_STOCK_FILE,
    CUFT_TO_CUM,
    RANDOM_SEED,
)
from stock import load_nb_permits, run_phase1
from forecast import run_phase2

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "map_forecast_comparison.html",
)

BTYPES = ["residential_single_family", "residential_multifamily", "nonresidential"]


# ── location helpers ───────────────────────────────────────────────────────────

def load_nb_centroids() -> pd.DataFrame:
    """
    Join historical NB permits to PLUTO centroids via BASE_BBL.
    Returns a DataFrame with columns: broad_bldg_type, lon, lat.
    These are used as a sampling pool to assign locations to simulated
    forecast buildings.
    """
    print("Loading PLUTO centroids for NB permit location pool… (~30–60s)")
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    cents = gpd.GeoSeries(gdf.geometry.centroid, crs=gdf.crs).to_crs("EPSG:4326")
    coords = pd.DataFrame({
        "BASE_BBL": gdf["BASE_BBL"].astype(str).str.replace(r"\.0$", "", regex=True),
        "lon":      cents.x.round(5),
        "lat":      cents.y.round(5),
    }).drop_duplicates("BASE_BBL")

    nb = load_nb_permits()
    nb["BASE_BBL"] = nb["BASE_BBL"].astype(str).str.replace(r"\.0$", "", regex=True)
    nb_loc = nb.merge(coords, on="BASE_BBL", how="inner")
    nb_loc = nb_loc[
        nb_loc["broad_bldg_type"].isin(BTYPES) &
        nb_loc["lon"].notna() &
        nb_loc["lat"].notna()
    ]
    print(f"  {len(nb_loc):,} NB permits with centroid coordinates")
    return nb_loc[["broad_bldg_type", "lon", "lat"]]


def build_location_pools(nb_loc: pd.DataFrame) -> dict:
    """Build per-building-type arrays of (lon, lat) for random sampling."""
    return {
        btype: nb_loc[nb_loc["broad_bldg_type"] == btype][["lon", "lat"]].values
        for btype in BTYPES
    }


def assign_locations(
        df: pd.DataFrame,
        location_pools: dict,
        rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Vectorised location assignment.  For each building type, sample from the
    historical NB permit centroid pool with replacement.
    """
    df = df.copy()
    df["lon"] = -73.98   # NYC fallback
    df["lat"] =  40.73
    for btype in BTYPES:
        mask = df["broad_bldg_type"] == btype
        pool = location_pools.get(btype)
        if pool is not None and len(pool) > 0:
            n   = int(mask.sum())
            idx = rng.integers(len(pool), size=n)
            df.loc[mask, "lon"] = pool[idx, 0]
            df.loc[mask, "lat"] = pool[idx, 1]
    return df


# ── colour / size encoding ────────────────────────────────────────────────────

def encode_color(series: pd.Series, vmin: float, vmax: float) -> np.ndarray:
    """Log-scale green → yellow → red with a shared range across both scenarios."""
    log_v = np.log1p(series.values)
    t = np.clip((log_v - vmin) / max(vmax - vmin, 1e-10), 0.0, 1.0)
    r = np.where(t < 0.5, (t * 2 * 255), 255).astype(np.uint8)
    g = np.where(t < 0.5, 200, ((1 - (t - 0.5) * 2) * 200)).astype(np.uint8)
    b = np.full(len(t), 40, dtype=np.uint8)
    a = np.full(len(t), 190, dtype=np.uint8)
    return np.stack([r, g, b, a], axis=1)


def encode_radius(gfa_m2: pd.Series) -> np.ndarray:
    """Radius in metres, scaled by sqrt(GFA), clamped 4–80 m."""
    return np.clip(np.sqrt(gfa_m2.clip(lower=1).values) * 0.5, 4, 80).round(1)


# ── HTML generation ───────────────────────────────────────────────────────────

def serialise_layer(df: pd.DataFrame, vmin: float, vmax: float) -> dict:
    colors = encode_color(df["embodied_carbon_kgco2e"], vmin, vmax)
    radii  = encode_radius(df["gfa_m2"])
    type_abbr = df["broad_bldg_type"].map({
        "residential_single_family": "SF residential",
        "residential_multifamily":   "MF residential",
        "nonresidential":            "Non-residential",
    }).fillna("Unknown").tolist()
    return {
        "lons":   df["lon"].round(5).tolist(),
        "lats":   df["lat"].round(5).tolist(),
        "colors": colors.tolist(),
        "radii":  radii.tolist(),
        "types":  type_abbr,
        "carbon": (df["embodied_carbon_kgco2e"] / 1000).round(1).tolist(),
        "year":   df["year"].tolist(),
    }


def build_html(bau_df: pd.DataFrame, bc_df: pd.DataFrame) -> str:
    # Shared log-scale colour range so BAU and Buy Clean are directly comparable
    all_carbon = pd.concat([
        bau_df["embodied_carbon_kgco2e"],
        bc_df["embodied_carbon_kgco2e"],
    ])
    log_all = np.log1p(all_carbon.values)
    vmin = float(np.percentile(log_all, 2))
    vmax = float(np.percentile(log_all, 98))

    print("Encoding colours and radii…")
    data_json = json.dumps({
        "BAU":      serialise_layer(bau_df, vmin, vmax),
        "BuyClean": serialise_layer(bc_df,  vmin, vmax),
    })

    bau_total = bau_df["embodied_carbon_kgco2e"].sum() / 1e6
    bc_total  =  bc_df["embodied_carbon_kgco2e"].sum() / 1e6
    avoided   = bau_total - bc_total
    n_bau     = len(bau_df)
    n_bc      = len(bc_df)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NYC Forecast Embodied Carbon — BAU vs Buy Clean</title>
<script src="https://unpkg.com/deck.gl@9/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
<style>
  body {{ margin: 0; padding: 0; font-family: sans-serif; }}
  #map {{ width: 100vw; height: 100vh; }}
  #controls {{
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
    background: white; padding: 10px 20px; border-radius: 8px;
    box-shadow: 2px 2px 8px rgba(0,0,0,.25); z-index: 999;
    text-align: center; white-space: nowrap;
  }}
  #controls h3 {{ margin: 0 0 5px 0; font-size: 13px; font-weight: bold; }}
  .stats {{ font-size: 11px; color: #555; margin-bottom: 8px; }}
  .btn {{
    padding: 6px 18px; border: none; border-radius: 4px; cursor: pointer;
    font-size: 12px; font-weight: bold; margin: 0 4px;
    transition: background 0.15s;
  }}
  .btn.active {{ background: #2563eb; color: white; }}
  .btn:not(.active) {{ background: #e5e7eb; color: #374151; }}
  #tooltip {{
    position: fixed; pointer-events: none;
    background: white; padding: 6px 10px; border-radius: 4px;
    box-shadow: 1px 1px 4px rgba(0,0,0,.2);
    font-family: sans-serif; font-size: 12px; display: none;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div id="controls">
  <h3>NYC New Construction — Embodied Carbon in Concrete (2024–2033 forecast)</h3>
  <div class="stats">
    BAU: <b>{bau_total:,.0f} ktCO\u2082e</b> &nbsp;|&nbsp;
    Buy Clean: <b>{bc_total:,.0f} ktCO\u2082e</b> &nbsp;|&nbsp;
    Avoided: <b>{avoided:,.0f} ktCO\u2082e</b> &nbsp;&nbsp;
    <span style="color:#888">green = low &nbsp; red = high (log scale, shared)</span>
  </div>
  <button class="btn active" id="btn-bau" onclick="switchScenario('BAU')">BAU</button>
  <button class="btn"        id="btn-bc"  onclick="switchScenario('BuyClean')">Buy Clean (all buildings)</button>
</div>
<div id="tooltip"></div>
<script>
const RAW = {data_json};

function makeData(key) {{
  const d = RAW[key];
  const N = d.lons.length;
  const arr = new Array(N);
  for (let i = 0; i < N; i++) {{
    arr[i] = {{
      position: [d.lons[i], d.lats[i]],
      color:    d.colors[i],
      radius:   d.radii[i],
      type:     d.types[i],
      carbon:   d.carbon[i],
      year:     d.year[i],
    }};
  }}
  return arr;
}}

const tooltip = document.getElementById('tooltip');

function makeLayer(scenario) {{
  return new deck.ScatterplotLayer({{
    id: 'buildings',
    data: makeData(scenario),
    getPosition:   d => d.position,
    getFillColor:  d => d.color,
    getRadius:     d => d.radius,
    radiusMinPixels: 1,
    radiusMaxPixels: 30,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 80],
  }});
}}

const deckgl = new deck.DeckGL({{
  container: 'map',
  mapStyle: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  initialViewState: {{ longitude: -73.98, latitude: 40.73, zoom: 11, pitch: 0 }},
  controller: true,
  layers: [makeLayer('BAU')],
  onHover: ({{object, x, y}}) => {{
    if (object) {{
      tooltip.style.display = 'block';
      tooltip.style.left = (x + 10) + 'px';
      tooltip.style.top  = (y + 10) + 'px';
      tooltip.innerHTML =
        '<b>' + object.type + '</b> (' + object.year + ')<br>' +
        'Embodied carbon: <b>' + object.carbon.toLocaleString() + ' tCO\u2082e</b>';
    }} else {{
      tooltip.style.display = 'none';
    }}
  }},
}});

function switchScenario(scenario) {{
  deckgl.setProps({{ layers: [makeLayer(scenario)] }});
  document.getElementById('btn-bau').classList.toggle('active', scenario === 'BAU');
  document.getElementById('btn-bc').classList.toggle('active',  scenario === 'BuyClean');
}}
</script>
</body>
</html>"""
    return html


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    rng = np.random.default_rng(RANDOM_SEED)

    # Build location pool from PLUTO + historical NB permits
    nb_loc         = load_nb_centroids()
    location_pools = build_location_pools(nb_loc)

    # Run Phase 1 + 2
    print("\nRunning Phase 1 (historical stock reconstruction)…")
    p1 = run_phase1()

    print("\nRunning Phase 2 (forecast 2024–2033)…")
    p2 = run_phase2(p1["nb"], p1["dm"], p1["building_stock"])

    building_carbon = p2["building_carbon"]

    bau_df = building_carbon[building_carbon["scenario"] == "BAU"].copy().reset_index(drop=True)
    bc_df  = building_carbon[building_carbon["scenario"] == "BuyClean"].copy().reset_index(drop=True)

    # Assign sampled geographic locations by building type
    print("Assigning locations to simulated buildings…")
    bau_df = assign_locations(bau_df, location_pools, rng)
    # Use the same seed offset so both scenarios sample similar areas
    rng_bc = np.random.default_rng(RANDOM_SEED)
    bc_df  = assign_locations(bc_df, location_pools, rng_bc)

    print("Building HTML…")
    html = build_html(bau_df, bc_df)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print("Writing HTML…")
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6
    bau_total = bau_df["embodied_carbon_kgco2e"].sum() / 1e6
    bc_total  =  bc_df["embodied_carbon_kgco2e"].sum() / 1e6

    print(f"\nMap saved → {OUTPUT_FILE}  ({size_mb:.1f} MB)")
    print(f"BAU buildings      : {len(bau_df):,}")
    print(f"Buy Clean buildings: {len(bc_df):,}")
    print(f"BAU total          : {bau_total:,.0f} ktCO₂e")
    print(f"Buy Clean total    : {bc_total:,.0f} ktCO₂e")
    print(f"Avoided            : {bau_total - bc_total:,.0f} ktCO₂e")


if __name__ == "__main__":
    main()
