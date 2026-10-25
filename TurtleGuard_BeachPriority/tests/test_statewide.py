"""Offline validation; fake TimesFM test responses NEVER exported as production forecasts."""
import sys,unittest,json,csv,tempfile
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import download_fwc_beaches as dl
import forecast_counties_2027 as cf
import build_statewide_estimates as alloc

class Output:
    def __init__(self,p):self.forecast=p
class FakeModel:
    def predict_batch(self,arrays,horizon,return_quantiles,use_symmetric_averaging):
        return [Output([max(0.,float(a[-1])*.94),max(0.,float(a[-1])*.99)]) for a in arrays]

class StatewideTests(unittest.TestCase):
    def test_county_histories_and_model(self):
        histories,excluded=cf.load_rows(ROOT/'data'/'FWC_county_nesting_2021_2025.csv')
        self.assertEqual(len(histories),27)
        self.assertIn('Hillsborough County',excluded)
        predicted=cf.make_predictions(histories,model=FakeModel(),batch_size=25)
        self.assertEqual(len(predicted),27*3)
        self.assertTrue(all(p['model']=='google/timesfm-3.0-pytorch' for p in predicted))
        self.assertTrue(all(p['target_year']==2027 for p in predicted))
        self.assertEqual(len({(p['county'],p['species']) for p in predicted}),len(predicted))

    def test_no_missing_as_zero(self):
        data=ROOT/'data'/'FWC_county_nesting_2021_2025.csv'
        with open(data,encoding='utf8',newline='') as f: rows=list(csv.DictReader(f))
        missing=[r for r in rows if r['status']!='observed']
        self.assertEqual(len(missing),1)
        self.assertEqual(missing[0]['nests'],'')

    def test_official_fwc_id_allocation_and_geometry(self):
        geom={'type':'FeatureCollection','features':[]}
        for oid in range(1,161):
            county='Sarasota' if oid<81 else 'Brevard'
            lat=27.22 if oid<81 else 28.72
            geom['features'].append({'type':'Feature','properties':{
                'OBJECTID':oid,'Beach':f'Unrelated arbitrary name {oid}','County':county,
                'ccDensClass':'High' if oid%2 else 'Medium',
                'cmDensClass':'Low','dcDensClass':'Low','nYearsSurvey':5},
                'geometry':{'type':'LineString','coordinates':[[-82.50,lat],[-82.50,lat+.005]] if oid<81 else [[-80.66,lat],[-80.66,lat+.005]]}})
        dl.validate(geom,min_features=150)
        county={'target_year':2027,'model':'google/timesfm-3.0-pytorch','forecasts':[
            {'county':county,'species':sp,'target_year':2027,'forecast_nests':n,'model':'google/timesfm-3.0-pytorch'}
            for county in ('Sarasota County','Brevard County')
            for sp,n in [('loggerhead',1000),('green',100),('leatherback',10)] ]}
        direct={'forecast_year':2027,'regions':[{'name':n,'year':2027,'priority_score':70,
             'projected_nests_per_mile':100,'projected_total_nests':1000} for n in
              ['Boca Raton','Canaveral National Seashore','Casey Key','Lido Key','Longboat Key','Siesta Key','Venice','Volusia County']]}
        result=alloc.build(geom,county,direct)
        self.assertEqual(len(result['features']),160)
        self.assertEqual(len({f['properties']['turtleguard_fwc_objectid'] for f in result['features']}),160)
        self.assertEqual(result['metadata']['estimated_segments'],160)
        sums=result['metadata']['county_allocation_checks']
        self.assertAlmostEqual(sums['sarasota']['allocated_nests'],1110,places=1)
        self.assertAlmostEqual(sums['brevard']['allocated_nests'],1110,places=1)
        self.assertTrue(any('turtleguard_direct_region' in f['properties'] for f in result['features']))
        self.assertEqual(result['features'][0]['properties']['Beach'],'Unrelated arbitrary name 1')

    def test_incomplete_gis_rejected(self):
        with self.assertRaisesRegex(ValueError,'Only 0 GIS features'):
            dl.validate({'type':'FeatureCollection','features':[]})

if __name__=='__main__':unittest.main()
