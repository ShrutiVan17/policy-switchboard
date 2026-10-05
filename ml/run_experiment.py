"""Reproduce the local GPU experiment; no paid services or customer data."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

MODEL = 'HuggingFaceTB/SmolLM2-135M-Instruct'
REVISION = '02e84e7cc564d9c3ca090f978a4da4698ccaac29'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--epochs',type=float,default=3)
    parser.add_argument('--cpu',action='store_true')
    parser.add_argument('--evaluate-only',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    def run(module,*arguments):
        subprocess.run([sys.executable,'-m',module,*arguments],cwd=root,check=True)
    if not args.evaluate_only: run('ml.build_dataset')
    registry={}
    for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
        destination=f'models/{tenant}-{version}'
        registry[f'{tenant}/{version}']=destination
        if args.evaluate_only: continue
        run('ml.train_lora','--model',MODEL,'--revision',REVISION,
            '--train',f'data/{tenant}-{version}-train.jsonl',
            '--validation',f'data/{tenant}-{version}-validation.jsonl',
            '--output',destination,'--tenant',tenant,'--policy-version',version,
            '--epochs',str(args.epochs),*(['--cpu'] if args.cpu else []))
    if not args.evaluate_only: Path(root/'models/registry.json').write_text(json.dumps(registry,indent=2))
    for name,extra in [('baseline-model',[]),('lora-model',['--registry','models/registry.json'])]:
        run('ml.evaluate_model','--model',MODEL,'--revision',REVISION,
            '--output',f'artifacts/{name}.json','--cache',f'artifacts/model-cache-{name}.json',*extra,*(['--cpu'] if args.cpu else []))
        run('ml.evaluate_model','--model',MODEL,'--revision',REVISION,'--holdout',
            '--output',f'artifacts/{name}-holdout.json','--cache',f'artifacts/model-cache-{name}-holdout.json',*extra,*(['--cpu'] if args.cpu else []))
    run('ml.summarize_experiment')


if __name__=='__main__': main()
