# TurtleGuard — Installation & Setup

These instructions assume Python 3.11 and Git are already installed.

## 1. Project Structure

After cloning the repository, the project should have the following structure:

```text
TurtleGuard/
├── README.md
├── .gitignore
├── turtleguard_timesfm/
│   ├── smoke_test.py
│   ├── forecast_csv.py
│   └── ...
└── TurtleGuard_BeachPriority/
    ├── data/
    ├── scripts/
    └── site/
```

All commands below should be run in a PowerShell terminal from the main `TurtleGuard` directory unless otherwise specified.

## 2. Create a Virtual Environment

```powershell
python -m venv turtleguard_timesfm\.venv
```

The virtual environment stores the project's Python packages locally and does not need to be uploaded to GitHub.

## 3. Install TimesFM 3

Upgrade pip:

```powershell
.\turtleguard_timesfm\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Install TimesFM and its PyTorch dependencies:

```powershell
.\turtleguard_timesfm\.venv\Scripts\python.exe -m pip install "timesfm[torch]"
```

Verify the installation:

```powershell
.\turtleguard_timesfm\.venv\Scripts\python.exe -c "from timesfm3 import TimesFM3Evaluator; print('TimesFM 3 available')"
```

## 4. Test the Model

Run:

```powershell
.\turtleguard_timesfm\.venv\Scripts\python.exe turtleguard_timesfm\smoke_test.py
```

The first run automatically downloads the pretrained TimesFM 3 model weights (approximately 1.3 GB).

A successful test should display:

```text
Success: one-step demonstration forecast: [...]
```

## 5. Generate Nesting Forecasts

Navigate to the main application directory:

```powershell
cd TurtleGuard_BeachPriority
```

Run the forecasting script:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\forecast_multi.py data\nesting_counts.csv
```

This generates nesting forecasts for each location and species using the historical data.

The results are saved in `forecast_results.json`, with historical accuracy comparisons in `backtest_results.csv`.

## 6. Generate Website Data

Run these commands:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_dashboard_data.py
```

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\build_beach_priorities.py
```

These scripts process the forecasts and calculate the nesting-priority scores displayed on the map.

## 7. Launch TurtleGuard

Start the local server:

```powershell
..\turtleguard_timesfm\.venv\Scripts\python.exe -m http.server 8000 -d site
```

Open the website at:

**http://localhost:8000**

Keep the terminal running while using the website. Press `Ctrl + C` to stop the server.

## 8. Updating Forecasts

When new nesting data becomes available:

1. Update `data/nesting_counts.csv`.
2. Rerun `scripts/forecast_multi.py`.
3. Rerun `scripts/build_dashboard_data.py`.
4. Rerun `scripts/build_beach_priorities.py`.
5. Refresh the website.

## 9. Adding New Nesting Data

Add new observations to `data/nesting_counts.csv` using this format:

```csv
location,year,species,nests
Example Beach,2021,loggerhead,320
Example Beach,2022,loggerhead,350
Example Beach,2023,loggerhead,340
```

These are example values, not actual observations.

The forecasting script requires at least 12 consecutive annual observations per location/species combination.

Once sufficient observations are added, the model can generate additional forecasts for those locations.

