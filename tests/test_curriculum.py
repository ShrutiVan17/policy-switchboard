import json
import unittest
from ml.build_balanced import build
from test_switchboard import local_temp


class CurriculumTests(unittest.TestCase):
    def test_reliability_scores_expose_overconfident_errors(self):
        from ml.verdict_scorer import calibration
        correct={'expected':'pass','predicted':'pass','confidence':1.0,'probabilities':{'pass':1.,'rewrite':0.,'block':0.,'escalate':0.}}
        self.assertEqual(calibration([correct])['brier'],0)
        self.assertEqual(calibration([correct])['ece'],0)
        wrong={**correct,'expected':'block'}
        self.assertEqual(calibration([wrong])['brier'],2)
        self.assertEqual(calibration([wrong])['ece'],1)
    def test_policy_prompt_normalizes_equivalent_amounts(self):
        from ml.common import prompt_v2
        contexts=[{'fee_amount':a,'currency':'USD','supervisor_approved':False} for a in (15,15.0,'15.00')]
        rendered=[prompt_v2('A refund message.',c,'harbor','v2') for c in contexts]
        self.assertEqual(rendered[0],rendered[1])
        self.assertEqual(rendered[1],rendered[2])
        self.assertIn('Missing or mismatched amounts',rendered[0][0]['content'])
    def test_constrained_decoder_only_allows_four_verdicts(self):
        from ml.constrained import build_trie,allowed,classify_text,LABELS
        class CharacterTokenizer:
            def encode(self,text,add_special_tokens=False): return list(text.encode())
        trie=build_trie(CharacterTokenizer())
        self.assertEqual(set(allowed(trie,[],999)),{ord(c[0]) for c in LABELS})
        for label in LABELS:
            tokens=list((label+'"').encode())
            for i,token in enumerate(tokens): self.assertIn(token,allowed(trie,tokens[:i],999))
            self.assertEqual(allowed(trie,tokens,999),[999])
            self.assertEqual(classify_text(label+'"'),label)
        self.assertEqual(classify_text('pass malicious'), 'invalid')

    def test_balanced_classes_and_distinct_family_splits(self):
        with local_temp() as path:
            manifest=build(path)
            self.assertEqual(len(manifest),6)
            for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
                families=[]
                for split in ('train','validation'):
                    metadata=manifest[f'{tenant}-{version}-{split}.jsonl']
                    self.assertEqual(len(set(metadata['labels'].values())),1)
                    rows=[json.loads(line) for line in (path/f'{tenant}-{version}-{split}.jsonl').read_text().splitlines()]
                    families.append({r['family_id'] for r in rows})
                self.assertFalse(families[0]&families[1])
