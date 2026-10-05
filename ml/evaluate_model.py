"""Offline evaluation of a prompted model or a three-adapter registry.

Never executes financial actions or delivers generated text to a customer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from switchboard.benchmark import cases
from switchboard.engine import VERDICTS, resolve
from switchboard.evals import summarize
from .common import prompt
from switchboard.release_gate import digest_file, assess


def parse_decision(text):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    result = json.loads(text, object_pairs_hook=unique)
    if not isinstance(result, dict) or set(result) != {'verdict','policy_ids','reason','proposed_output'}:
        raise ValueError('Unexpected output contract')
    if not isinstance(result, dict) or result.get("verdict") not in VERDICTS:
        raise ValueError("Malformed verdict")
    if not isinstance(result.get("policy_ids"), list) or len(result['policy_ids']) > 8 or not all(isinstance(x,str) and len(x)<100 for x in result["policy_ids"]):
        raise ValueError("Malformed policy IDs")
    if not isinstance(result.get("reason"), str) or len(result['reason'])>2000 or not (result.get("proposed_output") is None or isinstance(result["proposed_output"],str) and len(result['proposed_output'])<=6000):
        raise ValueError("Malformed output contract")
    return result


def policy_batches(rows,size):
    if not 1 <= size <= 16: raise ValueError('Batch size must be 1–16')
    groups={}
    for row in rows: groups.setdefault((row['tenant'],row['version']),[]).append(row)
    return [group[start:start+size] for group in groups.values() for start in range(0,len(group),size)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--registry", help="JSON mapping harbor/v1, harbor/v2, cedar/v1 to adapter directories")
    p.add_argument("--output", default="artifacts/model-evaluation.json")
    p.add_argument("--cpu", action="store_true")
    p.add_argument('--holdout',action='store_true',help='Evaluate the wording-family validation split instead of the smoke benchmark')
    p.add_argument('--mode',choices=['full','triage'],default='full')
    p.add_argument('--cache',help='Exact model/artifact/prompt/generation cache JSON for fictional inputs')
    p.add_argument('--batch-size',type=int,default=8)
    args = p.parse_args()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as exc:
        raise SystemExit("Install the optional ML dependencies first.") from exc
    torch.set_num_threads(2)
    if not args.cpu and not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU available; use --cpu for a small checkpoint.")
    if args.revision != "local" and (len(args.revision)!=40 or any(c not in "0123456789abcdef" for c in args.revision.lower())):
        raise SystemExit("Pin an immutable 40-character model revision, or specify local.")
    revision = None if args.revision == "local" else args.revision
    registry = json.loads(Path(args.registry).read_text()) if args.registry else None
    if registry is not None and set(registry) != {"harbor/v1","harbor/v2","cedar/v1"}:
        raise SystemExit("Registry must contain exactly harbor/v1, harbor/v2 and cedar/v1.")
    tokenizer = AutoTokenizer.from_pretrained(args.model,revision=revision,trust_remote_code=False)
    tokenizer.padding_side='left'
    tokenizer.pad_token=tokenizer.eos_token
    device = "cpu" if args.cpu else "cuda"
    base = AutoModelForCausalLM.from_pretrained(args.model,revision=revision,trust_remote_code=False,torch_dtype=torch.float32 if args.cpu else torch.float16).to(device)
    model = base
    if registry:
        for index,(key,path) in enumerate(registry.items()):
            manifest = json.loads(Path(path,"run_manifest.json").read_text())
            if manifest["model"] != args.model or manifest["revision"] != args.revision:
                raise SystemExit("Adapter manifest does not match the base model revision.")
            tenant, version = key.split('/')
            if (manifest.get('tenant'),manifest.get('policy_version'),manifest.get('policy_sha256')) != (tenant,version,resolve(tenant,version).digest):
                raise SystemExit('Adapter tenant or policy fingerprint mismatch.')
            if digest_file(Path(path,'adapter_model.safetensors')) != manifest.get('adapter_sha256'):
                raise SystemExit('Adapter weights changed after training.')
            if index==0:
                model=PeftModel.from_pretrained(base,path,adapter_name=key)
            else:
                model.load_adapter(path,adapter_name=key)
    model.eval()
    evaluation_cases=cases()
    if args.holdout:
        evaluation_cases=[]
        for tenant,version in [('harbor','v1'),('harbor','v2'),('cedar','v1')]:
            for index,line in enumerate(Path(f'data/{tenant}-{version}-validation.jsonl').read_text().splitlines()):
                example=json.loads(line)
                user=json.loads(example['prompt'][1]['content'])
                label=parse_decision(example['completion'][0]['content'])['verdict']
                evaluation_cases.append({'id':f'{tenant}-{version}-holdout-{index}','tenant':tenant,'version':version,
                    'family_id':f"{example['family_id']}-{index}",'message':user['message'],'context':user['trusted_context'],
                    'expected':label,'dependency':'REFUND-01','provenance':'Synthetic held-out wording families; not expert-reviewed'})
    if args.mode == 'triage':
        evaluation_cases=[c for c in evaluation_cases if c['dependency']=='REFUND-01' or c['family_id'] in {'hello','secret','guarantee'}]
    fingerprints={str(Path(path,name).as_posix()):digest_file(Path(path,name))
        for path in (registry or {}).values() for name in ('adapter_model.safetensors','adapter_config.json','run_manifest.json')}
    cache_path=Path(args.cache) if args.cache else None
    cache=json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else {}
    rows=[]
    start=time.perf_counter()
    for batch in policy_batches(evaluation_cases,args.batch_size):
        prompts=[prompt(c['message'],c['context'],c['tenant'],c['version']) for c in batch]
        identity={'model':args.model,'revision':args.revision,'artifacts':fingerprints,
            'prompts':prompts,'dtype':'float32' if args.cpu else 'float16','batch_size':args.batch_size,
            'libraries':{name:__import__(name).__version__ for name in ('torch','transformers','peft')},
            'generation':{'max_new_tokens':220,'do_sample':False},'parser_revision':'strict-json-v2'}
        batch_key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        keys=[f'{batch_key}/{index}' for index in range(len(batch))]
        if all(key in cache for key in keys):
            rows.extend({**case,**cache[key],'cache_hit':True,'latency_ms':0} for case,key in zip(batch,keys))
            continue
        if registry:
            model.set_adapter(f"{batch[0]['tenant']}/{batch[0]['version']}")
        texts=[tokenizer.apply_chat_template(p,tokenize=False,add_generation_prompt=True) for p in prompts]
        inputs=tokenizer(texts,add_special_tokens=False,padding=True,return_tensors='pt').to(device)
        if not args.cpu: torch.cuda.synchronize()
        t=time.perf_counter()
        with torch.inference_mode():
            output=model.generate(**inputs,max_new_tokens=220,do_sample=False,pad_token_id=tokenizer.eos_token_id)
        if not args.cpu: torch.cuda.synchronize()
        duration=(time.perf_counter()-t)*1000
        generated=tokenizer.batch_decode(output[:,inputs['input_ids'].shape[-1]:],skip_special_tokens=True)
        for case,key,text in zip(batch,keys,generated):
            error=None
            try: predicted=parse_decision(text)['verdict']
            except (ValueError,TypeError):
                predicted='invalid'
                error='Malformed model output; runtime must withhold delivery.'
            value={'predicted':predicted,'raw_output':text,'error':error,'source_batch_latency_ms':duration}
            rows.append({**case,**value,'cache_hit':False,'latency_ms':duration})
            cache[key]=value
        if cache_path:
            cache_path.parent.mkdir(parents=True,exist_ok=True)
            cache_path.write_text(json.dumps(cache),encoding='utf-8')
        print(f'Measured {len(rows)}/{len(evaluation_cases)} predictions',flush=True)
    result=summarize(rows,time.perf_counter()-start,cache_hits=sum(r['cache_hit'] for r in rows),backend="lora" if registry else "prompted-model")
    result['mode']=args.mode
    result['batch_size']=args.batch_size
    result['latency_definition']='Completion time for a homogeneous tenant/policy batch; excludes loading and queue time. Not single-request latency.'
    result['cases_per_second']=round(len(rows)/(result['wall_ms']/1000),3)
    result.update(model=args.model,revision=args.revision,adapter_registry=registry,
        invalid_outputs=sum(r["predicted"]=="invalid" for r in rows),
        limitations="Synthetic smoke benchmark only. Raw model outputs are offline; semantic rewrite quality needs independent human review. Dollar cost and GPU-seconds not measured.")
    result['artifact_fingerprints'] = fingerprints
    # Invalid outputs are neither correct decisions nor evidence of violation detection.
    violations=[r for r in rows if r["expected"]!="pass"]
    result["violation_recall"]=sum(r["predicted"] in {"rewrite","block","escalate"} for r in violations)/len(violations)
    if args.holdout:
        result['benchmark']='synthetic-wording-holdout-v1'
        result['release_gate']={'status':'not-a-release-suite','customer_delivery':False}
    else:
        result['release_gate'] = assess(result)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    if cache_path:
        cache_path.parent.mkdir(parents=True,exist_ok=True)
        cache_path.write_text(json.dumps(cache),encoding='utf-8')
    print(f"Saved {len(rows)} measured model predictions to {out}")


if __name__ == "__main__":
    main()
