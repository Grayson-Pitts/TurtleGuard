"""One-command 2027 forecasts: direct beach TimesFM + FWC county TimesFM + statewide map."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
parser=argparse.ArgumentParser()
parser.add_argument('--skip-forecast',action='store_true',help='Use existing 2027 direct+county TimesFM results')
parser.add_argument('--skip-weekly',action='store_true',help='Compatibility flag: weekly model is not run')
parser.add_argument('--exclude-provisional-2026',action='store_true',help='Exclude 2026 Mote provisional observations from direct model')
parser.add_argument('--refresh-fwc',action='store_true',help='Redownload the official FWC beach geometry')
parser.add_argument('--batch-size',type=int,default=6)
args=parser.parse_args()
if args.batch_size<=0:parser.error('--batch-size must be positive')
def run(script,*arguments):
    command=[sys.executable,str(SCRIPTS/script),*map(str,arguments)]
    print('\n>>>', ' '.join(command),flush=True)
    subprocess.run(command,cwd=ROOT,check=True)

# Fetch geometry first and validate it before expensive TimesFM inference.
run('download_fwc_beaches.py',*(['--refresh'] if args.refresh_fwc else []))
if not args.skip_forecast:
    direct=['--batch-size',args.batch_size]
    if args.exclude_provisional_2026:direct.append('--exclude-provisional-2026')
    run('forecast_2027.py',*direct)
    run('forecast_counties_2027.py','--batch-size',args.batch_size)
run('build_dashboard_data.py')
run('build_beach_priorities.py')
run('build_statewide_estimates.py')
run('normalize_priority_scores.py')
run('audit_statewide_outputs.py')
print('\nBuilt direct + statewide estimated 2027 map from TimesFM. Launch local web server and refresh.')
