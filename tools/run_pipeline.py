"""Re-run supplied R02-R09 code in a new folder; never overwrite archived results."""
from pathlib import Path
import argparse, os, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--output',default='build/run',help='New output directory inside this repository')
args=parser.parse_args()
out=(ROOT/args.output).resolve()
if not out.is_relative_to(ROOT/'build'):
    raise SystemExit('Output must be below build/.')
out.mkdir(parents=True,exist_ok=False)
for p in (ROOT/'data/inputs').glob('*.csv'):shutil.copy2(p,out/p.name)
scripts=sorted((ROOT/'analysis').glob('R*.py'))
env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PYTHONUTF8']='1'
for source in scripts:
    script=out/source.name
    shutil.copy2(source,script)
    command=[sys.executable,str(script)]
    if not source.name.startswith('R02_'):command+=['--root',str(out)]
    print('Running '+source.name,flush=True)
    with (out/(source.stem+'.log')).open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit('Stage failed; inspect '+str(out/(source.stem+'.log')))
print('Analysis complete: '+str(out))
print('Next: python tools/compare_run.py --run '+out.relative_to(ROOT).as_posix())
