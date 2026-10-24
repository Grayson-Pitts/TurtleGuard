"""Aggregate annual species forecasts, add historical support, and prepare segment-mapping data."""
import json,datetime,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'site'/'data.json').read_text(encoding='utf-8'))
config={'Boca Raton':{'matching_rule':'Boca Raton beach name only','county':'PALM BEACH','match_terms':['boca']},'Volusia County':{'matching_rule':'All FWC segments within Volusia County; regional allocation proxy','county':'VOLUSIA','match_terms':[]},'Canaveral National Seashore':{'matching_rule':'Canaveral-named FWC segments only','county':'BREVARD','match_terms':['canaveral']}}
result=[]
for l in data['locations']:
 specs=l['species']; latest=min(s['last_year'] for s in specs); nextyear=latest+1
 # Forecast years may vary by species; avoid summing different target years.
 eligible=[s for s in specs if s['forecast_year']==nextyear]
 forecast=sum(max(0,s['selected_forecast']) for s in eligible)
 hist_totals={}
 for s in specs:
  for obs in s['history']:
   hist_totals.setdefault(obs['year'],0)
   hist_totals[obs['year']]+=obs['nests']
 n=len(hist_totals); historic_activity=sum(1 for val in hist_totals.values() if val>0)/n if n else 0
 vals=sorted(hist_totals.items());mean5=statistics.mean(v for y,v in vals[-5:])
 model_count=sum(1 for s in eligible if s['selected_method']=='timesfm' and s['model_available'])
 result.append({'id':l['name'],'name':l['name'],'year':nextyear,'projected_total_nests':round(forecast,1),'historical_active_year_fraction':round(historic_activity,3),'historical_mean_5yr_nests':round(mean5,1),'source_count':len(eligible),'series_count':len(specs),'timesfm_selected_series':model_count,'available_species':[s['species'] for s in eligible],'proxy_mapping':config[l['name']], 'scope':l.get('scope'),'source_url':l.get('url')})
out={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'regions':result,'caveats':['Regions differ in surveyed extent and protocols','No beach-specific predicted nest counts are claimed','Forecast year varies by source','Undocumented species may be omitted from total']}
(ROOT/'site'/'priorities.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('Wrote site/priorities.json:',len(result),'regions,',sum(r['series_count'] for r in result),'species series')
for r in result:print(r['name'],r['year'],r['projected_total_nests'],'nests', 'TimesFM selected',r['timesfm_selected_series'])
