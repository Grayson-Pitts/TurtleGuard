"""Unit/integration tests do not require TimesFM weights. Run: python -m unittest discover -s tests"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

spec=importlib.util.spec_from_file_location('tgforecast',APP/'scripts'/'forecast_2027.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeResult:
    def __init__(self,values):self.forecast=values
class FakeForecaster:
    def predict_batch(self,arrays,horizon,**kwargs):
        for hist in arrays:
            avg=sum(hist[-min(5,len(hist)):])/min(5,len(hist))
            # Deterministic stub for testing only; no fake files are shipped as forecasts.
            yield FakeResult([avg*(1+.01*(h+1)) for h in range(horizon)])

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series=module.read_series(APP/'data'/'nesting_counts.csv')
        cls.tasks=module.run_model_forecasts(module.build_tasks(cls.series),forecaster=FakeForecaster(),batch_size=16)
        cls.preds,cls.tests=module.select_and_report(cls.tasks)

    def test_series_and_horizon(self):
        self.assertEqual(len(self.series),14)
        self.assertEqual(len({x['location'] for x in self.preds}),8)
        self.assertTrue(all(x['target_year']==2027 for x in self.preds))
        self.assertEqual({x['forecast_horizon_years'] for x in self.preds},{2,3})
        self.assertTrue(all(t['training_end']+t['horizon']==t['target_year'] for t in self.tasks))

    def test_no_leakage(self):
        self.assertTrue(all(t['training_end']<t['target_year'] for t in self.tasks if t['kind']=='backtest'))
        self.assertTrue(all(t['test_actual'] is None for t in self.tasks if t['kind']=='future'))

    def test_mock_data_build_and_lengths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'data').mkdir();(root/'scripts').mkdir();(root/'site').mkdir()
            for item in ('nesting_counts.csv','beach_lengths.csv'):
                (root/'data'/item).write_bytes((APP/'data'/item).read_bytes())
            for item in ('build_dashboard_data.py','build_beach_priorities.py'):
                (root/'scripts'/item).write_bytes((APP/'scripts'/item).read_bytes())
            (root/'forecast_results.json').write_text(json.dumps(self.preds),encoding='utf8')
            for item in ('build_dashboard_data.py','build_beach_priorities.py'):
                subprocess.run([sys.executable,str(root/'scripts'/item)],check=True,capture_output=True)
            data=json.loads((root/'site'/'priorities.json').read_text())
            self.assertEqual(len(data['regions']),8)
            self.assertEqual(data['forecast_year'],2027)
            self.assertTrue(all(x['projected_nests_per_mile']>=0 for x in data['regions']))
            self.assertTrue(all(10<=x['priority_score']<=90 for x in data['regions']))
            self.assertEqual(len({r['name'] for r in data['regions']}),8)
            # Stale forecasts must fail loudly.
            corrupted=json.loads((root/'forecast_results.json').read_text())
            corrupted[0]['target_year']=2026
            (root/'forecast_results.json').write_text(json.dumps(corrupted))
            proc=subprocess.run([sys.executable,str(root/'scripts'/'build_beach_priorities.py')],capture_output=True)
            self.assertNotEqual(proc.returncode,0)

if __name__=='__main__':unittest.main()
