"""Download the authoritative FWC density GIS polyline layer, one permanent OBJECTID per beach.
Never geocode/match by beach name. Requires internet access only for refresh.
"""
import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://gis.myfwc.com/hosting/rest/services/Projects_FWC/Sea_Turtle_Nest_Density_Florida/MapServer/2/query'
FIELDS = 'OBJECTID,Beach,County,nYearsSurvey,muLength,ccDensClass,cmDensClass,dcDensClass'


def fetch(params, attempts=3):
    url = BASE + '?' + urllib.parse.urlencode(params)
    for i in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'TurtleGuard-Hackathon/1.0'}), timeout=35) as resp:
                parsed = json.load(resp)
            if 'error' in parsed:
                raise ValueError('FWC ArcGIS error: ' + json.dumps(parsed['error']))
            return parsed
        except Exception:
            if i == attempts - 1: raise
            time.sleep(i + 1)


def validate(collection, min_features=150):
    feats = collection.get('features')
    if collection.get('type') != 'FeatureCollection' or not isinstance(feats,list):
        raise ValueError('Unexpected GIS response format; expected GeoJSON FeatureCollection')
    if len(feats) < min_features:
        raise ValueError(f'Only {len(feats)} GIS features returned; refusing incomplete coastline coverage')
    ids = set()
    for f in feats:
        p=f.get('properties') or {}
        oid=p.get('OBJECTID', f.get('id'))
        if oid is not None and p.get('OBJECTID') is None:
            p['OBJECTID']=oid  # The ArcGIS GeoJSON 'id' is its OBJECTID.
        if oid is None or oid in ids:
            raise ValueError(f'Missing or duplicate GIS OBJECTID: {oid}')
        ids.add(oid)
        coords=(f.get('geometry') or {}).get('coordinates')
        typ=(f.get('geometry') or {}).get('type')
        if typ not in ('LineString','MultiLineString') or not coords:
            raise ValueError(f'Invalid geometry for OBJECTID {oid}')
        # Unnamed/unassigned official features remain mapped gray instead of being dropped.
        # OBJECTID and real geometry, not display names, are required for coverage.
        # Confirm proper WGS84 conversion instead of trusting an arbitrary GIS CRS.
        def visit(a):
            if isinstance(a,list) and len(a) >= 2 and all(isinstance(x,(float,int)) for x in a[:2]):
                lon,lat=a[:2]
                if not (-88 <= lon <= -79 and 24 <= lat <= 32):
                    raise ValueError(f'Geometry not Florida WGS84 for OBJECTID {oid}: {(lon,lat)}')
            elif isinstance(a,list):
                for sub in a: visit(sub)
        visit(coords)
    return len(feats)


def download(min_features=150):
    ids_data=fetch({'where':'1=1','returnIdsOnly':'true','f':'json'})
    ids=ids_data.get('objectIds')
    if not isinstance(ids,list) or len(ids)<min_features:
        raise ValueError(f'FWC returned {len(ids or [])} object IDs; check the service')
    features=[]
    for i in range(0,len(ids),75):
        batch=ids[i:i+75]
        page=fetch({'objectIds':','.join(str(n) for n in batch), 'outFields':FIELDS,
                    'returnGeometry':'true','outSR':4326,'f':'geojson'})
        if not isinstance(page.get('features'),list):
            raise ValueError(f'Missing GIS features for batch {i}')
        features.extend(page['features'])
    result={'type':'FeatureCollection','features':features,
            'metadata':{'source':'Florida FWC SNBS Nest Density 2021-2025',
                        'source_url':BASE.rsplit('/',1)[0],
                        'downloaded_utc':datetime.now(timezone.utc).isoformat(),
                        'feature_id_field':'OBJECTID'}}
    count=validate(result,min_features)
    if count!=len(ids) or {f['properties']['OBJECTID'] for f in features}!=set(ids):
        raise ValueError(f'Missing GIS IDs; got {count}/{len(ids)}. Refusing partial import.')
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--refresh',action='store_true',help='Force a fresh FWC download')
    args=p.parse_args()
    path=ROOT/'site'/'fwc_beaches.geojson'
    if path.exists() and not args.refresh:
        data=json.loads(path.read_text(encoding='utf8'))
        print(f'FWC coastline cached: {validate(data)} official GIS segments ({path}).')
        return
    result=download()
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,separators=(',',':')),encoding='utf8')
    tmp.replace(path)
    print(f'Downloaded {len(result["features"])} real FWC coastline segments to {path}.')

if __name__=='__main__': main()
