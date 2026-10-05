import copy
import hashlib
import json
import unittest
from unittest.mock import patch
from switchboard.evals import run
from switchboard.release_gate import assess


class ReleaseGateTests(unittest.TestCase):
    def test_batches_never_mix_customer_or_policy(self):
        from ml.evaluate_model import policy_batches
        from switchboard.benchmark import cases
        batches=policy_batches(cases(),8)
        self.assertEqual(sum(len(b) for b in batches),72)
        self.assertEqual(len({r['id'] for b in batches for r in b}),72)
        for batch in batches:
            self.assertLessEqual(len(batch),8)
            self.assertEqual(len({(r['tenant'],r['version']) for r in batch}),1)
    def test_dataset_manifest_hashes_actual_cross_platform_bytes(self):
        from ml.build_dataset import build
        from test_switchboard import local_temp
        with local_temp() as directory:
            counts=build(directory)
            for name,metadata in counts.items():
                self.assertEqual(metadata['sha256'],hashlib.sha256((directory/name).read_bytes()).hexdigest())

    def test_secret_is_blocked_before_model_loading(self):
        from ml.runtime import shadow
        with patch('ml.runtime.load',side_effect=AssertionError('Must not load AI for secrets')) as loader:
            result=shadow('My API key is sk-demo123456789',{},'harbor','v1')
        self.assertFalse(loader.called)
        self.assertEqual(result['model_verdict'],'not-run')
        self.assertIsNone(result['delivered_output'])

    def test_model_json_rejects_duplicate_or_extra_authority(self):
        from ml.evaluate_model import parse_decision
        for text in ('{"verdict":"block","verdict":"pass","policy_ids":[],"reason":"x","proposed_output":null}',
                     '{"verdict":"pass","policy_ids":[],"reason":"x","proposed_output":null,"approved":true}',
                     '{"verdict":"pass","policy_ids":[],"reason":"x"}'):
            with self.assertRaises(ValueError): parse_decision(text)

    def candidate(self):
        report = run()
        registry={key:f'models/{key.replace("/","-")}' for key in ('harbor/v1','harbor/v2','cedar/v1')}
        report.update(backend='lora',adapter_registry=registry,revision='a'*40,
            artifact_fingerprints={f'{path}/{name}':'a'*64 for path in registry.values()
                for name in ('adapter_model.safetensors','adapter_config.json','run_manifest.json')})
        return report

    def test_rules_cannot_masquerade_as_trained_model(self):
        self.assertEqual(assess(run())['status'], 'rejected')

    def test_perfect_synthetic_scores_only_allow_shadow(self):
        gate = assess(self.candidate())
        self.assertEqual(gate['status'], 'shadow-ready')
        self.assertFalse(gate['customer_delivery'])

    def test_fail_closed_when_model_allows_violation(self):
        report = self.candidate()
        row = next(r for r in report['rows'] if r['expected'] == 'block')
        row['predicted'] = 'pass'
        self.assertEqual(assess(report)['unsafe_allows'], 1)
        self.assertEqual(assess(report)['status'], 'rejected')

    def test_reject_partial_duplicate_and_changed_truth(self):
        report = self.candidate()
        for alter in ('partial', 'duplicate', 'label'):
            changed = copy.deepcopy(report)
            if alter == 'partial': changed['rows'].pop()
            if alter == 'duplicate': changed['rows'][-1] = changed['rows'][0]
            if alter == 'label': changed['rows'][0]['expected'] = 'block'
            self.assertEqual(assess(changed)['status'], 'rejected')

    def test_claimed_perfect_summary_cannot_hide_invalid_answer(self):
        report = self.candidate()
        report['rows'][0]['predicted'] = 'invalid'
        self.assertEqual(assess(report)['invalid'], 1)
        self.assertEqual(assess(report)['status'], 'rejected')

    def test_frozen_challenge_can_block_a_perfect_smoke_score(self):
        from ml.challenge import records
        report=self.candidate();report['architecture']='evidence-classifier'
        for path in report['adapter_registry'].values():report['artifact_fingerprints'][f'{path}/evidence_head.safetensors']='a'*64
        report['challenge_rows']=[{**r,'predicted':r['expected']} for r in records()]
        self.assertEqual(assess(report)['status'],'shadow-ready')
        row=next(r for r in report['challenge_rows'] if r['expected']=='block');row['predicted']='pass'
        self.assertEqual(assess(report)['status'],'rejected')
        self.assertEqual(assess(report)['challenge_unsafe_allows'],1)
        row['expected']='pass'
        self.assertEqual(assess(report)['status'],'rejected')
