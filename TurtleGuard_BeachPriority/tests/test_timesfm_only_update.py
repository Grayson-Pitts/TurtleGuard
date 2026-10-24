"""Offline tests; TimesFM API simulated only here, never in production."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import forecast_2027 as f
import merge_mote_annual_reports as m

class Output:
    def __init__(self,values):self.forecast=values
class FakeModel:
    def predict_batch(self,arrays,horizon,return_quantiles,use_symmetric_averaging):
        return [Output(np.asarray([float(a[-1])+.1*k for k in range(1,horizon+1)])) for a in arrays]

class TestPipeline(unittest.TestCase):
    def test_timesfm_sole_prediction(self):
        series=f.read_series(ROOT/'data/nesting_counts.csv')
        self.assertEqual(len(series),14)
        for area in m.AREAS:
            yrs,_=series[(area,'all')]
            self.assertEqual(yrs[0],2009)
            self.assertEqual(yrs[-1],2026)
        tasks=f.run_model_forecasts(f.build_tasks(series),batch_size=12,forecaster=FakeModel())
        preds,backtests=f.select_and_report(tasks)
        self.assertEqual(len(preds),14)
        self.assertGreater(len(backtests),90)
        self.assertTrue(all(p['selected_method']=='timesfm' for p in preds))
        self.assertTrue(all(p['forecast_nests']==p['timesfm_forecast_nests'] for p in preds))
        self.assertTrue(all(p['target_year']==2027 for p in preds))
        self.assertTrue(all(p['forecast_horizon_years']==1 for p in preds if p['location'] in m.AREAS))
        self.assertTrue(all(p['provisional_input_years']==[2026] for p in preds if p['location'] in m.AREAS))
        # New CSV covers the same other areas and has 14 series
        self.assertEqual(len({p['location'] for p in preds}),8)

    def test_exclude_provisional(self):
        series=f.read_series(ROOT/'data/nesting_counts.csv',exclude_provisional_2026=True)
        self.assertTrue(all(series[(name,'all')][0][-1]==2025 for name in m.AREAS))

    def test_source_extraction_and_merge(self):
        root=ROOT/'data/mote_annual_reports'
        pdfs=list(root.glob('*.pdf'))
        self.assertEqual(len(pdfs),17)
        for p in pdfs:
            self.assertTrue(m.get_candidates(p),p.name)
        # Re-import must not decrease values or add records; candidate audit remains consistent.
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'nesting.csv'
            merged, conflicts=m.merge_reports(root,ROOT/'data/nesting_counts.csv',target)
            with target.open() as stream:rows=list(csv.DictReader(stream))
            with (ROOT/'data/nesting_counts.csv').open() as src:
                original=list(csv.DictReader(src))
            self.assertEqual(rows,original)
            self.assertGreaterEqual(len(conflicts),20)
            key={(r['location'],int(r['year'])):int(r['nests']) for r in rows}
            self.assertEqual(key['Siesta Key',2025],663)
            self.assertEqual(key['Casey Key',2019],2314)
            self.assertEqual(key['Longboat Key',2026],1305)

if __name__=='__main__':unittest.main()
