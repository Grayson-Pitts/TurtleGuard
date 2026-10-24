"""TimesFM 3 direct 2027 two-step forecasts from verified 2021–2025 FWC county totals.
Separate county output to prevent double-counting smaller monitoring areas.
Five data points is a *very* short context: these outputs are experimental estimates.
"""
import argparse,csv,json,math,sys,statistics
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
YEAR=2027
SPECIES=('loggerhead','green','leatherback')


def load_rows(filename):
    source=defaultdict(dict)
    with open(filename,newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        for key in ('location','year','species','nests','status','geographic_scope'):
            if key not in (reader.fieldnames or []):raise ValueError('FWC CSV missing '+key)
        for r in reader:
            if r['geographic_scope'].lower()!='county':raise ValueError('Not county-level data: '+str(r))
            county=r['location'].strip(); species=r['species'].lower().strip(); year=int(r['year'])
            if species not in SPECIES:continue
            key=(county,species)
            if year in source[key]:raise ValueError('Duplicate county observation: '+str((key,year)))
            valid=r['status'].lower().strip()=='observed' and r['nests'].strip()!=''
            val=float(r['nests']) if valid else None
            if val is not None and (not math.isfinite(val) or val<0):raise ValueError('Bad counts: '+str(r))
            source[key][year]=val
    counties=sorted({c for c,_ in source})
    series={}; excluded={}
    for county in counties:
        by_species={}
        for sp in SPECIES:
            vals=source.get((county,sp),{})
            if list(sorted(vals))!=[2021,2022,2023,2024,2025] or any(vals[y] is None for y in range(2021,2026)):
                excluded[county]='incomplete/missing county annual observations; not zero-filled'
                break
            by_species[sp]=[vals[y] for y in range(2021,2026)]
        if county not in excluded:series[county]=by_species
    return series,excluded


def make_predictions(series,model=None,batch_size=6):
    tasks=[(county,sp,vals) for county in sorted(series) for sp,vals in series[county].items()]
    if model is None:
        from timesfm3 import TimesFM3Evaluator,ModelConfig
        print('Loading TimesFM 3 for FWC county estimates (2027; 2-year horizon) ...',flush=True)
        model=TimesFM3Evaluator(ModelConfig(checkpoint_path='google/timesfm-3.0-pytorch',device='cpu',per_core_batch_size=min(batch_size,6)))
    import numpy as np
    output=[]
    for i in range(0,len(tasks),batch_size):
        batch=tasks[i:i+batch_size]
        inp=[np.asarray(t[2],dtype=np.float32) for t in batch]
        results=list(model.predict_batch(inp,horizon=2,return_quantiles=False,use_symmetric_averaging=False))
        if len(results)!=len(batch):raise RuntimeError('Unexpected TimesFM output size')
        for (county,sp,history),result in zip(batch,results):
            val=float(result.forecast[1])
            if not math.isfinite(val):raise RuntimeError(f'Invalid forecast for {county}/{sp}')
            output.append({'county':county,'species':sp,'target_year':YEAR,
                           'last_observed_year':2025,'forecast_horizon_years':2,
                           'forecast_nests':round(max(0,val),2),
                           'five_year_mean_reference':round(statistics.mean(history),2),
                           'model':'google/timesfm-3.0-pytorch',
                           'forecast_type':'TimesFM county-level short-history experimental estimate',
                           'history_years':5})
        print(f'  County TimesFM inference {min(i+len(batch),len(tasks))}/{len(tasks)}',flush=True)
    return output


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch-size',type=int,default=6)
    args=ap.parse_args()
    if args.batch_size<=0:raise ValueError('batch-size must be positive')
    src=ROOT/'data'/'FWC_county_nesting_2021_2025.csv'
    series,excluded=load_rows(src)
    print(f'{len(series)} complete counties eligible; {len(excluded)} excluded for missing/partial data: {excluded}',flush=True)
    predictions=make_predictions(series,batch_size=args.batch_size)
    payload={'target_year':YEAR,'source':'FWC county nesting totals 2021-2025',
             'model':'google/timesfm-3.0-pytorch','forecast_type':'county_estimate',
             'method_note':'All predictions from TimesFM 3; only five input years; not validated beach-level forecasts',
             'excluded_counties':excluded,'forecasts':predictions,
             'generated_utc':datetime.now(timezone.utc).isoformat()}
    path=ROOT/'county_forecasts_2027.json';temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,indent=2),encoding='utf8');temp.replace(path)
    print(f'Saved {len(predictions)} TimesFM county/species 2027 estimates to {path}')

if __name__=='__main__':main()
