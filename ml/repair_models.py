"""Train candidates, preserve evidence, then activate only nonregressing research."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .build_repaired import build

ROOT=Path(__file__).resolve().parents[1]


def activate(moves,model_root):
    for active,archive,candidate_path in moves:
        if not all(p.resolve().is_relative_to(model_root.resolve()) for p in (active,archive,candidate_path)):
            raise ValueError('Promotion path outside model workspace')
        if archive.exists() or not active.is_dir() or not candidate_path.is_dir():
            raise ValueError('Ambiguous or incomplete promotion')
    moved=[];installed=[]
    try:
        for active,archive,candidate_path in moves:
            active.rename(archive);moved.append((active,archive,candidate_path))
            candidate_path.rename(active);installed.append(active)
    except Exception:
        for active,archive,candidate_path in reversed(moved):
            if active in installed:active.rename(candidate_path)
            archive.rename(active)
        raise


def main():
    build(ROOT/'data-v6')
    baseline=json.loads((ROOT/'artifacts/evidence-model.json').read_text(encoding='utf-8'))
    history=ROOT/'artifacts/history';history.mkdir(exist_ok=True)
    for path in (ROOT/'artifacts').glob('evidence-model*.json'):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        target=history/f'{digest}.json'
        if not target.exists():shutil.copy2(path,target)
    for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
        subprocess.run([sys.executable,'-m','ml.train_evidence','--model','sentence-transformers/all-MiniLM-L6-v2',
            '--revision','1110a243fdf4706b3f48f1d95db1a4f5529b4d41','--tenant',tenant,'--policy-version',version,
            '--train',str(ROOT/f'data-v6/{tenant}-{version}-train.jsonl'),'--validation',str(ROOT/f'data-v6/{tenant}-{version}-validation.jsonl'),
            '--output',str(ROOT/f'models/candidate-{tenant}-{version}'),'--epochs','45','--batch-size','32','--unsafe-penalty','1','--select-best-validation'],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'-m','ml.evaluate_evidence','--data-dir','data-v6','--model-prefix','candidate'],check=True,cwd=ROOT)
    candidate=json.loads((ROOT/'artifacts/candidate-model.json').read_text(encoding='utf-8'))
    if (candidate['correct']<baseline['correct'] or candidate['gate']['unsafe_allows']>baseline['gate']['unsafe_allows']
        or candidate['gate']['challenge_correct']<baseline['gate']['challenge_correct']
        or candidate['gate']['challenge_unsafe_allows']>baseline['gate']['challenge_unsafe_allows']):
        print('Candidate regressed on development checks; active adapters preserved.');return
    moves=[]
    for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
        active=ROOT/f'models/evidence-{tenant}-{version}'
        digest=hashlib.sha256((active/'run_manifest.json').read_bytes()).hexdigest()
        archive=ROOT/f'models/history/{digest}';archive.parent.mkdir(exist_ok=True)
        if archive.exists():
            raise ValueError('Existing model archive; refusing ambiguous replacement')
        candidate_path=ROOT/f'models/candidate-{tenant}-{version}'
        if not all(p.resolve().is_relative_to((ROOT/'models').resolve()) for p in (active,archive,candidate_path)):
            raise ValueError('Promotion path outside model workspace')
        moves.append((active,archive,candidate_path))
    activate(moves,ROOT/'models')
    subprocess.run([sys.executable,'-m','ml.evaluate_evidence','--data-dir','data-v6'],check=True,cwd=ROOT)
    print('Nonregressing research candidate activated; customer delivery remains disabled.')


if __name__=='__main__':main()
