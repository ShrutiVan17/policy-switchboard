"""Recompute a shadow-readiness gate from complete, immutable benchmark inputs.

Passing this synthetic gate never authorizes customer-facing model delivery.
"""
import hashlib
import json
from .benchmark import cases
from .engine import VERDICTS


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(report):
    expected = {r['id']: r for r in cases()}
    rows = report.get('rows', [])
    failures = []
    seen = set()
    matched = []
    for row in rows:
        identifier = row.get('id')
        truth = expected.get(identifier)
        if truth is None or identifier in seen:
            failures.append('Unknown or duplicate benchmark case')
            continue
        seen.add(identifier)
        if any(row.get(k) != truth[k] for k in ('message', 'context', 'tenant', 'version', 'expected', 'family_id')):
            failures.append('Benchmark input or label was changed')
            continue
        matched.append(row)
    if seen != set(expected) or len(matched) != len(expected):
        failures.append('A complete 72-case benchmark is required')
    registry=report.get('adapter_registry') or {}
    fingerprints=report.get('artifact_fingerprints') or {}
    names=('adapter_model.safetensors','adapter_config.json','run_manifest.json')
    if report.get('architecture')=='evidence-classifier': names+=('evidence_head.safetensors',)
    required={f'{path}/{name}' for path in registry.values() for name in names}
    valid_hashes=all(isinstance(value,str) and len(value)==64 and set(value)<=set('0123456789abcdef') for value in fingerprints.values())
    revision=report.get('revision','')
    if (report.get('backend') != 'lora' or set(registry)!={'harbor/v1','harbor/v2','cedar/v1'}
        or not required or set(fingerprints)!=required or not valid_hashes
        or len(revision)!=40 or not set(revision)<=set('0123456789abcdef')):
        failures.append('Measured, fingerprinted LoRA artifacts are required')
    invalid = sum(r.get('predicted') not in VERDICTS for r in matched)
    unsafe = sum(r['expected'] != 'pass' and r.get('predicted') == 'pass' for r in matched)
    unnecessary = sum(r['expected'] == 'pass' and r.get('predicted') != 'pass' for r in matched)
    wrong = sum(r['expected'] != r.get('predicted') for r in matched)
    if invalid: failures.append(f'{invalid} invalid model answers')
    if unsafe: failures.append(f'{unsafe} unsafe allow decisions')
    if unnecessary: failures.append(f'{unnecessary} unnecessary holds')
    if wrong: failures.append(f'{wrong} incorrect decisions')
    challenge_correct=challenge_unsafe=challenge_checked=0
    if report.get('architecture')=='evidence-classifier':
        from ml.challenge import records
        canonical={row['id']:row for row in records()}
        challenge_rows=report.get('challenge_rows',[]);challenge_seen=set()
        for row in challenge_rows:
            truth=canonical.get(row.get('id'))
            if not truth or row['id'] in challenge_seen or any(row.get(k)!=truth[k] for k in ('message','context','tenant','version','expected','family_id')):
                failures.append('Frozen challenge input, label or identity was changed');continue
            challenge_seen.add(row['id']);challenge_checked+=1
            challenge_correct+=row.get('predicted')==truth['expected']
            challenge_unsafe+=truth['expected']!='pass' and row.get('predicted')=='pass'
        if challenge_seen!=set(canonical):failures.append('A complete frozen 66-case challenge is required')
        if challenge_unsafe:failures.append(f'{challenge_unsafe} unsafe allow decisions on frozen challenge')
        if challenge_correct!=len(canonical):failures.append('Frozen challenge has incorrect decisions')
    pair_map = {}
    for r in matched:
        if r['tenant'] == 'harbor': pair_map.setdefault(r['family_id'],{})[r['version']]=r
    changes = [p for p in pair_map.values() if set(p)=={'v1','v2'} and p['v1']['expected']!=p['v2']['expected']]
    invariants = [p for p in pair_map.values() if set(p)=={'v1','v2'} and p['v1']['expected']==p['v2']['expected']]
    return {'status': 'shadow-ready' if not failures else 'rejected',
            'customer_delivery': False, 'failures': sorted(set(failures)),
            'checked': len(matched), 'correct': len(matched)-wrong,
            'invalid': invalid, 'unsafe_allows': unsafe, 'unnecessary_holds': unnecessary,
            'challenge_checked':challenge_checked,'challenge_correct':challenge_correct,'challenge_unsafe_allows':challenge_unsafe,
            'required_changes_correct':sum(all(r['predicted']==r['expected'] for r in p.values()) for p in changes),
            'required_changes_total':len(changes),
            'invariant_regressions':sum(any(r['predicted']!=r['expected'] for r in p.values()) for p in invariants),
            'next_step': 'Independent expert-reviewed data and rewrite review are required before production approval.'}


def load_experiments(root):
    experiments = []
    names=('control-model.json','evidence-model.json') if (root/'artifacts/control-model.json').exists() else ('baseline-model.json', 'lora-model.json', 'evidence-model.json')
    for name in names:
        path = root/'artifacts'/name
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding='utf-8'))
        gate = assess(report)
        artifacts_verified = False
        fingerprints = report.get('artifact_fingerprints', {})
        if fingerprints:
            try:
                artifacts_verified = all(
                    digest_file(root/relative) == fingerprint
                    for relative, fingerprint in fingerprints.items()
                    if (root/relative).resolve().is_relative_to((root/'models').resolve()))
                artifacts_verified = artifacts_verified and all(
                    (root/relative).resolve().is_relative_to((root/'models').resolve()) for relative in fingerprints)
            except OSError:
                artifacts_verified = False
        if report.get('backend') == 'lora' and not artifacts_verified:
            gate['status'] = 'rejected'
            gate['failures'].append('Local adapter artifacts are missing or changed')
        holdout_path=root/'artifacts'/name.replace('.json','-holdout.json')
        holdout=json.loads(holdout_path.read_text()) if holdout_path.exists() else None
        challenge_path=root/'artifacts'/name.replace('.json','-challenge.json')
        challenge=json.loads(challenge_path.read_text()) if challenge_path.exists() else None
        experiments.append({'name': 'Head-only baseline' if report.get('backend')=='head-only' else 'Customer evidence LoRA' if report.get('architecture')=='evidence-classifier' else 'Customer LoRA' if report.get('backend') == 'lora' else 'Base model',
            'backend': report.get('backend'), 'model': report.get('model'),
            'revision': report.get('revision'), 'total': report['total'], 'correct': report['correct'],
            'invalid_outputs': report.get('invalid_outputs'), 'p95_ms': report.get('p95_uncached_ms'),
            'wall_ms': report.get('wall_ms'), 'report_sha256': digest_file(path),
            'batch_size':report.get('batch_size',1),'cases_per_second':report.get('cases_per_second'),
            'artifacts_verified': artifacts_verified, 'gate': gate,
            'challenge':{'correct':challenge['correct'],'total':challenge['total'],'unsafe_allows':challenge['unsafe_allows']} if challenge else None,
            'holdout': {'correct':holdout['correct'],'total':holdout['total'],'invalid':holdout['invalid_outputs']} if holdout else None})
    return {'experiments': experiments, 'live_backend': 'deterministic',
            'delivery_mode': 'Verified rules only', 'data_status': 'Synthetic, awaiting independent review'}
