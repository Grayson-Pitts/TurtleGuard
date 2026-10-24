# TurtleGuard — Beach Priority Prototype v2

## What changed
- Displays official FWC beach *line segments* with a red-yellow-green priority gradient instead of map pins. The live ArcGIS endpoint requires internet and may be blocked by browser CORS or server settings.
- Forecast-based **total nesting activity** is the main metric. Species are only used internally to build totals.
- Shows regional allocation proxies **explicitly labeled as proxies**, not precise beach forecasts. Unmatched FWC segments remain gray.
- Adds **Boca Raton and Canaveral leatherback annual counts**, extracted from the official government tables. Existing Volusia loggerhead/green histories are retained. No invented TimesFM results.
- Provides date-based general Florida season urgency, editable weights, and a volunteer-hour knapsack optimizer. Urgency is common across all regions, not a beach-specific prediction.

## Quick start — your existing Windows setup
Extract this ZIP in Downloads next to `turtleguard_timesfm`. Open the new folder in VS Code, then run:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_dashboard_data.py
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_beach_priorities.py
..\turtleguard_timesfm\.venv\Scripts\python.exe -m http.server 8000 -d site
```

Open http://localhost:8000. **Before generating the newly added leatherback forecasts**, the dashboard will use five-year historical averages as explicitly labeled fallbacks for those series.

## Generate NEW TimesFM 3 predictions for the expanded dataset

From the prototype folder:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\forecast_multi.py data\nesting_counts.csv
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_dashboard_data.py
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_beach_priorities.py
```

Refresh the browser. The forecast script runs on CPU by default, produces `forecast_results.json` plus `backtest_results.csv`, and can take time due to historical backtests. **The ZIP has not been run through TimesFM in this container, so the new series' values must be generated on your laptop.**

## Critical science / mapping caveats
1. FWC ArcGIS nesting geometry is beach polyline geometry, *not filled sand polygons*. We style full surveyed coastline lines.
2. Region-level nest forecasts from Boca Raton, Volusia, and Canaveral should not be presented as nest counts on specific FWC beach segments. The colored mapping is a regional *proxy* with names/county matching, not a confirmed spatial correspondence.
3. Raw forecast totals from different surveyed extents are not directly comparable. Need surveyed beach km and survey effort for real density scores.
4. `historical_active_year_fraction` is the fraction of annual records with at least one nest, **not** the probability of a turtle nesting at a beach.
5. Shared calendar urgency does not differentiate within-region timing. To prioritize *how soon* by beach, obtain weekly/daily survey histories.
6. Without debris observations this is preventive inspection priority, **not debris cleanup urgency**. Do not advise removing equipment or interacting with nests without local permitting guidance.
7. FWC feature service may return a browser CORS error; if so download GeoJSON locally and serve it from `site/` or route requests through your own backend.

## Data source attribution
- Boca Raton: https://www.myboca.us/2140/Sea-Turtle-Nesting-Totals
- Volusia: https://www.volusia.org/services/growth-and-resource-management/environmental-management/sustainability-and-resilience/sea-turtles/Volusia-nesting-summary.stml
- Canaveral NPS: https://www.nps.gov/cana/learn/nature/sea-turtle-monitoring.htm
- FWC beach-segment geometry: https://gis.myfwc.com/hosting/rest/services/Projects_FWC/Sea_Turtle_Nest_Density_Florida/MapServer/2
