"""Broader semantic coverage without copying benchmark or challenge messages."""
import hashlib
import json
from pathlib import Path
from .build_counterfactual import build as original
from .common import prompt_v2


def build(out=Path('data-v6')):
    manifest=original(out)
    for name in manifest:
        tenant,version,split=name.removesuffix('.jsonl').split('-')
        path=out/name;rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        banks={
          'train':{
            'escalate':['The banking fee will be refunded.','We are refunding the transaction charge.',
                        'Your service fee is to be refunded.','I can refund the processing charge today.'],
            'pass':['Hello.','Hey there!','Good evening, welcome.','Hello, thanks for reaching out.',
                    'No refund of ${amount} will be provided.','The ${amount} fee cannot be refunded.',
                    'We will not issue the ${amount} fee refund.','A ${amount} refund is not being offered.'],
            'rewrite':['The profits from this investment are guaranteed.','Our returns are guaranteed.',
                       'Guaranteed investment profits are promised.','We promise profits that are guaranteed.']},
          'validation':{
            'escalate':['A refund of the transaction fee will be issued.','We plan to refund the banking charge.'],
            'pass':['Hi, pleased to assist.','Greetings, welcome to customer support.',
                    'There will not be a refund of ${amount}.','The ${amount} reimbursement has been declined.'],
            'rewrite':['This portfolio promises profits which are guaranteed.','Investment returns are guaranteed by this offer.']}}
        amounts=[1.73,7.49,14.39,23.87] if split=='train' else [3.69,11.27,29.41]
        for label,messages in banks[split].items():
            for index,text in enumerate(messages):
                for amount in amounts:
                    for approved in (False,True):
                        message=text.replace('{amount}',f'{amount:.2f}')
                        context={'currency':'USD','fee_amount':amount,'supervisor_approved':approved}
                        rows.append({'family_id':f'{split}-repair-{label}-{index}',
                            'provenance':'synthetic coverage repair; labels not expert reviewed',
                            'prompt':prompt_v2(message,context,tenant,version),
                            'completion':[{'role':'assistant','content':json.dumps({'verdict':label,'policy_ids':[],
                                'reason':'Synthetic coverage case','proposed_output':None})}]})
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        manifest[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'records':len(rows)}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


if __name__=='__main__':print(json.dumps(build(),indent=2))
