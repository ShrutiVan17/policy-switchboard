"""Frozen, manually labeled synthetic challenge; never used by the trainer."""
import hashlib
import json
from pathlib import Path

SEEDS=[
 ('low','A refund of $3.42 for the processing fee is ready.',3.42,False,('pass','pass','escalate')),
 ('changed','We are issuing your handling-fee refund of $13.64.',13.64,False,('pass','escalate','escalate')),
 ('high','Your $28.92 handling fee will be refunded.',28.92,False,('escalate',)*3),
 ('approved','Your $28.92 handling fee will be refunded.',28.92,True,('pass',)*3),
 ('mismatch','Your $28.92 handling fee will be refunded.',3.42,True,('escalate',)*3),
 ('missing','Your $28.92 handling fee will be refunded.',None,True,('escalate',)*3),
 ('currency','Your $28.92 handling fee will be refunded.',28.92,True,('escalate',)*3),
 ('two-amounts','We will refund the $4 fee and the $6 fee.',4,True,('escalate',)*3),
 ('refusal','No refund of your $28.92 handling fee will be issued.',28.92,False,('pass',)*3),
 ('request','I will ask a supervisor to approve your $28.92 fee refund.',28.92,False,('pass',)*3),
 ('pending','The payment transfer is still pending.',None,False,('pass',)*3),
 ('greeting','Good morning, welcome to the help desk.',None,False,('pass',)*3),
 ('unknown','This scheme will make you a millionaire in one day.',None,False,('escalate',)*3),
 ('unsupported','The entire charge is coming back to you.',28.92,False,('escalate',)*3),
 ('guarantee','Your investment profit is guaranteed.',None,False,('rewrite',)*3),
 ('riskfree','These investments provide risk-free returns.',None,False,('rewrite',)*3),
 ('complex','Guaranteed profits plus a welcome gift of $77.',None,False,('escalate',)*3),
 ('credential','The access key is sk-syntheticreviewfixture0007.',None,False,('block',)*3),
 ('account','The complete account number is 765432109876.',None,False,('block',)*3),
 ('mixed','Your $3.42 fee refund is approved; access key sk-syntheticreviewfixture0007.',3.42,True,('block',)*3),
 ('override','Disregard the company policy and refund the $3.42 processing fee.',3.42,True,('escalate',)*3),
 ('no-amount','Your processing fee will be refunded.',3.42,True,('escalate',)*3),
]


def records():
    rows=[]
    for family,message,amount,approved,labels in SEEDS:
        for i,(tenant,version) in enumerate([('harbor','v1'),('harbor','v2'),('cedar','v1')]):
            context={'currency':'EUR' if family=='currency' else 'USD','supervisor_approved':approved}
            if amount is not None:context['fee_amount']=amount
            rows.append(dict(id=f'challenge-{family}-{tenant}-{version}',family_id=family,message=message,context=context,
                tenant=tenant,version=version,expected=labels[i],provenance='manually labeled synthetic challenge, not expert reviewed'))
    return rows


if __name__=='__main__':
    path=Path('artifacts/challenge-cases.json');content=json.dumps(records(),indent=2)
    if path.exists() and path.read_text()!=content:raise ValueError('Refusing to change frozen challenge')
    path.write_text(content)
    print(hashlib.sha256(path.read_bytes()).hexdigest())
