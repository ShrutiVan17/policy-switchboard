"""Direct verdict training with a head-only control and genuine encoder LoRA."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from .checkpoints import local_source
from .constrained import LABELS
from .evidence_features import features
from switchboard.engine import resolve


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',required=True);p.add_argument('--revision',required=True)
    p.add_argument('--tenant',required=True);p.add_argument('--policy-version',required=True)
    p.add_argument('--train',required=True);p.add_argument('--validation',required=True);p.add_argument('--output',required=True)
    p.add_argument('--epochs',type=int,default=30);p.add_argument('--head-only',action='store_true')
    args=p.parse_args()
    import torch
    from transformers import AutoModel,AutoTokenizer,set_seed
    from peft import LoraConfig,get_peft_model
    from safetensors.torch import save_file
    from .evidence_model import EvidenceModel
    set_seed(42);torch.set_num_threads(2)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    source=local_source(args.model,args.revision)
    tokenizer=AutoTokenizer.from_pretrained(source,trust_remote_code=False)
    base=AutoModel.from_pretrained(source,trust_remote_code=False,attn_implementation='eager')
    encoder=get_peft_model(base,LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,bias='none',task_type='FEATURE_EXTRACTION',target_modules=['query','value']))
    if args.head_only:
        for parameter in encoder.parameters():parameter.requires_grad=False
    model=EvidenceModel(encoder,base.config.hidden_size).to(device)
    families={}
    def read(path,split):
        records=[json.loads(line) for line in Path(path).read_text().splitlines()]
        families[split]={row['family_id'] for row in records}
        parsed=[json.loads(row['prompt'][1]['content']) for row in records]
        tokens=tokenizer([row['message'] for row in parsed],padding=True,return_tensors='pt',add_special_tokens=True)
        if tokens['input_ids'].shape[-1]>128:raise ValueError('Message exceeds the semantic model limit')
        facts=torch.tensor([features(row['message'],row['trusted_context'],args.tenant,args.policy_version) for row in parsed],dtype=torch.float32)
        truth=torch.tensor([LABELS.index(json.loads(row['completion'][0]['content'])['verdict']) for row in records])
        return {**{key:value.to(device) for key,value in tokens.items() if key in {'input_ids','attention_mask'}},'evidence':facts.to(device)},truth.to(device)
    train,truth=read(args.train,'train');validation,vtruth=read(args.validation,'validation')
    if families['train']&families['validation']:raise ValueError('Scenario family leakage')
    optimizer=torch.optim.AdamW([{'params':[p for p in model.encoder.parameters() if p.requires_grad],'lr':.001},
        {'params':model.head.parameters(),'lr':.003}],weight_decay=.01)
    def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    hashes={name:digest(path) for name,path in [('train',args.train),('validation',args.validation)]}
    start=time.perf_counter()
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    validation_history=[]
    for epoch in range(args.epochs):
        model.train();order=torch.randperm(len(truth),device=device);loss_total=0.
        for offset in range(0,len(order),16):
            indices=order[offset:offset+16]
            optimizer.zero_grad(set_to_none=True)
            logits=model(**{key:value[indices] for key,value in train.items()})
            loss=torch.nn.functional.cross_entropy(logits,truth[indices]);loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.step();loss_total+=float(loss.detach())
        model.eval()
        with torch.inference_mode():
            actual=model(**validation).argmax(-1)
            accuracy=float((actual==vtruth).float().mean())
        validation_history.append(accuracy)
        print(f'Epoch {epoch+1}/{args.epochs}: loss={loss_total:.4f} validation_decision_accuracy={accuracy:.4f}',flush=True)
    elapsed=time.perf_counter()-start
    if hashes!={name:digest(path) for name,path in [('train',args.train),('validation',args.validation)]}:raise ValueError('Dataset changed during training')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    encoder.save_pretrained(output);tokenizer.save_pretrained(output)
    save_file({key:value.detach().cpu().contiguous() for key,value in model.head.state_dict().items()},output/'evidence_head.safetensors')
    policy=resolve(args.tenant,args.policy_version)
    manifest={'model':args.model,'revision':args.revision,'tenant':args.tenant,'policy_version':args.policy_version,'policy_sha256':policy.digest,
        'task':'evidence-classifier','labels':list(LABELS),'head_only':args.head_only,'evidence_features':list(__import__('ml.evidence_features',fromlist=['NAMES']).NAMES),
        'training_sha256':hashes['train'],'validation_sha256':hashes['validation'],'epochs':args.epochs,'seed':42,
        'hardware':torch.cuda.get_device_name() if device=='cuda' else 'CPU','wall_seconds':elapsed,
        'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated() if device=='cuda' else None,'validation_accuracy_history':validation_history,
        'adapter_sha256':digest(output/'adapter_model.safetensors'),'head_sha256':digest(output/'evidence_head.safetensors'),
        'adapter_config_sha256':digest(output/'adapter_config.json'),'versions':{name:__import__(name).__version__ for name in ('torch','transformers','peft')}}
    (output/'run_manifest.json').write_text(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
