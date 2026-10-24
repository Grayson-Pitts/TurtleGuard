"""Validate the restored forecasting inputs before rebuilding the website."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with (root/'data/nesting_counts.csv').open(encoding='utf-8',newline='') as f:
    rows=list(csv.DictReader(f))
locations={r['location'] for r in rows}
forecasts=json.loads((root/'forecast_results.json').read_text(encoding='utf-8'))
forecast_locations={r['location'] for r in forecasts}
print(f"Historical data: {len(rows)} observations across {len(locations)} regions")
print(f"Forecast outputs: {len(forecasts)} series across {len(forecast_locations)} regions")
missing=locations-forecast_locations
if missing:
    raise SystemExit('ERROR: Missing forecasts for: '+', '.join(sorted(missing)))
if len(locations)<8:
    raise SystemExit('ERROR: Expected at least 8 regions. Refusing to publish a reduced map.')
print('Data checks passed; rebuild site/data.json and site/priorities.json in that order.')
