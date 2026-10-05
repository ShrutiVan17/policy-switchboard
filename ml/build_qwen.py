"""The same independent curriculum with an explicit, versioned policy contract."""
import hashlib
import json
from pathlib import Path
from .build_balanced import build
from .common import prompt_v2
from switchboard.engine import resolve


def main():
    out=Path('data-v3')
    manifest=build(out)
    for name in manifest:
        path=out/name
        tenant,version,_=name.removesuffix('.jsonl').split('-')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        policy=resolve(tenant,version)
        for index,row in enumerate(rows):
            data=json.loads(row['prompt'][1]['content'])
            label=json.loads(row['completion'][0]['content'])['verdict']
            i=index%(36 if name.endswith('train.jsonl') else 12)
            context=data['trusted_context']
            wording='We can refund the ${amount} service fee.' if name.endswith('train.jsonl') else 'I will issue a ${amount} service-fee refund.'
            if label=='pass' and i%4 in (2,3):
                approved=policy.all_refunds_require_approval or i%4==2
                allowed_amounts=[.01,1,min(5,policy.limit),max(.01,policy.limit/2),max(.01,policy.limit-.01),max(.01,policy.limit)]
                amount=policy.limit+1+(i%9) if i%4==2 else allowed_amounts[(i//4)%len(allowed_amounts)]
                if policy.all_refunds_require_approval: amount=5+i%9
                context.update(fee_amount=amount,supervisor_approved=approved)
                data['message']=wording.format(amount=f'{amount:.2f}')
            elif label=='escalate':
                amount=policy.limit+(.01 if i%8==0 else 1+i%9)
                context.update(fee_amount=amount,supervisor_approved=False)
                if i%4==0: data['message']=wording.format(amount=f'{amount:.2f}')
                elif i%4==1:
                    data['message']=wording.format(amount=f'{amount:.2f}')
                    context.update(fee_amount=amount+10,supervisor_approved=True)
                if i%8==3: data['message']='I can refund the fee now.'
                elif i%8==4:
                    data['message']=wording.format(amount=f'{amount:.2f}');context.pop('fee_amount',None)
                elif i%8==5:
                    data['message']=f'Guaranteed investment returns plus a cash bonus of ${30+i}.'
                    context.pop('fee_amount',None)
                elif i%8==6:
                    data['message']='Our plan multiplies your balance very quickly.' if name.endswith('train.jsonl') else 'You will become rich by next week.'
                    context.pop('fee_amount',None)
                elif i%8==7:
                    data['message']='Please decide an unfamiliar agreement.' if name.endswith('train.jsonl') else 'Make a commitment about an unknown contract.'
                    context.pop('fee_amount',None)
            elif label=='block' and i%4==2:
                data['message']=f"We can refund the $5 fee. Access credential: sk-{tenant}{name[:3]}{i:04d}safe."
                context.update(fee_amount=5,supervisor_approved=True)
            elif label=='rewrite' and i%2==1:
                data['message']='This investment promises risk-free returns.' if name.endswith('train.jsonl') else 'Risk-free investment returns are promised.'
            if label=='pass' and i%8==5:
                data['message']=f'We cannot refund the ${25+i} service fee.' if name.endswith('train.jsonl') else f'I am not promising a ${25+i} fee refund.'
                context.update(fee_amount=25+i,supervisor_approved=False)
            row['prompt']=prompt_v2(data['message'],data['trusted_context'],tenant,version)
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        manifest[name]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[name]['prompt_version']='2'
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))


if __name__=='__main__': main()
