"""Use one statewide nest-density reference for direct and county-derived priority scores.

This is a display-index transformation, NOT a TimesFM inference step. It leaves
all forecasted nest counts, geography, allocations, and species records untouched.
Run after build_beach_priorities.py AND build_statewide_estimates.py.
"""
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIRECT=ROOT/'site'/'priorities.json'
STATEWIDE=ROOT/'site'/'statewide_estimates.geojson'


def number(value):
    if value is None: return None
    n=float(value)
    if not math.isfinite(n) or n<0: raise ValueError('Invalid projected nests-per-mile value')
    return n


def score_for(density, reference):
    # Same sqrt curve as the former direct-region index, except it is now
    # anchored to all mapped areas, NOT only the 8 direct monitoring areas.
    # 10-90 design range: the upper value is not a probability or risk limit.
    return round(10 + 80*math.sqrt(density/reference),1)


def normalize(direct, statewide):
    if direct.get('forecast_year')!=2027 or statewide.get('metadata',{}).get('year')!=2027:
        raise ValueError('Both direct and statewide outputs must target 2027')
    regions=direct['regions']; features=statewide['features']
    if len(regions)!=8 or len(features)<150:
        raise ValueError('Unexpected mapping extent: expected 8 regions and at least 150 FWC features')
    densities=[number(r['projected_nests_per_mile']) for r in regions]
    estimated=[]
    for f in features:
        p=f['properties']
        d=number(p.get('turtleguard_nests_per_mile'))
        if d is not None and p.get('turtleguard_type')=='timesfm_county_disaggregation':
            estimated.append(d)
    if not estimated:raise ValueError('No county-estimated FWC features available')
    reference=max(densities+estimated)
    if reference<=0:raise ValueError('No positive nesting-density reference')
    unchanged_direct_nests={r['name']:r['projected_total_nests'] for r in regions}
    unchanged_est_nests={f['id']:f['properties'].get('turtleguard_estimated_nests') for f in features}
    for r,d in zip(regions,densities):
        r['priority_score']=score_for(d,reference)
        r['priority_basis']='statewide-relative 2027 projected nests per mile (sqrt normalized; shared direct+county reference)'
    by_name={r['name']:r for r in regions}
    revised=0
    for f in features:
        p=f['properties']
        d=number(p.get('turtleguard_nests_per_mile'))
        if d is not None and p.get('turtleguard_type')=='timesfm_county_disaggregation':
            p['turtleguard_priority_score']=score_for(d,reference)
            revised+=1
        name=p.get('turtleguard_direct_region')
        if name:
            if name not in by_name: raise ValueError('Unknown direct-region match: '+name)
            p['turtleguard_direct_priority_score']=by_name[name]['priority_score']
    assert unchanged_direct_nests=={r['name']:r['projected_total_nests'] for r in regions}
    assert unchanged_est_nests=={f['id']:f['properties'].get('turtleguard_estimated_nests') for f in features}
    metadata=statewide['metadata']
    metadata['priority_index_reference_nests_per_mile']=round(reference,2)
    metadata['priority_index_method']='10 + 80 * sqrt(nests_per_mile / max density across mapped direct and county areas), shared 2027 normalization; max 90 by design'
    metadata['priority_index_note']='Comparative nesting-density index, not a probability, hazard measurement, or independently validated cleanup priority.'
    direct['priority_index_reference_nests_per_mile']=round(reference,2)
    direct['priority_index_method']=metadata['priority_index_method']
    caveat='Index scores share one statewide reference but county-derived nests/mile depend on uncalibrated FWC category weights.'
    if caveat not in direct.setdefault('caveats',[]): direct['caveats'].append(caveat)
    return reference,revised


def main():
    direct=json.loads(DIRECT.read_text(encoding='utf-8'))
    statewide=json.loads(STATEWIDE.read_text(encoding='utf-8'))
    old_saturated=sum(
        f['properties'].get('turtleguard_direct_region') is None
        and f['properties'].get('turtleguard_priority_score') is not None
        and float(f['properties']['turtleguard_priority_score']) >= 99.9
        for f in statewide['features']
    )
    ref,estimated=normalize(direct,statewide)
    # Validate output before writing either file; keep all model outputs intact.
    assert all(0<=r['priority_score']<=90 for r in direct['regions'])
    assert all(p['properties'].get('turtleguard_priority_score') is None or
               0<=float(p['properties']['turtleguard_priority_score'])<=90
               for p in statewide['features'])
    for path,payload in ((DIRECT,direct),(STATEWIDE,statewide)):
        temp=path.with_name(path.name+'.new')
        temp.write_text(json.dumps(payload,indent=2 if path==DIRECT else None),encoding='utf-8')
        temp.replace(path)
    print(f'Normalized 8 direct regions and {estimated} county-derived FWC estimates.')
    print(f'Shared reference density: {ref:,.2f} nests/mile; scores now use 10..90, not 100 saturation.')
    print(f'Previously capped county estimates: {old_saturated}; currently at 100: 0.')
    print('All 2027 TimesFM forecasts and nest allocations are unchanged.')
    for r in sorted(direct['regions'],key=lambda r:-r['priority_score']):
        print(f"  {r['name']:<29} {r['projected_nests_per_mile']:>7.1f} nests/mile  -> {r['priority_score']:>4.1f}/100")

if __name__=='__main__':main()
