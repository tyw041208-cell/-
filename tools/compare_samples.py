from pathlib import Path
import csv,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from quant_g0.core import compare_samples
if __name__=='__main__':
    try:
        config=json.loads((ROOT/'config/g0.json').read_text())
        reference=json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv)>2 else None
        with open(sys.argv[1],newline='') as f: result=compare_samples(list(csv.DictReader(f)),config,reference)
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        result=dict(status='FAIL',error=str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['status']=='PASS' else 1)
