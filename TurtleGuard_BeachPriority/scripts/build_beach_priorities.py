"""2027 density-adjusted inspection index, joined by stable location names.

Uses the forecast JSON directly and published length estimates. Does not
substitute FWC county nests for counts on an individual beach.
"""
import csv,datetime,json,math
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
YEAR=2027

observations=defaultdict(dict)
with (ROOT/'data'/'nesting_counts.csv').open(newline='',encoding='utf8') as f:
    for row in csv.DictReader(f):
        key=(row['location'],row['species'])
        observations[key][int(row['year'])]=float(row['nests'])

lengths={}
with (ROOT/'data'/'beach_lengths.csv').open(newline='',encoding='utf8') as f:
    for row in csv.DictReader(f):
        miles=float(row['length_miles'])
        if not math.isfinite(miles) or miles<=0: raise ValueError('Invalid length for '+row['location'])
        lengths[row['location']]={**row,'length_miles':miles}

forecasts=json.loads((ROOT/'forecast_results.json').read_text(encoding='utf8'))
if not forecasts or any(int(f.get('target_year',f.get('forecast_year',0)))!=YEAR for f in forecasts):
    raise RuntimeError('Forecasts are missing or not 2027. Run scripts/forecast_2027.py first.')

if any(f.get('selected_method')!='timesfm' for f in forecasts):
    raise RuntimeError('Found baseline-selected predictions. Rerun the TimesFM-only forecast_2027.py before rebuilding priorities.')

parts=defaultdict(list)
for f in forecasts:
    key=(f['location'],f['species'])
    if key not in observations:raise RuntimeError('Missing matching observations for '+str(key))
    if f['location'] not in lengths:raise RuntimeError('Missing length for '+f['location'])
    parts[f['location']].append(f)

regions=[]
for loc,records in sorted(parts.items()):
    miles=lengths[loc]['length_miles']
    forecast=sum(max(0,float(r['forecast_nests'])) for r in records)
    timesfm=sum(max(0,float(r['timesfm_forecast_nests'])) for r in records)
    # Species records may omit rare species; do not label counts as all species without noting coverage.
    last_obs={r['species']:int(r['last_observed_year']) for r in records}
    record={
        'id':loc,'name':loc,'year':YEAR,'forecast_year':YEAR,
        'projected_total_nests':round(forecast,1),
        'timesfm_total_nests':round(timesfm,1),
        'survey_length_miles':round(miles,2),
        'length_quality':lengths[loc]['length_quality'],
        'length_source':lengths[loc]['source_url'],
        'length_limitations':lengths[loc]['limitations'],
        'projected_nests_per_mile':round(forecast/miles,2),
        'species_covered':[r['species'] for r in records],
        'uses_provisional_2026':any(2026 in r.get('provisional_input_years',[]) for r in records),
        'methods_used':{r['species']:r['selected_method'] for r in records},
        'source_years':last_obs,
        'source_count':len(records),'series_count':len(records),
        'timesfm_selected_series':sum(r['selected_method'] in ('timesfm','timesfm_parity_blend') for r in records),
        'scope':'Named beach monitoring area (geographic path approximate)' if loc!='Volusia County' else 'County-managed nesting area (length proxy from broader survey)',
        'mapping_uncertainty':'Approximate line; not surveyed GPS boundary',
        'length_verified_for_series':lengths[loc]['length_quality']!='county_extent_proxy_UNVERIFIED'
    }
    regions.append(record)

max_density=max(r['projected_nests_per_mile'] for r in regions)
if max_density<=0:raise RuntimeError('No positive densities')
for r in regions:
    # Monotonic normalized 0–100 index; not a calibrated chance or estimated ecological impact.
    r['priority_score']=round(10+80*math.sqrt(r['projected_nests_per_mile']/max_density),1)
    r['priority_basis']='relative projected nests per mile (sqrt normalized), 2027'

payload={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'forecast_year':YEAR,'regions':regions,
         'caveats':['Priority is a relative nesting-density index, not measured beach litter or cleanup effectiveness',
                    'Volusia length is a county-level proxy and does not exactly match the historical nesting survey boundary',
                    'Forecasts have differing historical end years and therefore differing direct model horizons',
                    'Some records omit rare species, and nest counts do not equal number of distinct turtles',
                    'Map GeoJSON paths are hand-approximated, not survey extents',
                    '2026 Mote counts are preliminary as of Week 42, not finished-season observations']}
p=ROOT/'site'/'priorities.json';p.write_text(json.dumps(payload,indent=2),encoding='utf8')
print(f'Wrote {p} for {len(regions)} regions (2027; length-adjusted):')
for r in sorted(regions,key=lambda x:-x['priority_score']):
    print(f"{r['name']:<28} nests={r['projected_total_nests']:>8,.1f}  "
          f"mi={r['survey_length_miles']:>5.1f}  nests/mi={r['projected_nests_per_mile']:>7.1f}  "
          f"priority={r['priority_score']:>5.1f}")
