"""Join source annual observations with exclusively 2027 forecast results."""
import csv,json,datetime
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=2027

raw=defaultdict(list)
with (ROOT/'data'/'nesting_counts.csv').open(newline='',encoding='utf8') as f:
    for r in csv.DictReader(f):
        raw[(r['location'],r['species'])].append({'year':int(r['year']),'nests':float(r['nests'])})
forecasts=json.loads((ROOT/'forecast_results.json').read_text(encoding='utf8'))
keys={(r['location'],r['species']) for r in forecasts}
if keys!=set(raw):
    raise RuntimeError('Forecast series differ from historical series; run scripts/forecast_2027.py first.')
if any(int(r.get('target_year',r.get('forecast_year',0)))!=TARGET for r in forecasts):
    raise RuntimeError('Mixed/outdated forecast years. Run scripts/forecast_2027.py first.')
groups=defaultdict(list)
for r in forecasts:
    obs=sorted(raw[(r['location'],r['species'])],key=lambda item:item['year'])
    groups[r['location']].append({
        'species':r['species'],'history':obs,
        'last_year':r['last_observed_year'],
        'forecast_year':TARGET,
        'forecast_horizon_years':r['forecast_horizon_years'],
        'forecasts':r['candidates'],'selected_forecast':r['forecast_nests'],
        'selected_method':r['selected_method'],'model_available':True,
        'timesfm_forecast':r['timesfm_forecast_nests'],
        'selection_mae':r['selection_mae'],'evaluation_mae':r.get('holdout_mae'),
        'backtest_years':list(range(r['last_observed_year']-r['selection_backtests']+1,r['last_observed_year']+1)),
        'confidence_note':r['confidence_note'],
    })
locations=[{'name':loc,'species':specs} for loc,specs in sorted(groups.items())]
out={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'forecast_year':TARGET,'locations':locations,
     'notes':'2027 horizon-matched TimesFM experiments and baselines; annual counts are not distinct turtles or site-specific nest probabilities.'}
path=ROOT/'site'/'data.json'
path.write_text(json.dumps(out,indent=2),encoding='utf8')
print(f'Built {path}: {len(locations)} regions / {len(forecasts)} series for {TARGET}')
