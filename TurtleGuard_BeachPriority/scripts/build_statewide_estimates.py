"""Allocate TimesFM county predictions to FWC beach polylines by actual OBJECTID.
County 2027 species forecast * (segment length x ordinal FWC density weight) /
county total weights. This is a heuristic disaggregation, NOT TimesFM applied to a beach.
No beach-name text matching, no fabricated per-beach training series.
"""
import json, math, csv, re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from direct_area_spatial_rules import approximate_direct_region
YEAR=2027
SP_FIELDS={'loggerhead':'ccDensClass','green':'cmDensClass','leatherback':'dcDensClass'}
CLASS_WEIGHTS={'low':0.5,'medium':1.0,'high':2.0}


def county_key(raw):
    s=str(raw or '').casefold().strip()
    s=re.sub(r'\s+county$','',s)
    s=s.replace('.','').replace('saint ','st ').replace('st johns','st johns').replace('miami dade','miami-dade')
    s=re.sub(r'[^a-z0-9]+','',s)
    # The only administrative alias, not beach-name guessing.
    return {'dade':'miamidade'}.get(s,s)


def density_class(v):
    if v is None:return None
    x=re.sub(r'\s+',' ',str(v)).strip().lower()
    if not x:return None
    if x.startswith(('high','h -','h ')) or x=='h':return 'high'
    if x.startswith(('medium','moderate','med','m -','m ')) or x=='m':return 'medium'
    if x.startswith(('low','l -','l ')) or x=='l':return 'low'
    if any(word in x for word in ('none','not observed','no nests','absent','not present')):return 'absent'
    return None


def distance_km(lon1,lat1,lon2,lat2):
    r=6371.0088
    lat1,lat2=math.radians(lat1),math.radians(lat2)
    dlat=lat2-lat1;dlon=math.radians(lon2-lon1)
    a=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*r*math.asin(min(1.0,math.sqrt(a)))


def geometry_length_km(geometry):
    typ=geometry['type']; coords=geometry['coordinates']
    lines=[coords] if typ=='LineString' else coords if typ=='MultiLineString' else []
    total=0.
    for line in lines:
        total+=sum(distance_km(a[0],a[1],b[0],b[1]) for a,b in zip(line,line[1:]))
    return total


def get_county_forecasts(payload):
    if payload.get('target_year')!=YEAR or payload.get('model')!='google/timesfm-3.0-pytorch':
        raise ValueError('Expected 2027 TimesFM county estimates; rerun forecast_counties_2027.py')
    group=defaultdict(dict)
    for row in payload['forecasts']:
        if int(row['target_year'])!=YEAR or row['model']!='google/timesfm-3.0-pytorch':
            raise ValueError('Stale or non-TimesFM county estimate')
        key=county_key(row['county']);sp=row['species'];v=float(row['forecast_nests'])
        if sp not in SP_FIELDS or sp in group[key] or not math.isfinite(v) or v<0:raise ValueError('Invalid duplicated county species forecast: '+str(row))
        group[key][sp]=v
    return group


