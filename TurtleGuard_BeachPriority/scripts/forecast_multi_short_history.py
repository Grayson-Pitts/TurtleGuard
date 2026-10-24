"""Annual nest-count forecasts by location & species, with historical rolling tests.

Usage: .\.venv\Scripts\python.exe forecast_multi.py nesting_counts.csv
Outputs: forecast_results.json and backtest_results.csv
"""
import csv, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from timesfm3 import TimesFM3Evaluator, ModelConfig

if len(sys.argv) != 2:
    raise SystemExit('Usage: python forecast_multi.py nesting_counts.csv')
series = defaultdict(dict)
with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    required = {'location','year','species','nests'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise SystemExit('Required columns: location,year,species,nests')
    for row in reader:
        key = (row['location'].strip(), row['species'].strip().lower())
        year, count = int(row['year']), float(row['nests'])
        if year in series[key]:
            raise SystemExit(f'Duplicate year {year} for {key}')
        if count < 0:
            raise SystemExit(f'Negative nest count in {key}, {year}')
        series[key][year] = count

print('Loading TimesFM 3 on CPU...', flush=True)
forecaster = TimesFM3Evaluator(ModelConfig(
    checkpoint_path='google/timesfm-3.0-pytorch',
    per_core_batch_size=1, device='cpu'
))

def predict(history):
    x = np.asarray(history, dtype=np.float32)
    result = next(iter(forecaster.predict_batch(
        [x], horizon=1, return_quantiles=False, use_symmetric_averaging=False)))
    return max(0.0, float(result.forecast[0]))

forecasts, tests = [], []
for (location, species), year_counts in sorted(series.items()):
    years = sorted(year_counts)
    if len(years) < 8 or years != list(range(years[0], years[-1]+1)):
        print(f'SKIP {location} / {species}: need >=8 consecutive annual observations')
        continue
    history = [year_counts[y] for y in years]
    future = predict(history)
    # Evaluate on at most the last eight observed years; never use future values
    # to calculate a historical baseline.
    for idx in range(max(6, len(history)-3),len(history)):
        actual = history[idx]
        model_pred = predict(history[:idx])
        five_year_mean = float(np.mean(history[idx-5:idx]))
        two_year_seasonal = float(history[idx-2])
        tests.append({
            'location':location,'species':species,'year':years[idx],
            'actual':round(actual,2),'timesfm':round(model_pred,2),
            'mean_5yr':round(five_year_mean,2),
            'same_parity_2yr':round(two_year_seasonal,2),
            'timesfm_absolute_error':round(abs(actual-model_pred),2),
            'mean_5yr_absolute_error':round(abs(actual-five_year_mean),2),
            'same_parity_2yr_absolute_error':round(abs(actual-two_year_seasonal),2)
        })
    forecasts.append({
        'location':location,'species':species,
        'training_years':f'{years[0]}–{years[-1]}',
        'last_observed_year': years[-1],
        'forecast_year':years[-1]+1,
        'forecast_nests':round(future,2),
        'model':'google/timesfm-3.0-pytorch',
        'source':{'Boca Raton':'City of Boca Raton annual nesting totals','Volusia County':'Volusia County nesting summary','Canaveral National Seashore':'NPS Canaveral Sea Turtle Monitoring'}.get(location,'Mote Marine Laboratory annual beach totals (historical)' if location in {'Longboat Key','Lido Key','Siesta Key','Casey Key','Venice'} else 'User-supplied annual totals')
    })
    print(f'{location:16} {species:11} {years[-1]+1}: {future:.1f} nests')

Path('forecast_results.json').write_text(json.dumps(forecasts,indent=2),encoding='utf-8')
if tests:
    with open('backtest_results.csv','w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(tests[0].keys()))
        writer.writeheader();writer.writerows(tests)
    print('\nHistorical mean absolute errors (MAE; smaller is better):')
    for key in sorted({(r['location'],r['species']) for r in tests}):
        subset=[r for r in tests if (r['location'],r['species'])==key]
        def mae(col):return sum(r[col] for r in subset)/len(subset)
        print(f'{key[0]} / {key[1]}: TimesFM {mae("timesfm_absolute_error"):.1f} | '
              f'5-year mean {mae("mean_5yr_absolute_error"):.1f} | '
              f'2-year seasonal {mae("same_parity_2yr_absolute_error"):.1f}')
print('\nSaved forecast_results.json and backtest_results.csv')
