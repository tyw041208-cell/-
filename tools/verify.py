"""Run all offline checks and preserve real exit codes; no external services."""
from pathlib import Path
import subprocess,sys,os,json,platform,hashlib
ROOT=Path(__file__).resolve().parents[1]
env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
commands=[('unittest',[sys.executable,'-m','unittest','discover','-s','tests','-v'],0),('compile',[sys.executable,'-m','compileall','-q','src','tests','tools','quantconnect'],0),('sample_comparison',[sys.executable,'tools/compare_samples.py','reports/evidence/independent_samples.csv'],1)]
results=[]
for label,args,expected in commands:
    p=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True)
    (ROOT/f'reports/evidence/{label}.log').write_text(p.stdout+p.stderr)
    results.append(dict(label=label,command=args,exit_code=p.returncode,expected_exit_code=expected,status='PASS' if p.returncode==expected else 'FAIL'))
manifest=dict(python=sys.version,platform=platform.platform(),project=str(ROOT),results=results)
(ROOT/'reports/evidence/local_verification.json').write_text(json.dumps(manifest,indent=2))
files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src','quantconnect','config','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(ROOT/'reports/evidence/source_sha256.json').write_text(json.dumps(files,indent=2,sort_keys=True))
print(json.dumps(manifest,indent=2))
sys.exit(any(r['status']=='FAIL' for r in results))
