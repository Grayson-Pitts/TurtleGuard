"""TurtleGuard one-command dataset ingestion, predictions, and map refresh.
Run from TurtleGuard_BeachPriority: python scripts/run_all.py
"""
import argparse, subprocess, sys
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--skip-forecast',action='store_true',help='Import and rebuild UI using existing forecast results')
p.add_argument('--skip-weekly',action='store_true',help='Skip experimental next-week forecast')
p.add_argument('--no-import',action='store_true',help='Do not process incoming PDFs')
a=p.parse_args()
root=Path(__file__).resolve().parent.parent
scripts=root/'scripts'

def run(args):
    print('\n>>>',' '.join(map(str,args)),flush=True)
    subprocess.run([sys.executable,*map(str,args)],cwd=root,check=True)

if not a.no_import:run([scripts/'import_mote_pdfs.py','--incoming','data/incoming_reports','--output','data/mote_weekly_2007_2008.csv'])
if not a.skip_forecast:
    annual=scripts/'forecast_multi_short_history.py'
    if not annual.exists():annual=scripts/'forecast_multi.py'
    if not annual.exists():raise SystemExit('Missing annual forecast script. Copy forecast_multi_short_history.py from prior starter kit into scripts/.')
    run([annual,'data/nesting_counts.csv'])
    weekly_data=root/'data/mote_weekly_2007_2008.csv'
    weekly_script=scripts/'forecast_by_frequency.py'
    if not a.skip_weekly and weekly_data.exists() and weekly_script.exists():
        run([weekly_script,'--frequency','weekly','--input','data/mote_weekly_2007_2008.csv'])
    elif not a.skip_weekly:print('Weekly inference skipped: missing weekly dataset or scripts/forecast_by_frequency.py')
for name in ['build_dashboard_data.py','build_beach_priorities.py']:
    script=scripts/name
    if not script.exists():raise SystemExit(f'Missing {script}')
    run([script])
print('\nAll steps finished. Refresh TurtleGuard website. Annual and weekly forecast results remain separate.')
