"""Compare joint probabilities of complete verdicts, not greedy token prefixes."""
from .constrained import LABELS,PREFIX


def score(model,tokenizer,texts,device):
    import torch
    suffixes=[tokenizer.encode(label+'"',add_special_tokens=False) for label in LABELS]
    prefixes=[tokenizer.encode(text+PREFIX,add_special_tokens=False) for text in texts]
    sequences=[prefix+suffix for prefix in prefixes for suffix in suffixes]
    width=max(map(len,sequences))
    keep=max(map(len,suffixes))+1
    ids=torch.full((len(sequences),width),tokenizer.eos_token_id,dtype=torch.long,device=device)
    mask=torch.zeros_like(ids)
    for index,sequence in enumerate(sequences):
        ids[index,-len(sequence):]=torch.tensor(sequence,device=device)
        mask[index,-len(sequence):]=1
    with torch.inference_mode():
        output=model(input_ids=ids,attention_mask=mask,use_cache=False,logits_to_keep=keep)
        logits=output.logits.float().log_softmax(dim=-1)
        joint=[]
        for row in range(len(sequences)):
            suffix=suffixes[row%len(LABELS)]
            start=logits.shape[1]-len(suffix)-1
            joint.append(sum(logits[row,start+i,token] for i,token in enumerate(suffix)))
        joint=torch.stack(joint).reshape(len(texts),len(LABELS))
        probabilities=joint.softmax(dim=-1)
    results=[]
    for row in probabilities:
        if not torch.isfinite(row).all():
            results.append({'predicted':'invalid','confidence':None,'probabilities':None})
            continue
        values=row.tolist()
        winner=max(range(len(LABELS)),key=lambda i:values[i])
        results.append({'predicted':LABELS[winner],'confidence':values[winner],
            'probabilities':dict(zip(LABELS,values))})
    return results


def calibration(rows):
    usable=[r for r in rows if r.get('probabilities')]
    if not usable:return {'ece':None,'brier':None,'cases':0}
    brier=sum(sum((r['probabilities'][label]-int(r['expected']==label))**2 for label in LABELS) for r in usable)/len(usable)
    ece=0
    for index in range(10):
        bucket=[r for r in usable if min(9,int(r['confidence']*10))==index]
        if bucket:
            accuracy=sum(r['predicted']==r['expected'] for r in bucket)/len(bucket)
            confidence=sum(r['confidence'] for r in bucket)/len(bucket)
            ece+=len(bucket)/len(usable)*abs(accuracy-confidence)
    return {'ece':round(ece,6),'brier':round(brier,6),'cases':len(usable),
        'caveat':'Conditional verdict probabilities; synthetic reliability estimate, not a compliance guarantee.'}
