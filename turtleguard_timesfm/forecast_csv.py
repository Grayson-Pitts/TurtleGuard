"""Forecast one year of annual nest counts from a CSV with year, species, nests.
Example: python forecast_csv.py boca_counts.csv
Separate species are evaluated independently. One-step holdout is reported.
"""
import csv
import json
import sys
import numpy as np
from timesfm3 import TimesFM3Evaluator, ModelConfig

if len(sys.argv) != 2:
    raise SystemExit('Usage: python forecast_csv.py data.csv')

with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
needed = {'year', 'species', 'nests'}
if not rows or not needed.issubset(rows[0].keys()):
    raise SystemExit('CSV columns required: year,species,nests')

groups = {}
for row in rows:
    species = row['species'].strip()
    year = int(row['year'])
    nests = float(row['nests'])
    groups.setdefault(species, {})[year] = nests

print('Loading TimesFM 3 on CPU (safe starting point for 6 GB GPU)...', flush=True)
forecaster = TimesFM3Evaluator(ModelConfig(checkpoint_path='google/timesfm-3.0-pytorch', per_core_batch_size=1, device='cpu'))
results = []
for species, by_year in sorted(groups.items()):
    years = sorted(by_year)
    if len(years) < 12 or years != list(range(years[0], years[-1] + 1)):
        print(f'Skipping {species}: needs >=12 consecutive annual observations')
        continue
    values = np.array([by_year[y] for y in years], dtype=np.float32)
    # Historical evaluation without future-data leakage
    holdout = next(iter(forecaster.predict_batch([values[:-1]], horizon=1, return_quantiles=False, use_symmetric_averaging=False)))
    forecast = next(iter(forecaster.predict_batch([values], horizon=1, return_quantiles=True, use_symmetric_averaging=False)))
    pred = max(0, float(forecast.forecast[0]))
    baseline = float(np.mean(values[-5:]))
    entry = {
        'species': species,
        'last_observed_year': years[-1],
        'forecast_year': years[-1] + 1,
        'forecast_nests': round(pred, 2),
        'last_year_holdout_actual': round(float(values[-1]), 2),
        'last_year_holdout_prediction': round(max(0, float(holdout.forecast[0])), 2),
        'five_year_mean_baseline': round(baseline, 2),
        'model': 'google/timesfm-3.0-pytorch'
    }
    results.append(entry)
    print(json.dumps(entry, indent=2))
with open('nesting_forecasts.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Wrote nesting_forecasts.json')