def build(geometry, county_data, direct_data):
    if int(direct_data.get('forecast_year',0))!=YEAR:raise ValueError('Direct forecasts not 2027')
    direct_regions=direct_data.get('regions',[])
    if len(direct_regions)<8 or any(r['year']!=YEAR for r in direct_regions):raise ValueError('Missing one of the 8 direct regions')
    county_fc=get_county_forecasts(county_data)
    features=geometry['features']
    if len(features)<150:raise ValueError('FWC GIS is incomplete: fewer than 150 beaches')
    rows=[]; eligible=defaultdict(list); no_match=[]; unknown_class=defaultdict(set); ids=set()
    direct_by_name={r["name"]:r for r in direct_regions}
    direct_matched=defaultdict(int)
    for orig in features:
        f=json.loads(json.dumps(orig));p=f['properties'];oid=p.get('OBJECTID')
        if oid is None or oid in ids:raise ValueError('Missing/duplicate FWC OBJECTID '+str(oid))
        ids.add(oid)
        key=county_key(p.get('County'));length=geometry_length_km(f['geometry'])
        density={sp:density_class(p.get(field)) for sp,field in SP_FIELDS.items()}
        for sp,val in density.items():
            if val is None and p.get(SP_FIELDS[sp]) not in (None,''):
                unknown_class[sp].add(str(p[SP_FIELDS[sp]]))
        direct_id=approximate_direct_region(key,f['geometry'])
        if direct_id not in direct_by_name:direct_id=None
        if direct_id:direct_matched[direct_id]+=1
        r={'f':f,'key':key,'length_km':length,'classes':density,'per_species':{},'direct_id':direct_id}
        rows.append(r)
        if key not in county_fc: no_match.append(str(p.get('County')))
        elif length>0:eligible[key].append(r)
    alerts=[]; sums={}
    for county, observations in county_fc.items():
        mapped=eligible.get(county,[])
        sums[county]={'forecast_total_nests':round(sum(observations.values()),2),
                      'allocated_nests':0.,'mapped_segments':len(mapped),'unallocated_species':[]}
        if not mapped:
            alerts.append(f'County {county} has TimesFM data but no FWC polygons/lines matched by County field.')
            continue
        for species,value in observations.items():
            denom=sum(r['length_km']*CLASS_WEIGHTS.get(r['classes'][species],0) for r in mapped)
            if denom <= 0:
                if value>0:
                    sums[county]['unallocated_species'].append(species)
                    alerts.append(f'{county}: {species} 2027 forecast has no positive mapped density-class weights, so not allocated.')
                continue
            for r in mapped:
                w=r['length_km']*CLASS_WEIGHTS.get(r['classes'][species],0)
                r['per_species'][species]=value*(w/denom)
        sums[county]['allocated_nests']=round(sum(sum(r['per_species'].values()) for r in mapped),2)
    max_direct_density=max(float(r['projected_nests_per_mile']) for r in direct_regions)
    if max_direct_density<=0:raise ValueError('Invalid reference density from direct forecast')
    output=[];estimated=0;gray=0
    for r in rows:
        f=r['f'];p=f['properties'];km=r['length_km']
        estimated_nests=sum(r['per_species'].values())
        if km>0 and estimated_nests>0:
            density=estimated_nests/(km/1.609344)
            score=round(min(100,10+80*math.sqrt(density/max_direct_density)),1)
            estimated+=1
        else:
            density=None;score=None;gray+=1
        # Direct monitoring areas override county estimates visually: NEVER sum the two.
        # Both layers still retain provenance, so their geographic scopes remain explicit.
        if r['direct_id']:
            direct=direct_by_name[r['direct_id']]
            p['turtleguard_direct_region']=r['direct_id']
            p['turtleguard_direct_priority_score']=float(direct['priority_score'])
            p['turtleguard_direct_region_nests']=float(direct['projected_total_nests'])
            p['turtleguard_direct_nests_per_mile']=float(direct['projected_nests_per_mile'])
            p['turtleguard_direct_match_method']='approximate coordinate area + FWC county attribute, not beach-name text'
        # IDs are assigned from the GIS primary key; do not use the display name for linking.
        f['id']=str(p['OBJECTID'])
        p.update({'turtleguard_fwc_objectid':p['OBJECTID'],
                  'turtleguard_type':'timesfm_county_disaggregation' if score is not None else 'no_supported_estimate',
                  'turtleguard_forecast_year':YEAR if score is not None else None,
                  'turtleguard_estimated_nests':round(estimated_nests,1) if score is not None else None,
                  'turtleguard_nests_per_mile':round(density,2) if density is not None else None,
                  'turtleguard_priority_score':score,
                  'turtleguard_line_km':round(km,3),
                  'turtleguard_county_key':r['key'],
                  'turtleguard_input_history_years':5 if score is not None else None,
                  'turtleguard_allocation_rule':'TimesFM county annual forecasts × length × FWC ordinal class weight' if score is not None else None})
        output.append(f)
    payload={'type':'FeatureCollection','features':output,
             'metadata':{'year':YEAR,'model':'google/timesfm-3.0-pytorch',
                         'source':'FWC official nest density GIS layer, 2021-2025 + county nest counts 2021-2025',
                         'feature_id':'FWC OBJECTID, never beach name',
                         'estimated_segments':estimated,'gray_segments':gray,
                         'county_forecast_count':len(county_fc),'county_allocation_checks':sums,
                         'direct_gis_match_counts':dict(direct_matched),
                         'direct_no_gis_match':[r for r in direct_by_name if not direct_matched.get(r)],
                         'unknown_density_values':{k:sorted(v) for k,v in unknown_class.items()},
                         'unmatched_fwc_county_names':sorted(set(no_match)),
                         'allocation_warnings':alerts,
                         'caveat':'County-level TimesFM forecasts on five annual observations are heuristically distributed by surveyed coastline length and categorical density; NOT beach-level AI forecasts or verified nesting risk.',
                         'generated_utc':datetime.now(timezone.utc).isoformat()}}
    return payload


def main():
    src=ROOT/'site'/'fwc_beaches.geojson'
    if not src.exists():raise FileNotFoundError('Missing site/fwc_beaches.geojson; run download_fwc_beaches.py first')
    county=ROOT/'county_forecasts_2027.json'
    if not county.exists():raise FileNotFoundError('Missing county_forecasts_2027.json; run forecast_counties_2027.py first')
    raw=json.loads(src.read_text(encoding='utf8'))
    cf=json.loads(county.read_text(encoding='utf8'))
    direct=json.loads((ROOT/'site'/'priorities.json').read_text(encoding='utf8'))
    out=build(raw,cf,direct)
    path=ROOT/'site'/'statewide_estimates.geojson'; tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(out,separators=(',',':')),encoding='utf8');tmp.replace(path)
    meta=out['metadata']
    print(f'Wrote {len(out["features"])} FWC GIS beach lines: {meta["estimated_segments"]} derived TimesFM county estimates + {meta["gray_segments"]} gray.')
    print('County allocation checks:')
    for key,row in sorted(meta['county_allocation_checks'].items()):
        print(f'  {key:20s} TimesFM county={row["forecast_total_nests"]:>10,.1f} allocated={row["allocated_nests"]:>10,.1f} lines={row["mapped_segments"]:>3}')
    if meta['unmatched_fwc_county_names']:print('Unmatched GIS County values (gray, no guessing):',meta['unmatched_fwc_county_names'])
    if meta['unknown_density_values']:print('Unrecognized density classes (not interpreted):',meta['unknown_density_values'])
    if meta['allocation_warnings']:print('Allocation warnings:',*meta['allocation_warnings'],sep='\n  ')
    print('Approximate direct-area matches to actual FWC shorelines:',meta['direct_gis_match_counts'])
    if meta['direct_no_gis_match']:print('Direct regions without GIS segments (will use approximate fallback):',meta['direct_no_gis_match'])

if __name__=='__main__':main()
