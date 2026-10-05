"""Create a small, shareable report from actual completed runs."""
from datetime import datetime, timezone
import json
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    manifests={}
    for path in (root/'models').glob('*/run_manifest.json'):
        manifests[path.parent.name]=json.loads(path.read_text())
    (root/'artifacts/training-runs.json').write_text(json.dumps(manifests,indent=2),encoding='utf-8')
    lines=['# Measured model experiment','',f"Generated from completed runs: {datetime.now(timezone.utc).isoformat()}",'',
        'All inputs are fictional. Scores measure this experiment, not regulatory compliance.','',
        '| Run | Correct | Invalid JSON | Unsafe allows | Batch p95 uncached |',
        '| --- | --- | --- | --- | --- |']
    for filename in ('baseline-model.json','lora-model.json','baseline-model-holdout.json','lora-model-holdout.json'):
        path=root/'artifacts'/filename
        if not path.exists(): continue
        report=json.loads(path.read_text())
        unsafe=sum(r['expected']!='pass' and r['predicted']=='pass' for r in report['rows'])
        latency=report['p95_uncached_ms']
        lines.append(f"| [{filename}](../artifacts/{filename}) | {report['correct']}/{report['total']} | {report['invalid_outputs']} | {unsafe} | {latency:.1f} ms |")
    lines+=['','## Training','',
        '| Adapter | Epochs | Training wall time | Hardware |','| --- | --- | --- | --- |']
    for name,manifest in manifests.items():
        lines.append(f"| {name} | {manifest['epochs']} | {manifest['wall_seconds']:.1f} s | {manifest['hardware']} |")
    lines+=['','Weight, policy, dataset and software identities are in [training manifests](../artifacts/training-runs.json).',
        '', 'The smoke suite includes schema seeds overlapping training. The 132-case wording holdout excludes entire refund template families from training; labels remain synthetic and unreviewed.',
        '', 'The base is SmolLM2-135M-Instruct at immutable revision `02e84e7cc564d9c3ca090f978a4da4698ccaac29`. It is much smaller than the model described by ZeroDrift.',
        '', 'Gate results are in each smoke report. Incorrect or invalid decisions reject shadow readiness. Passing synthetic tests alone never authorizes customer delivery.',
        '', 'Offline inference uses homogeneous tenant/policy batches of up to 8. The reported p95 measures whole-batch completion, not individual interactive-request latency. Timings exclude model loading and presentation animation. Training wall time is measured elapsed time, including interruptions; it is not billed GPU time. Dollar costs are unknown.']
    adapted=root/'artifacts/lora-model.json'
    if adapted.exists():
        report=json.loads(adapted.read_text())
        lines+=['','## Release decision','',str(report['release_gate']['status']),
            '', '; '.join(report['release_gate'].get('failures',[])) or 'Synthetic gate passed; expert review is still required.',
            '', '## Example errors','', '| Family | Customer/policy | Expected | Model |', '| --- | --- | --- | --- |']
        for row in [r for r in report['rows'] if r['expected']!=r['predicted']][:12]:
            lines.append(f"| {row['family_id']} | {row['tenant']}/{row['version']} | {row['expected']} | {row['predicted']} |")
        if len({r['predicted'] for r in report['rows']})==1:
            lines+=['','## Failure analysis','',
                'The adapted model collapsed to a single decision class. Better JSON validity and low token-level validation loss did not establish policy discrimination. The release gate catches this through unsafe-allow counts and required-change pairs.',
                '', 'The next controlled experiment should emphasize verdict loss, balance decision families, standardize numeric representations, expand safety/unknown examples and compare a stronger checkpoint. These are proposed experiments, not completed results. A separate independently reviewed test set is still required.']
    (root/'docs/MODEL_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__': main()
