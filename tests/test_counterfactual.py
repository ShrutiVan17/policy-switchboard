import json
import unittest
from ml.build_counterfactual import build
from ml.evidence_features import features
from ml.challenge import records
from switchboard.benchmark import cases
from test_switchboard import local_temp


class CounterfactualTests(unittest.TestCase):
    def test_partial_adapter_promotion_rolls_back_all_customers(self):
        from pathlib import Path
        from unittest.mock import patch
        from ml.repair_models import activate
        with local_temp() as root:
            moves=[]
            for name in ('first','second'):
                active=root/f'{name}-active';candidate=root/f'{name}-candidate';archive=root/f'{name}-archive'
                active.mkdir();candidate.mkdir()
                (active/'value').write_text('old');(candidate/'value').write_text('new')
                moves.append((active,archive,candidate))
            original=Path.rename
            def rename(path,target):
                if path==moves[1][2]:raise OSError('Simulated interrupted activation')
                return original(path,target)
            try:
                with patch.object(Path,'rename',rename),self.assertRaises(OSError):activate(moves,root)
                for active,archive,candidate in moves:
                    self.assertEqual((active/'value').read_text(),'old')
                    self.assertEqual((candidate/'value').read_text(),'new')
                    self.assertFalse(archive.exists())
            finally:
                for active,archive,candidate in moves:
                    for folder in (active,archive,candidate):
                        if folder.exists():(folder/'value').unlink();folder.rmdir()
    def test_repaired_data_keeps_new_frozen_test_unseen(self):
        from ml.build_repaired import build as repaired
        from ml.challenge_v2 import records as fresh
        reserved={r['message'] for r in cases()+records()+fresh()}
        with local_temp() as out:
            repaired(out)
            for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
                def texts(split):return {json.loads(json.loads(line)['prompt'][1]['content'])['message']
                    for line in (out/f'{tenant}-{version}-{split}.jsonl').read_text(encoding='utf-8').splitlines()}
                self.assertFalse(texts('train')&reserved)
                self.assertFalse(texts('train')&texts('validation'))
    def test_money_identity_approval_and_tenant_features(self):
        context={'currency':'USD','fee_amount':13.64,'supervisor_approved':False}
        self.assertEqual(features('Refund $13.64.',context,'harbor','v1'),[0.,1.,1.,1.,1.,0.])
        self.assertEqual(features('Refund $13.64.',context,'harbor','v2')[-2:], [0.,0.])
        self.assertEqual(features('Refund $13.64.',context,'cedar','v1')[-2:], [0.,1.])
        self.assertEqual(features('Refund $3.42.',{**context,'supervisor_approved':True},'harbor','v1')[3],0.)

    def test_no_exact_training_validation_smoke_or_challenge_overlap(self):
        reserved={r['message'] for r in cases()+records()}
        with local_temp() as out:
            build(out)
            for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
                def read(split):
                    return [json.loads(r) for r in (out/f'{tenant}-{version}-{split}.jsonl').read_text().splitlines()]
                train,validation=read('train'),read('validation')
                texts=lambda rows:{json.loads(r['prompt'][1]['content'])['message'] for r in rows}
                self.assertFalse(texts(train)&texts(validation))
                self.assertFalse(texts(train)&reserved)
                self.assertFalse({r['family_id'] for r in train}&{r['family_id'] for r in validation})
                grouped={}
                for row in train:
                    data=json.loads(row['prompt'][1]['content']);label=json.loads(row['completion'][0]['content'])['verdict']
                    grouped.setdefault(data['message'],set()).add(label)
                self.assertTrue(any(labels=={'pass','escalate'} for labels in grouped.values()))
