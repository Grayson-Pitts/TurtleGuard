"""Audit existing TurtleGuard 2027 forecasts and FWC beach allocations.
Does NOT modify forecasts or coastline data; no TimesFM model load required.
Produces direct_match_review.csv, county_forecast_plausibility.csv, and map_audit_report.json.
"""
import csv, json, math, statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/FWC_county_nesting_2021_2025.csv'
COUNTY=ROOT/'county_forecasts_2027.json'
RAW=ROOT/'site/fwc_beaches.geojson'
MAPPED=ROOT/'site/statewide_estimates.geojson'
DIRECT=ROOT/'site/priorities.json'
OUT=ROOT/'site'

def key(value):
    import re
    s=str(value or '').strip().casefold()
    s=re.sub(r'\s+county$', '', s)
    return re.sub(r'[^a-z0-9]', '', s)

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer=csv.DictWriter(file, fieldnames=fields)
        writer.writeheader();writer.writerows(rows)

def audit():
    historical=defaultdict(lambda:defaultdict(float))
    status_warnings=[]
    with DATA.open(newline='', encoding='utf-8-sig') as file:
        for r in csv.DictReader(file):
            if r['status'].strip().lower()=='observed' and r['nests'].strip():
                historical[key(r['location'])][int(r['year'])]+=float(r['nests'])
            elif r['nests'].strip()=='':
                status_warnings.append(f'Missing or not-surveyed source: {r["location"]}/{r["species"]}/{r["year"]}')

    predictions=read(COUNTY); original=read(RAW); mapped=read(MAPPED); direct=read(DIRECT)
    assert predictions['target_year']==2027 and predictions['model']=='google/timesfm-3.0-pytorch'
    assert mapped['metadata']['year']==2027 and direct['forecast_year']==2027
    assert len(direct['regions'])==8, 'Expected 8 direct monitoring areas'
    assert len(predictions['forecasts'])==81, 'Expected 27 counties x 3 TimesFM series'

    original_ids={str(f['properties']['OBJECTID']) for f in original['features']}
    mapped_ids={str(f['properties']['OBJECTID']) for f in mapped['features']}
    if len(original_ids)!=len(original['features']) or len(mapped_ids)!=len(mapped['features']) or original_ids!=mapped_ids:
        raise ValueError('Original/mapped FWC OBJECTID coverage mismatch or duplicates')

    by_county=defaultdict(float)
    for r in predictions['forecasts']:
        assert r['target_year']==2027 and r['model']=='google/timesfm-3.0-pytorch'
        by_county[key(r['county'])]+=float(r['forecast_nests'])
    county_rows=[]; issues=[]
    sums=mapped['metadata']['county_allocation_checks']
    for county, forecast in sorted(by_county.items()):
        history=historical.get(county,{})
        vals=[history.get(y) for y in range(2021,2026)]
        if any(v is None for v in vals):
            issues.append(f'{county}: missing complete 2021-2025 history')
            continue
        avg=statistics.mean(vals); max5=max(vals)
        last=vals[-1]; ratio=forecast/avg if avg else None
        allocated=float(sums.get(county,{}).get('allocated_nests',0))
        segments=int(sums.get(county,{}).get('mapped_segments',0))
        discrepancy=abs(allocated-forecast)
        if discrepancy>max(.11,.001*forecast):
            issues.append(f'{county}: {forecast:.1f} TimesFM county nests but only {allocated:.1f} allocated to FWC lines ({segments} lines)')
        if avg>=10 and ratio is not None and (ratio>1.5 or ratio<0.6):
            issues.append(f'{county}: forecast {forecast:.1f} is {ratio:.2f}x its 2021-25 mean; review small-history uncertainty')
        if avg>=20 and (forecast>2*max5 or (min(vals)>0 and forecast<.35*min(vals))):
            issues.append(f'{county}: extreme historical range deviation ({forecast:.1f}); inspect')
        county_rows.append({'county':county,'forecast_2027':round(forecast,1),
          'observed_2025':round(last,1),'five_year_mean':round(avg,1),
          'forecast_over_mean':round(ratio,3) if ratio is not None else '',
          'mapped_segments':segments,'allocated_nests':round(allocated,1),
          'difference_forecast_minus_allocated':round(forecast-allocated,1)})

    by_direct=defaultdict(list)
    saturated_estimates=[]
    counts={'direct':0,'county_estimate':0,'gray':0}
    for f in mapped['features']:
        p=f['properties'];id_=p['turtleguard_fwc_objectid']
        name=p.get('turtleguard_direct_region')
        if name:
            counts['direct']+=1
            by_direct[name].append({'direct_region':name,'fwc_objectid':id_,
               'fwc_beach_name':p.get('Beach',''), 'county':p.get('County',''),
               'mapped_length_km':p.get('turtleguard_line_km'),
               'match_method':p.get('turtleguard_direct_match_method','')})
        elif p.get('turtleguard_type')=='timesfm_county_disaggregation':
            counts['county_estimate']+=1
        else: counts['gray']+=1
        if p.get('turtleguard_type')=='timesfm_county_disaggregation':
            score=p.get('turtleguard_priority_score'); nests=p.get('turtleguard_estimated_nests')
            if score is None or not 0<=float(score)<=100 or nests is None or float(nests)<0:
                raise ValueError(f'Invalid score/estimate for OBJECTID {id_}')
            if not name and float(score)>=99.9:
                saturated_estimates.append(str(id_))

    for direct_region in [r['name'] for r in direct['regions']]:
        if not by_direct.get(direct_region):
            issues.append(f'Direct region {direct_region} not represented by official FWC lines (may use approximated fallback)')

    # Data source discrepancy: the user's Jan 2026 FWC/FWRI 5-year PDF
    # lists Brevard leatherbacks 2025=130, while the published 2025 FWC
    # statewide HTML table lists 129. No automatic correction is made.
    if historical.get('brevard',{}).get(2025)==53277:
        issues.append('SOURCE-VERSION NOTE: source PDF has Brevard 2025 leatherbacks 130, current FWC public 2025 table 129; retain PDF value until provenance reconciled')
    if 'levy' in by_county:
        issues.append('Levy County appears in FWC 2021-25 historical PDFs but has no matching FWC atlas beach segment; do not paint an estimate there')
    if saturated_estimates:
        issues.append(f'{len(saturated_estimates)} county-derived beach scores saturate at approximately 100/100; compare scoring normalization before interpreting all as maximal risk')
    issues.extend(status_warnings)
    for item in mapped['metadata'].get('allocation_warnings',[]):
        if item not in issues: issues.append(item)

    detail=[r for name in sorted(by_direct) for r in by_direct[name]]
    write_csv(OUT/'direct_match_review.csv',detail,['direct_region','fwc_objectid','fwc_beach_name','county','mapped_length_km','match_method'])
    write_csv(OUT/'county_forecast_plausibility.csv',county_rows,
       ['county','forecast_2027','observed_2025','five_year_mean','forecast_over_mean',
        'mapped_segments','allocated_nests','difference_forecast_minus_allocated'])
    report={'forecast_year':2027,'source_fwc_objectid_count':len(original_ids),
            'map_fwc_objectid_count':len(mapped_ids),
            'display_counts':counts,'saturated_estimated_segment_ids':saturated_estimates,'direct_regions':{name:len(vals) for name,vals in sorted(by_direct.items())},
            'issues_for_review':issues,
            'scientific_caveats':['5 annual observations for county TimesFM forecasts; no adequate held-out validation',
              'FWC quartile density classes are not calibrated 0.5/1/2 numeric multipliers',
              'FWC GIS line length may not equal current-year surveyed beach length',
              'County allocation is deterministic and is not a beach-level TimesFM prediction',
              'Direct region mapping uses approximate geometric bounding rules; inspect direct_match_review.csv',
              'County total sums include segments whose display is overridden by direct predictions; do not add map labels as separate counts'],
            'model':'google/timesfm-3.0-pytorch'}
    (OUT/'map_audit_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'FWC OBJECTIDs checked: {len(original_ids)} identical source/mapped, no duplicates')
    print(f"Visible map segments: {counts['direct']} DIRECT solid, {counts['county_estimate']} COUNTY dashed, {counts['gray']} gray")
    print('Wrote site/map_audit_report.json, site/county_forecast_plausibility.csv, site/direct_match_review.csv')
    if issues:
        print('CHECK THESE WARNINGS (none silently auto-corrected):')
        for issue in issues: print('  -',issue)
    return report

if __name__=='__main__':audit()
