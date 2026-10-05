"""Bounded compact-model retraining; preserve the prior experiment."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import argparse
from .build_counterfactual import build


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--epochs',type=int,default=45)
    parser.add_argument('--head-only',action='store_true');args=parser.parse_args()
    prefix='control' if args.head_only else 'evidence'
    root=Path(__file__).resolve().parents[1]
    manifest=build(root/'data-v5')
    for name in ('evidence-model.json','evidence-model-holdout.json'):
        path=root/'artifacts'/name
        if path.exists() and not args.head_only:shutil.copy2(path,root/'artifacts'/name.replace('.json','-v4.json'))
    for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
        old=root/f'models/{prefix}-{tenant}-{version}'
        archive=root/f'models/archive-v4-{tenant}-{version}'
        if not args.head_only and old.exists() and not archive.exists():shutil.copytree(old,archive)
        command=[sys.executable,'-m','ml.train_evidence','--model','sentence-transformers/all-MiniLM-L6-v2',
            '--revision','1110a243fdf4706b3f48f1d95db1a4f5529b4d41','--tenant',tenant,'--policy-version',version,
            '--train',str(root/f'data-v5/{tenant}-{version}-train.jsonl'),
            '--validation',str(root/f'data-v5/{tenant}-{version}-validation.jsonl'),
            '--output',str(old),'--epochs',str(args.epochs),'--unsafe-penalty','1','--batch-size','32','--select-best-validation']
        if args.head_only:command+=['--head-only']
        subprocess.run(command,check=True,cwd=root)
    subprocess.run([sys.executable,'-m','ml.evaluate_evidence','--data-dir','data-v5','--model-prefix',prefix],check=True,cwd=root)


if __name__=='__main__':main()
