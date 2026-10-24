# TurtleGuard 2027 forecast update

## What has changed

- Every annual series targets **2027**. Boca Raton and the five Mote areas (latest data 2025) need a **2-year-ahead** TimesFM forecast; Canaveral and Volusia (latest data 2024) need a **3-year-ahead** forecast.
- Historical tests use that same horizon (not 1-year forecasts masquerading as 2- or 3-year validation).
- TimesFM is compared against three explicitly defined baselines: five-year mean, five-year median, and mean of the last three observations with matching year parity. A 35% TimesFM / 65% parity-mean blend is also tested.
- The selected method is evaluated using rolling-origin historical years. Where sufficient test years exist, the final two observed targets are reserved for holdout evaluation. For nine-year Mote histories, the historical evidence is too short for robust selection; the conservative parity baseline is chosen by default, but the real TimesFM 2027 forecast is always computed and stored separately.
- The map displays a 0–100 **relative nesting inspection-priority index** computed from forecast nest counts **per mile**, not from raw regional total nest counts. This is not a calibrated probability or an estimate of debris hazards.
- The website refuses to display out-of-date forecast JSON.

## Installation in the existing repository

Back up existing `scripts/` and `site/index.html` first. Copy the package's contents into `TurtleGuard_BeachPriority/`, retaining existing historical CSVs and the website's `site/beach_areas.geojson` file. The patch includes an unchanged copy of the existing approximate-beach GeoJSON only for convenience.

From `TurtleGuard_BeachPriority` in PowerShell:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\forecast_2027.py
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_dashboard_data.py
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_beach_priorities.py
..\turtleguard_timesfm\.venv\Scripts\python.exe -m http.server 8000 -d site
```

Or one command to import supported weekly PDFs and rebuild everything:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\run_all.py --skip-weekly
```

When you only change site styling or the beach-length lookup, **and already have actual 2027 `forecast_results.json`**, rebuild without expensive inference:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\run_all.py --skip-forecast --no-import
```

After the server starts, open http://localhost:8000 and press Ctrl+F5 to hard refresh.

No downloaded model weights or `.venv` files are included.

## Inputs and outputs

Input: `data/nesting_counts.csv` (annual, species or `all`, and unmodified). Mote weekly observations stay in their own file; they are **not mixed into annual forecasts**.

Input: `data/beach_lengths.csv` (published/beach-length source and data-quality flag). Do not use the GeoJSON sketched-line length as a substitute for the length of surveyed coastline.

Output files are generated only when all forecasts succeed:
- `forecast_results.json`: true TimesFM prediction, method candidates, and selected forecast for **2027**.
- `backtest_results.csv`: horizon-aligned historical predictions, training origin, errors, and method-selection vs holdout phase.
- `site/data.json`: history and method details.
- `site/priorities.json`: total selected nests, beach length, projected nests/mile, and a relative score 10–90.

## Data provenance and limitations

1. **Boca Raton**: City sea-turtle program says it monitors **five miles**. https://www.myboca.us/2139/Nesting
2. **Canaveral National Seashore**: NPS reports **24 miles of beach**; extent is a park-wide proxy rather than precisely proven overlap with the nesting survey boundaries. https://www.nps.gov/cana/planyourvisit/basicinfo.htm
3. **Mote sites**: published coastal monitoring study Table 1: Longboat Key 17.1 km, Lido 5.3 km, North Siesta 5.2 km, South Siesta 4.1 km, Casey 11.8 km, Venice 7.4 km. https://pmc.ncbi.nlm.nih.gov/articles/PMC10567714/
4. **Volusia**: FWC's **79.8 km** surveyed beach length is a **county-level proxy**. The long-term source of the approximately 900 nest counts is the county-managed beach program, **not** the all-county FWC survey. The denominator may not match. Therefore Volusia's priority is low-confidence and should not be used operationally without matching the surveyed boundary. https://myfwc.com/research/wildlife/sea-turtles/nesting/statewide/
5. **Canaveral source discrepancy**: NPS historical table lists total 5,140 for 2013 but its listed species counts sum to 7,933; it lists 7,888 for 2020 but the displayed species sum is much lower. We retain reported **species-specific** values as provided and do not invent corrections; this reduces confidence in the Canaveral history. NPS historical table: https://www.nps.gov/cana/learn/nature/sea-turtle-monitoring.htm
6. As of October 24, 2026, the 2026 Mote season is not finalized; Mote says it will post the final total after October 31. We don't append unfinished 2026 observations to this annual dataset. https://mote.org/research/program/sea-turtle-conservation-research/nesting-numbers/
7. The previous assistant's assertion that NPS reported **1,277 total Canaveral nests in 2025** could not be substantiated by the current NPS historical table. It should **not** be used to evaluate model accuracy. The NPS page currently shows a 2026 running total while its historical annual table ends at 2024.

**Important:** The forecast model cannot estimate the number of individual turtles from nest counts alone, nor can the output prove cleaning effectiveness. The best forecasting method may differ by region/species and true future accuracy cannot be known until observed 2027 results exist.

## Developer tests (no GPU/model weights required)

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use a deterministic `FakeForecaster` *only in memory* to verify algorithms and data joins. They do **not** represent model forecasts and aren't shipped as website data.
