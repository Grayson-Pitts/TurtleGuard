"""TurtleGuard mixed-frequency TimesFM example.
Run from TurtleGuard_BeachPriority with existing .venv Python:
  ..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\forecast_by_frequency.py --frequency weekly --input data/mote_weekly_2007_2008.csv
  ..\turtleguard_timesfm\.venv\Scripts\python.exe scripts\forecast_by_frequency.py --frequency annual --input data/nesting_counts.csv
Does NOT convert weekly observations into whole-year forecasts.
"""
import argparse, csv, json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import numpy as np
from timesfm3 import TimesFM3Evaluator, ModelConfig

p=argparse.ArgumentParser()
p.add_argument('--frequency',choices=['annual','weekly'],required=True)
p.add_argument('--input',required=True)
p.add_argument('--output',default=None)
a=p.parse_args()
groups=defaultdict(dict)
with open(a.input,newline='',encoding='utf-8-sig') as f:
 reader=csv.DictReader(f)
 for r in reader:
  loc=r['location'].strip(); sp=r['species'].strip().lower(); n=float(r['nests'])
  if n<0:raise ValueError('Negative nest count')
  if a.frequency=='annual':
   period=int(r['year']); key=(loc,sp)
  else:
   if r.get('frequency')!='weekly':raise ValueError('Weekly input must have frequency=weekly')
   period=date.fromisoformat(r['period_end']);key=(loc,sp,int(r['year']))
  if period in groups[key]:raise ValueError(f'Duplicate observation: {key} {period}')
  groups[key][period]=n
print('Loading TimesFM 3 on CPU...')
model=TimesFM3Evaluator(ModelConfig(checkpoint_path='google/timesfm-3.0-pytorch',per_core_batch_size=1,device='cpu'))
def predict(x):
 result=next(iter(model.predict_batch([np.asarray(x,dtype=np.float32)],horizon=1,return_quantiles=False,use_symmetric_averaging=False)))
 return max(0.,float(result.forecast[0]))
results=[]
for key, counts in sorted(groups.items()):
 periods=sorted(counts)
 if a.frequency=='annual':
  # no interpolation or invented missing year
  complete=periods==list(range(periods[0],periods[-1]+1))
  minimum=8
  if not complete or len(periods)<minimum:
   print('Skipping annual incomplete/short:',key);continue
  subset=periods
 else:
  # only most recent contiguous sequence; missing weeks are NOT zeros
  chains=[]; cur=[]
  for dt in periods:
   if cur and (dt-cur[-1]).days !=7:chains.append(cur);cur=[]
   cur.append(dt)
  if cur:chains.append(cur)
  subset=max(chains,key=len)
  if len(subset)<8:
   print('Skipping weekly short contiguous run:',key);continue
 values=[counts[d] for d in subset]
 horizon_period=subset[-1]+1 if a.frequency=='annual' else (subset[-1]+timedelta(days=7)).isoformat()
 row={'location':key[0],'species':key[1],'frequency':a.frequency,'training_observations':len(values),'last_observed_period':str(subset[-1]),'next_period':horizon_period,'forecast_nests':round(predict(values),2),'limitations':('Within-season next 7-day interval; NOT a whole-season forecast; only 2007/2008 evidence' if a.frequency=='weekly' else 'Annual next year; compare with a simple baseline before use')}
 if a.frequency=='weekly':row['season_year']=key[2]
 results.append(row)
 print(key, '->',horizon_period, ':',row['forecast_nests'])
filename=a.output or f'forecast_{a.frequency}_experimental.json'
Path(filename).write_text(json.dumps(results,indent=2),encoding='utf8')
print('Saved',filename)
