"""Measure the hybrid encoder on unchanged smoke cases and synthetic validation."""
import json
import time
import argparse
from .evidence_runtime import ROOT, predict
from .constrained import LABELS
from .verdict_scorer import calibration
from switchboard.benchmark import cases
from switchboard.evals import summarize
from switchboard.release_gate import assess, digest_file


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',default='data-v3')
    parser.add_argument('--model-prefix',choices=['evidence','control','candidate'],default='evidence');args=parser.parse_args()
    prefix=args.model_prefix
    registry={f'{t}/{v}':f'models/{prefix}-{t}-{v}' for t,v in [('harbor','v1'),('harbor','v2'),('cedar','v1')]}
    for key,path in registry.items():
        tenant,version=key.split('/')
        manifest=json.loads((ROOT/path/'run_manifest.json').read_text(encoding='utf-8'))
        for split,field in [('train','training_sha256'),('validation','validation_sha256')]:
            if digest_file(ROOT/f'{args.data_dir}/{tenant}-{version}-{split}.jsonl')!=manifest[field]:
                raise ValueError('Evaluation dataset does not match the trained manifest')
    # Warm each provisioned model; report latency without cold checkpoint loading.
    for key in registry:
        t,v=key.split('/');predict('Hello, how can I help?',{},t,v,prefix)
    def evaluate(records):
        start=time.perf_counter(); rows=[]
        for row in records:
            result=predict(row['message'],row['context'],row['tenant'],row['version'],prefix)
            rows.append({**row,'predicted':result['model_verdict'],'confidence':result['confidence'],
                         'probabilities':dict(zip(LABELS,result['probabilities'])),'latency_ms':result['latency_ms'],'cache_hit':False})
        report=summarize(rows,time.perf_counter()-start,backend='head-only' if prefix=='control' else 'lora')
        report.update(model='sentence-transformers/all-MiniLM-L6-v2',revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
                      architecture='evidence-classifier',adapter_registry=registry,batch_size=1,
                      dataset_revision=args.data_dir,
                      invalid_outputs=sum(r['predicted'] not in LABELS for r in rows),calibration=calibration(rows),
                      limitations='Synthetic examples. Explicit numeric and approval facts are computed outside the model; this measures the combined classifier, not learned arithmetic. Validation was monitored during training. Rewrite quality and independent compliance accuracy are unverified.')
        report['artifact_fingerprints']={f'{path}/{name}':digest_file(ROOT/path/name) for path in registry.values()
            for name in ('adapter_model.safetensors','adapter_config.json','run_manifest.json','evidence_head.safetensors')}
        return report
    report=evaluate(cases());report['gate']=assess(report)
    (ROOT/f'artifacts/{prefix}-model.json').write_text(json.dumps(report,indent=2))
    validation=[];overlap=0
    for key in registry:
        tenant,version=key.split('/')
        train=[json.loads(x) for x in (ROOT/f'{args.data_dir}/{tenant}-{version}-train.jsonl').read_text().splitlines()]
        train_text={json.loads(x['prompt'][1]['content'])['message'] for x in train}
        for i,line in enumerate((ROOT/f'{args.data_dir}/{tenant}-{version}-validation.jsonl').read_text().splitlines()):
            row=json.loads(line); source=json.loads(row['prompt'][1]['content'])
            overlap+=source['message'] in train_text
            validation.append(dict(id=f'{key}-{i}',tenant=tenant,version=version,family_id=row['family_id'],
                                   message=source['message'],context=source['trusted_context'],expected=json.loads(row['completion'][0]['content'])['verdict']))
    holdout=evaluate(validation);holdout.update(benchmark='synthetic-monitored-validation-'+args.data_dir,exact_message_overlap_with_training=overlap)
    (ROOT/f'artifacts/{prefix}-model-holdout.json').write_text(json.dumps(holdout,indent=2))
    challenge_path=ROOT/'artifacts/challenge-cases.json'
    if challenge_path.exists():
        challenge=evaluate(json.loads(challenge_path.read_text()));challenge['benchmark']='frozen-synthetic-challenge-v1'
        challenge['case_file_sha256']=digest_file(challenge_path)
        challenge['limitations']='Earlier challenge is now a development regression set for v6. No expert review.' if args.data_dir=='data-v6' else 'Frozen synthetic challenge; not used for training or epoch selection. No independent expert review.'
        challenge['unsafe_allows']=sum(r['expected']!='pass' and r['predicted']=='pass' for r in challenge['rows'])
        (ROOT/f'artifacts/{prefix}-model-challenge.json').write_text(json.dumps(challenge,indent=2))
        report['challenge_rows']=challenge['rows'];report['challenge_sha256']=digest_file(challenge_path)
        report['gate']=assess(report)
        (ROOT/f'artifacts/{prefix}-model.json').write_text(json.dumps(report,indent=2))
    test_path=ROOT/'artifacts/challenge-v2-cases.json'
    if args.data_dir=='data-v6' and test_path.exists():
        test=evaluate(json.loads(test_path.read_text(encoding='utf-8')))
        test.update(benchmark='frozen-synthetic-test-v2',case_file_sha256=digest_file(test_path),
                    limitations='New synthetic test frozen before v6 training; not used for training, epoch selection or subsequent tuning.')
        test['unsafe_allows']=sum(r['expected']!='pass' and r['predicted']=='pass' for r in test['rows'])
        (ROOT/f'artifacts/{prefix}-model-test.json').write_text(json.dumps(test,indent=2))
        report['test_rows']=test['rows'];report['test_sha256']=digest_file(test_path);report['evaluation_protocol']='development-v1/frozen-test-v2'
        report['gate']=assess(report);(ROOT/f'artifacts/{prefix}-model.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'smoke_correct':report['correct'],'total':report['total'],'p95_ms':report['p95_uncached_ms'],
                      'gate':report['gate'],'validation_correct':holdout['correct'],'validation_total':holdout['total'],'message_overlap':overlap},indent=2))


if __name__=='__main__':main()
