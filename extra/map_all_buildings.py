"""
map_all_buildings.py

Interactive map of embodied carbon for every building in the NYC PLUTO stock
(~1M buildings). Uses pydeck (WebGL) for smooth rendering.

Each building is its centroid dot, sized by sqrt(GFA), colored green→red by
embodied carbon on a log scale. Hover for type + carbon.

Run from: model/
Output:   model/outputs/map_all_buildings.html
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import BUILDING_STOCK_FILE, CUFT_TO_CUM, HISTORICAL_END
from emissions import calc_embodied_carbon_batch, compute_gfa_m2_batch

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outputs",
    "map_all_buildings.html",
)

FALLBACK_YEAR = HISTORICAL_END  # for buildings with no yearbuilt


# ── data loading ──────────────────────────────────────────────────────────────

def load_stock() -> gpd.GeoDataFrame:
    print("Loading building stock… (~30–60s)")
    gdf = gpd.read_file(BUILDING_STOCK_FILE)
    print(f"  {len(gdf):,} buildings loaded")
    return gdf


def calc_carbon(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["volume_m3"] = df["volume"] * CUFT_TO_CUM
    df["year_col"] = (
        pd.to_numeric(df["yearbuilt"], errors="coerce")
        .fillna(FALLBACK_YEAR)
        .clip(lower=1900, upper=FALLBACK_YEAR)
        .astype(int)
    )
    print("Calculating embodied carbon…")
    df["gfa_m2"] = compute_gfa_m2_batch(df)
    df["embodied_carbon_kgco2e"] = calc_embodied_carbon_batch(df, year_col="year_col")
    valid = df["embodied_carbon_kgco2e"].notna() & (df["embodied_carbon_kgco2e"] > 0)
    print(f"  {valid.sum():,} buildings with valid estimate")
    return df[valid].copy()


def extract_centroids(gdf: gpd.GeoDataFrame, df: pd.DataFrame) -> pd.DataFrame:
    print("Extracting centroids…")
    # Compute in original projected CRS, then convert to WGS84
    cents = gpd.GeoSeries(gdf.geometry.centroid, crs=gdf.crs).to_crs("EPSG:4326")
    coords = pd.DataFrame({"BASE_BBL": gdf["BASE_BBL"], "lon": cents.x, "lat": cents.y})
    coords["BASE_BBL"] = coords["BASE_BBL"].astype(str).str.replace(r"\.0$", "", regex=True)

    merged = df.merge(coords.drop_duplicates("BASE_BBL"), on="BASE_BBL", how="inner")
    merged = merged.dropna(subset=["lon", "lat"])
    print(f"  {len(merged):,} buildings with coordinates")
    return merged


# ── colour / size encoding ────────────────────────────────────────────────────

def encode_color(series: pd.Series) -> np.ndarray:
    """Log-scale green → yellow → red, returns uint8 array (N, 4)."""
    log_v = np.log1p(series.values)
    vmin, vmax = np.percentile(log_v, 2), np.percentile(log_v, 98)
    t = np.clip((log_v - vmin) / max(vmax - vmin, 1e-10), 0.0, 1.0)

    r = np.where(t < 0.5, (t * 2 * 255), 255).astype(np.uint8)
    g = np.where(t < 0.5, 200, ((1 - (t - 0.5) * 2) * 200)).astype(np.uint8)
    b = np.full(len(t), 40, dtype=np.uint8)
    a = np.full(len(t), 190, dtype=np.uint8)
    return np.stack([r, g, b, a], axis=1)


def encode_radius(gfa_m2: pd.Series) -> np.ndarray:
    """Radius in metres, scaled by sqrt(GFA), clamped 4–80m."""
    return np.clip(np.sqrt(gfa_m2.clip(lower=1).values) * 0.5, 4, 80).round(1)


# ── compact column-oriented JSON ──────────────────────────────────────────────
#
# pydeck's default row-oriented JSON repeats every field name once per row.
# We instead build a custom layer spec that references pre-serialised typed
# arrays (lons, lats, colors, radii) as flat arrays — roughly 4–5× smaller.

def build_html(df: pd.DataFrame, n_buildings: int, total_ktco2e: float) -> str:
    print("Encoding colours and radii…")
    colors  = encode_color(df["embodied_carbon_kgco2e"])  # (N, 4) uint8
    radii   = encode_radius(df["gfa_m2"])                 # (N,)   float

    # Round coordinates to 5 d.p. (~1m precision) to save characters
    lons = df["lon"].round(5).values.tolist()
    lats = df["lat"].round(5).values.tolist()

    # Tooltip fields — kept short: type abbreviation + carbon (tCO₂e)
    type_abbr = df["broad_bldg_type"].map({
        "residential_single_family": "SF residential",
        "residential_multifamily":   "MF residential",
        "nonresidential":            "Non-residential",
    }).fillna("Unknown").tolist()
    carbon_t  = (df["embodied_carbon_kgco2e"] / 1000).round(1).values.tolist()

    # Serialise as parallel arrays — avoids repeating key names per row
    print("Serialising data arrays…")
    data_json = json.dumps({
        "lons":    lons,
        "lats":    lats,
        "colors":  colors.tolist(),
        "radii":   radii.tolist(),
        "types":   type_abbr,
        "carbon":  carbon_t,
    })

    # Build the page — deck.gl loaded directly from CDN; no pydeck dependency at runtime
    title_text = (
        f"NYC Building Stock — Embodied Carbon in Concrete<br>"
        f"<span style='font-weight:normal;font-size:11px;'>"
        f"{n_buildings:,} buildings · {total_ktco2e:,.0f} ktCO₂e · "
        f"green = low carbon, red = high carbon (log scale)"
        f"</span>"
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NYC Embodied Carbon</title>
<script src="https://unpkg.com/deck.gl@9/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ width: 100vw; height: 100vh; }}
  #title {{
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
    background: white; padding: 8px 18px; border-radius: 6px;
    box-shadow: 2px 2px 8px rgba(0,0,0,.25); z-index: 999;
    font-family: sans-serif; font-size: 13px; font-weight: bold;
    pointer-events: none; white-space: nowrap;
  }}
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
<div id="title">{title_text}</div>
<div id="tooltip"></div>
<script>
const RAW = {data_json};

// Reconstruct row objects for deck.gl ScatterplotLayer
const N = RAW.lons.length;
const data = new Array(N);
for (let i = 0; i < N; i++) {{
  data[i] = {{
    position: [RAW.lons[i], RAW.lats[i]],
    color:    RAW.colors[i],
    radius:   RAW.radii[i],
    type:     RAW.types[i],
    carbon:   RAW.carbon[i],
  }};
}}

const tooltip = document.getElementById('tooltip');

const layer = new deck.ScatterplotLayer({{
  id: 'buildings',
  data,
  getPosition:   d => d.position,
  getFillColor:  d => d.color,
  getRadius:     d => d.radius,
  radiusMinPixels: 1,
  radiusMaxPixels: 30,
  pickable: true,
  autoHighlight: true,
  highlightColor: [255, 255, 255, 80],
}});

const deckgl = new deck.DeckGL({{
  container: 'map',
  mapStyle: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  initialViewState: {{
    longitude: -73.98,
    latitude:  40.73,
    zoom: 11,
    pitch: 0,
  }},
  controller: true,
  layers: [layer],
  onHover: ({{object, x, y}}) => {{
    if (object) {{
      tooltip.style.display = 'block';
      tooltip.style.left = (x + 10) + 'px';
      tooltip.style.top  = (y + 10) + 'px';
      tooltip.innerHTML =
        '<b>' + object.type + '</b><br>' +
        'Embodied carbon: <b>' + object.carbon.toLocaleString() + ' tCO\u2082e</b>';
    }} else {{
      tooltip.style.display = 'none';
    }}
  }},
}});
</script>
</body>
</html>"""
    return html


def main():
    gdf = load_stock()
    df  = calc_carbon(gdf)
    df  = extract_centroids(gdf, df)

    total_ktco2e = df["embodied_carbon_kgco2e"].sum() / 1e6
    html = build_html(df, len(df), total_ktco2e)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print("Writing HTML…")
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT_FILE) / 1e6
    print(f"\nMap saved → {OUTPUT_FILE}  ({size_mb:.0f} MB)")
    print(f"Buildings mapped      : {len(df):,}")
    print(f"Total embodied carbon : {total_ktco2e:,.0f} ktCO₂e")
    print(f"Median per building   : {df['embodied_carbon_kgco2e'].median():,.0f} kgCO₂e")


if __name__ == "__main__":
    main()
