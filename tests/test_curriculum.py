import json
import unittest
from ml.build_balanced import build
from test_switchboard import local_temp


class CurriculumTests(unittest.TestCase):
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
