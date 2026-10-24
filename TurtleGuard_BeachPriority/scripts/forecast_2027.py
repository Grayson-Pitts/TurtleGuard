"""TurtleGuard: TimesFM-only 2027 forecasts with horizon-matched diagnostics.

Run in TurtleGuard_BeachPriority from your venv:
  ..\\turtleguard_timesfm\\.venv\\Scripts\\python.exe scripts\\forecast_2027.py

Notes: forecasts are nest *counts*, never numbers of individual turtles.
The five Mote beach areas include a provisional 2026 Week 42 observation,
which is not final season data. Use --exclude-provisional-2026 to omit it.
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_YEAR = 2027
MIN_HISTORY = 6
MAX_BACKTESTS = 9


MOTE_AREAS = {'Longboat Key','Lido Key','Siesta Key','Casey Key','Venice'}

def read_series(filename, exclude_provisional_2026=False):
    grouped = defaultdict(dict)
    with Path(filename).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not {'location', 'species', 'year', 'nests'}.issubset(reader.fieldnames or []):
            raise ValueError('CSV must contain location,year,species,nests')
        for row in reader:
            key = (row['location'].strip(), row['species'].strip().lower())
            yr = int(row['year'])
            if exclude_provisional_2026 and yr == 2026 and key[0] in MOTE_AREAS:
                continue
            val = float(row['nests'])
            if not math.isfinite(val) or val < 0:
                raise ValueError(f'Non-finite/negative nests: {key}, {yr}')
            if yr in grouped[key]:
                raise ValueError(f'Duplicate record for {key}, year {yr}')
            grouped[key][yr] = val
    result = {}
    for key, observations in sorted(grouped.items()):
        years = sorted(observations)
        # Missing year is not the same as zero nests.
        if years != list(range(years[0], years[-1] + 1)):
            raise ValueError(f'Nonconsecutive annual history for {key}; missing years must be resolved, not zero-filled.')
        if len(years) < MIN_HISTORY:
            print(f'SKIP {key}: fewer than {MIN_HISTORY} annual observations')
            continue
        if years[-1] >= TARGET_YEAR:
            raise ValueError(f'{key} already contains {TARGET_YEAR} or later; change target explicitly.')
        result[key] = (years, [observations[y] for y in years])
    if not result:
        raise ValueError('No valid annual series')
    return result


def baseline(history, years, target_year):
    if len(history) < 5:
        raise ValueError('Need >=5 years for baselines')
    same_parity = [v for y, v in zip(years, history) if y % 2 == target_year % 2][-3:]
    return {
        'five_year_mean': float(statistics.mean(history[-5:])),
        'recent_median': float(statistics.median(history[-5:])),
        'parity_mean': float(statistics.mean(same_parity)) if same_parity else float(statistics.mean(history[-5:])),
    }


def build_tasks(series):
    tasks = []
    for (loc, sp), (years, values) in series.items():
        h = TARGET_YEAR - years[-1]
        if h < 1 or h > 5:
            raise ValueError(f'Unsupported horizon for {loc}/{sp}: {h} years. Add recent annual data.')
        tasks.append(dict(key=(loc, sp), years=years, values=values, training_end=years[-1],
                          target_year=TARGET_YEAR, horizon=h, kind='future', context=values,
                          test_actual=None))
        # Historical origin-based backtest for the *same horizon* as the 2027 task.
        # This prevents accidentally evaluating 1-year forecasts for 3-year planning.
        for target_idx in range(max(0, len(values) - MAX_BACKTESTS), len(values)):
            origin_idx = target_idx - h
            if origin_idx < MIN_HISTORY - 1:
                continue
            context = values[:origin_idx + 1]
            tasks.append(dict(key=(loc, sp), years=years[:origin_idx+1], values=context,
                              training_end=years[origin_idx], target_year=years[target_idx],
                              horizon=h, kind='backtest', context=context, test_actual=values[target_idx]))
    return tasks


def run_model_forecasts(tasks, batch_size=6, forecaster=None):
    """Batch examples with fixed horizon 1..5 to reduce CPU forward passes."""
    if forecaster is None:
        from timesfm3 import TimesFM3Evaluator, ModelConfig
        print('Loading TimesFM 3 on CPU (model cache is reused)...', flush=True)
        forecaster = TimesFM3Evaluator(ModelConfig(
            checkpoint_path='google/timesfm-3.0-pytorch',
            device='cpu', per_core_batch_size=min(6, batch_size)))
    import numpy as np
    # Single horizon equal to the longest horizon requested, e.g. 3.
    # Each result selects its own (horizon - 1) index of the direct multi-step output.
    H = max(t['horizon'] for t in tasks)
    done = 0
    for start in range(0, len(tasks), batch_size):
        group = tasks[start:start+batch_size]
        arrays = [np.asarray(t['context'], dtype=np.float32) for t in group]
        results = list(forecaster.predict_batch(
            arrays, horizon=H, return_quantiles=False,
            use_symmetric_averaging=False))
        if len(results) != len(group):
            raise RuntimeError('TimesFM did not return one forecast per requested series')
        for t, r in zip(group, results):
            raw = float(r.forecast[t['horizon']-1])
            if not math.isfinite(raw):
                raise RuntimeError(f'TimesFM produced invalid output for {t["key"]}')
            # Nonnegative counts, no artificial upper bound that could hide model errors.
            t['timesfm'] = max(0.0, raw)
        done += len(group)
        print(f'  Inference {done}/{len(tasks)} series/origins', flush=True)
    return tasks


def select_and_report(tasks):
    by_key = defaultdict(list)
    for t in tasks:
        by_key[t['key']].append(t)

    predictions, backtests = [], []
    for (loc, sp), group in sorted(by_key.items()):
        future = next(t for t in group if t['kind'] == 'future')
        hist_tests = sorted((t for t in group if t['kind'] == 'backtest'), key=lambda t:t['target_year'])
        method_names = ['timesfm', 'five_year_mean', 'recent_median', 'parity_mean', 'timesfm_parity_blend']
        for t in group:
            base = baseline(t['context'], t['years'], t['target_year'])
            t['candidates'] = {**base, 'timesfm': t['timesfm'],
                               'timesfm_parity_blend': .35*t['timesfm'] + .65*base['parity_mean']}
        # Explicit final holdout where sample count permits; never include it in selecting method.
        holdout_count = 2 if len(hist_tests) >= 6 else 0
        choose = hist_tests[:-holdout_count] if holdout_count else hist_tests
        assess = hist_tests[-holdout_count:] if holdout_count else []
        ma = {m: statistics.mean(abs(t['candidates'][m] - t['test_actual']) for t in choose)
              for m in method_names} if choose else {}
        # Product policy: TimesFM is always the displayed forecast.
        # Historical methods are retained ONLY for honest comparative evaluation.
        selected = 'timesfm'
        candidates = {k: round(max(0.,v),2) for k,v in future['candidates'].items()}
        pred = candidates[selected]
        holdout_mae = {m:round(statistics.mean(abs(t['candidates'][m]-t['test_actual']) for t in assess),2)
                       for m in method_names} if assess else None
        years = future['years']
        output = {
            'location':loc,'species':sp,'target_year':TARGET_YEAR,
            'forecast_year':TARGET_YEAR,'last_observed_year':years[-1],
            'forecast_horizon_years':future['horizon'],
            'training_years':f'{years[0]}-{years[-1]}',
            'forecast_nests':pred,'selected_forecast':pred,'selected_method':selected,
            'timesfm_forecast_nests':candidates['timesfm'],
            'candidates':candidates,'selection_backtests':len(choose),
            'selection_mae':{m:round(v,2) for m,v in ma.items()},
            'holdout_backtests':len(assess),'holdout_mae':holdout_mae,
            'confidence_note':('2026 Mote nesting observation is provisional (Week 42); final annual totals may differ. ' if (loc in MOTE_AREAS and years[-1]==2026) else '') +
                   ('Short historical series; limited backtest evidence' if len(choose)<3 else
                    'Horizon-matched backtesting; observational ecological uncertainty remains'),
            'provisional_input_years':[2026] if loc in MOTE_AREAS and years[-1]==2026 else [],
            'prediction_role':'TimesFM-only; statistical baselines are evaluation comparators',
            'model':'google/timesfm-3.0-pytorch',
        }
        predictions.append(output)
        for t in hist_tests:
            phase = 'independent_holdout' if t in assess else 'method_selection'
            record = {'location':loc,'species':sp,'target_year':t['target_year'],
                      'forecast_horizon_years':t['horizon'],'origin_year':t['training_end'],
                      'phase':phase,'actual_nests':t['test_actual']}
            for m in method_names:
                record[m] = round(t['candidates'][m],2)
                record[m+'_abs_error'] = round(abs(t['candidates'][m]-t['test_actual']),2)
            backtests.append(record)
        print(f'{loc:<30} {sp:<12} -> 2027 {pred:>9,.1f}  '
              f'[{selected}; TimesFM {candidates["timesfm"]:,.1f}; horizon {future["horizon"]}]')
    return predictions, backtests


def persist(preds, tests):
    import os
    # Write only after all inference/validation succeeds. Never mix 2025/2026 and 2027 files.
    path = ROOT/'forecast_results.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(preds,indent=2),encoding='utf8')
    os.replace(temp,path)
    path = ROOT/'backtest_results.csv'; temp = path.with_suffix('.tmp')
    with temp.open('w',newline='',encoding='utf8') as file:
        if tests:
            w=csv.DictWriter(file,fieldnames=list(tests[0]));w.writeheader();w.writerows(tests)
    os.replace(temp,path)
    print('Saved 2027 forecast_results.json and horizon-matched backtest_results.csv')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='data/nesting_counts.csv')
    parser.add_argument('--batch-size',type=int,default=6)
    parser.add_argument('--exclude-provisional-2026',action='store_true',
                        help='Ignore 2026 Mote counts from unfinished nesting season')
    args=parser.parse_args()
    series=read_series(ROOT/args.input,exclude_provisional_2026=args.exclude_provisional_2026)
    print(f'Found {len(series)} location/species series; generating TimesFM-only 2027 forecasts')
    if not args.exclude_provisional_2026: print('WARNING: Mote 2026 observations are provisional Week 42 counts, not final season totals.')
    tasks=run_model_forecasts(build_tasks(series),batch_size=args.batch_size)
    preds,tests=select_and_report(tasks)
    if len({r['location'] for r in preds}) != len({k[0] for k in series}):
        raise RuntimeError('Not all historical regions received a forecast')
    persist(preds,tests)

if __name__=='__main__':main()
