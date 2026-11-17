from pathlib import Path
import csv,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from quant_g0.core import compare_samples
if __name__=='__main__':
    with open(sys.argv[1],newline='') as f: result=compare_samples(list(csv.DictReader(f)))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['status']=='PASS' else 1)
