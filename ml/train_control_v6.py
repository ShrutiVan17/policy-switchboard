"""Matched frozen-encoder control for the repaired curriculum."""
import subprocess
import sys
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
        subprocess.run([sys.executable,'-m','ml.train_evidence','--model','sentence-transformers/all-MiniLM-L6-v2',
            '--revision','1110a243fdf4706b3f48f1d95db1a4f5529b4d41','--tenant',tenant,'--policy-version',version,
            '--train',str(root/f'data-v6/{tenant}-{version}-train.jsonl'),'--validation',str(root/f'data-v6/{tenant}-{version}-validation.jsonl'),
            '--output',str(root/f'models/control-{tenant}-{version}'),'--epochs','45','--batch-size','32',
            '--unsafe-penalty','1','--select-best-validation','--head-only'],check=True,cwd=root)
    subprocess.run([sys.executable,'-m','ml.evaluate_evidence','--data-dir','data-v6','--model-prefix','control'],check=True,cwd=root)


if __name__=='__main__':main()
