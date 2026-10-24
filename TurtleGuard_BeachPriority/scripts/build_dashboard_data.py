"""Build app data from historical counts and optional TimesFM forecast/backtest outputs."""
import csv,json,statistics,datetime
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HIST=ROOT/'data'/'nesting_counts.csv'
FORE=ROOT/'forecast_results.json'; BACK=ROOT/'backtest_results.csv'
series=defaultdict(dict)
with HIST.open(newline='',encoding='utf-8') as f:
 for r in csv.DictReader(f):series[(r['location'],r['species'])][int(r['year'])]=float(r['nests'])
forecast={}
if FORE.exists():
 for r in json.loads(FORE.read_text(encoding='utf-8')): forecast[(r['location'],r['species'])]=r
back=defaultdict(list)
if BACK.exists():
 with BACK.open(newline='',encoding='utf-8') as f:
  for r in csv.DictReader(f):back[(r['location'],r['species'])].append(r)
places={
 'Boca Raton':{'lat':26.35,'lng':-80.071,'scope':'City monitoring area; representative map point','url':'https://www.myboca.us/2140/Sea-Turtle-Nesting-Totals'},
 'Volusia County':{'lat':29.21,'lng':-81.01,'scope':'County monitoring area; representative map point','url':'https://www.volusia.org/services/growth-and-resource-management/environmental-management/sustainability-and-resilience/sea-turtles/Volusia-nesting-summary.stml'},
 'Canaveral National Seashore':{'lat':28.78,'lng':-80.77,'scope':'National seashore monitoring area; representative map point','url':'https://www.nps.gov/cana/learn/nature/sea-turtle-monitoring.htm'}
}
locations=[]
for loc in sorted({k[0] for k in series}):
 specs=[]
 for (l,sp),ys in sorted(series.items()):
  if l!=loc:continue
  years=sorted(ys); hist=[{'year':y,'nests':ys[y]} for y in years]
  # Distinct holdout selection: 2018-2021 for method selection, 2022-2024 final honest test, when available
  rows=back.get((loc,sp),[])
  fit=[r for r in rows if int(r['year'])<=2021]
  evaluation=[r for r in rows if int(r['year'])>2021]
  fields={'timesfm':'timesfm_absolute_error','five_year':'mean_5yr_absolute_error','two_year':'same_parity_2yr_absolute_error'}
  def stats(records):return {key:round(statistics.mean(float(r[field]) for r in records),1) for key,field in fields.items()} if records else None
  method_mae=stats(fit); eval_mae=stats(evaluation)
  # fallback TimesFM when not enough selection data; display selection as experimental
  selected=min(method_mae,key=method_mae.get) if method_mae else 'timesfm'
  last_year=years[-1]; recent=[ys[y] for y in years[-5:]]
  pred=forecast.get((loc,sp))
  preds={'five_year':statistics.mean(recent),'two_year':ys[years[-2]]}
  if pred:preds['timesfm']=float(pred['forecast_nests'])
  else:selected='five_year' # no model result yet
  specs.append({'species':sp,'history':hist,'last_year':last_year,'forecast_year':last_year+1,
    'forecasts':{k:round(v,1) for k,v in preds.items()},'selected_method':selected,
    'selected_forecast':round(preds[selected],1),'model_available':bool(pred),
    'selection_mae':method_mae,'evaluation_mae':eval_mae,
    'backtest_years':[int(r['year']) for r in rows]})
 locations.append({'name':loc,**places.get(loc,{}),'species':specs})
# Regional workload assumptions are intentionally editable, not measured. No debris claims.
config={'Boca Raton':{'hours':3},'Volusia County':{'hours':5},'Canaveral National Seashore':{'hours':4}}
for l in locations:l['illustrative_inspection_hours']=config.get(l['name'],{'hours':3})['hours']
output={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'locations':locations,
 'notes':'Experimental regional nest forecasts; no beach-level probabilities. Beach segment mapping is a planning proxy, not a direct observation.'}
out=ROOT/'site'/'data.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(output,indent=2),encoding='utf-8')
print('Built',out,'for',len(locations),'regions /',sum(len(l['species']) for l in locations),'series')
