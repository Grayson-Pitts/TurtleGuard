"""One-command update: optional PDF intake -> 2027 predictions -> mapped priorities.
Run from TurtleGuard_BeachPriority using the existing TimesFM venv Python.
"""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
parser=argparse.ArgumentParser()
parser.add_argument('--skip-forecast',action='store_true',help='Only rebuild data from verified existing 2027 predictions')
parser.add_argument('--no-import',action='store_true',help='Skip supported Mote PDF intake')
parser.add_argument('--skip-weekly',action='store_true',help='Compatibility option; weekly inference is not used in 2027 priority')
parser.add_argument('--batch-size',type=int,default=6)
args=parser.parse_args()
def run(cmd):
    print('\n>>>',' '.join(map(str,cmd)),flush=True)
    subprocess.run([sys.executable,*map(str,cmd)],cwd=ROOT,check=True)
if not args.no_import:
    run([SCRIPTS/'import_mote_pdfs.py','--incoming','data/incoming_reports',
         '--output','data/mote_weekly_2007_2008.csv'])
if not args.skip_forecast:
    run([SCRIPTS/'forecast_2027.py','--batch-size',str(args.batch_size)])
for name in ('build_dashboard_data.py','build_beach_priorities.py'):
    run([SCRIPTS/name])
print('\n2027 data rebuilt. Run HTTP server and refresh browser. Weekly data stays separate and does not affect annual priorities.')
