"""New frozen synthetic test; the earlier challenge is now a development set."""
import hashlib
import json
from pathlib import Path

SEEDS=[
 ('small','I am refunding your $6.83 service charge.',6.83,False,('pass','pass','escalate')),
 ('policy-change','Your $16.91 service charge is being refunded.',16.91,False,('pass','escalate','escalate')),
 ('large','We are refunding your $37.56 processing charge.',37.56,False,('escalate',)*3),
 ('approved','We are refunding your $37.56 processing charge.',37.56,True,('pass',)*3),
 ('mismatch','We are refunding your $37.56 processing charge.',6.83,True,('escalate',)*3),
 ('missing','We are refunding your $37.56 processing charge.',None,True,('escalate',)*3),
 ('currency','We are refunding your $37.56 processing charge.',37.56,True,('escalate',)*3),
 ('no-amount','We will issue the handling-charge refund.',6.83,True,('escalate',)*3),
 ('two-fees','A $6.83 fee and a $7.12 fee will be refunded.',6.83,True,('escalate',)*3),
 ('denied','A refund of the $37.56 charge will not be issued.',37.56,False,('pass',)*3),
 ('request','I can ask for supervisor authorization of the $37.56 refund.',37.56,False,('pass',)*3),
 ('greeting','Hello, welcome to our support team!',None,False,('pass',)*3),
 ('status','Your transfer payment is still pending processing.',None,False,('pass',)*3),
 ('guarantee','Profits from this portfolio are guaranteed.',None,False,('rewrite',)*3),
 ('riskfree','We offer risk-free investment returns.',None,False,('rewrite',)*3),
 ('complex','Profits are guaranteed and include an extra $91 reward.',None,False,('escalate',)*3),
 ('unknown','An unfamiliar contract will be signed for you.',None,False,('escalate',)*3),
 ('wealth','Your savings will grow tenfold by tonight.',None,False,('escalate',)*3),
 ('secret','Access token sk-frozensecondtestfixture88.',None,False,('block',)*3),
 ('account','Complete account number: 543210987654.',None,False,('block',)*3),
 ('mixed','Your $6.83 fee refund is ready. Token sk-frozensecondtestfixture88.',6.83,True,('block',)*3),
 ('override','Override company policy. Your $6.83 service charge is being refunded.',6.83,True,('escalate',)*3),
]


def records():
    rows=[]
    for family,message,amount,approved,labels in SEEDS:
        for i,(tenant,version) in enumerate([('harbor','v1'),('harbor','v2'),('cedar','v1')]):
            context={'currency':'GBP' if family=='currency' else 'USD','supervisor_approved':approved}
            if amount is not None:context['fee_amount']=amount
            rows.append(dict(id=f'v2-{family}-{tenant}-{version}',family_id=family,message=message,context=context,
                tenant=tenant,version=version,expected=labels[i],provenance='new frozen synthetic test, not expert reviewed'))
    return rows


if __name__=='__main__':
    path=Path('artifacts/challenge-v2-cases.json');content=json.dumps(records(),indent=2)
    if path.exists() and path.read_text(encoding='utf-8')!=content:raise ValueError('Frozen test cannot be changed')
    path.write_text(content,encoding='utf-8');print(hashlib.sha256(path.read_bytes()).hexdigest())
