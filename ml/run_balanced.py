"""Train a decision-focused candidate while preserving the failed first experiment."""
import json
from pathlib import Path
import subprocess
import sys
from .run_experiment import MODEL,REVISION


def main():
    root=Path(__file__).resolve().parents[1]
    def run(module,*args): subprocess.run([sys.executable,'-m',module,*args],cwd=root,check=True)
    run('ml.build_balanced')
    registry={}
    for tenant,version in [('harbor','v2'),('harbor','v1'),('cedar','v1')]:
        path=f'models/balanced-{tenant}-{version}'
        run('ml.train_lora','--model',MODEL,'--revision',REVISION,'--tenant',tenant,'--policy-version',version,
            '--train',f'data-v2/{tenant}-{version}-train.jsonl','--validation',f'data-v2/{tenant}-{version}-validation.jsonl',
            '--output',path,'--epochs','3','--verdict-weight','20')
        registry[f'{tenant}/{version}']=path
    (root/'models/registry-balanced.json').write_text(json.dumps(registry,indent=2))
    run('ml.evaluate_model','--model',MODEL,'--revision',REVISION,'--registry','models/registry-balanced.json',
        '--output','artifacts/balanced-model.json','--cache','artifacts/model-cache-balanced.json')


if __name__=='__main__': main()
