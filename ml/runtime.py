"""Locked, local-only shadow inference; generated text never becomes delivered text."""
import json
from pathlib import Path
import threading
import time
from .common import prompt
from .evaluate_model import parse_decision
from switchboard.engine import resolve, enforce
from switchboard.release_gate import digest_file

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
STATE = None


def load():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from huggingface_hub import snapshot_download
    torch.set_num_threads(2)
    registry = json.loads((ROOT/'models/registry.json').read_text())
    model = None
    tokenizer = None
    revision = None
    fingerprints = {}
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    for key, relative in registry.items():
        path = (ROOT/relative).resolve()
        if not path.is_relative_to((ROOT/'models').resolve()):
            raise ValueError('Adapter path outside model directory')
        manifest = json.loads((path/'run_manifest.json').read_text())
        tenant, version = key.split('/')
        if (manifest['tenant'],manifest['policy_version'],manifest['policy_sha256']) != (tenant,version,resolve(tenant,version).digest):
            raise ValueError('Adapter tenant or policy mismatch')
        fingerprint = digest_file(path/'adapter_model.safetensors')
        if fingerprint != manifest['adapter_sha256']:
            raise ValueError('Changed model weights')
        identity = (manifest['model'],manifest['revision'])
        if model is None:
            revision = identity
            snapshot=snapshot_download(identity[0],revision=identity[1],local_files_only=True)
            tokenizer = AutoTokenizer.from_pretrained(snapshot,local_files_only=True)
            base = AutoModelForCausalLM.from_pretrained(snapshot,local_files_only=True,
                torch_dtype=torch.float32 if device=='cpu' else torch.float16).to(device)
            model = PeftModel.from_pretrained(base,str(path),adapter_name=key)
        else:
            if identity != revision: raise ValueError('Mixed base model revisions')
            model.load_adapter(str(path),adapter_name=key)
        fingerprints[key] = fingerprint
    if set(registry) != {'harbor/v1','harbor/v2','cedar/v1'}:
        raise ValueError('Incomplete adapter registry')
    model.eval()
    return model,tokenizer,device,fingerprints


def shadow(message,context,tenant,version):
    global STATE
    checked = enforce(message,context,tenant,version)
    # Never pass detected credentials into the model or return them as generated text.
    if checked['verdict'] == 'block':
        return {'model_verdict':'not-run','rule_verdict':'block','delivered_output':None,
                'reason':'Private information blocked before AI inference.','mode':'shadow'}
    import torch
    with LOCK:
        if STATE is None: STATE = load()
        model,tokenizer,device,fingerprints = STATE
        key = f'{tenant}/{version}'
        model.set_adapter(key)
        ids=tokenizer.apply_chat_template(prompt(message,context,tenant,version),add_generation_prompt=True,return_tensors='pt').to(device)
        if ids.shape[-1] > 1536: raise ValueError('Message too long for this research model')
        start=time.perf_counter()
        with torch.inference_mode():
            output=model.generate(ids,attention_mask=torch.ones_like(ids),max_new_tokens=220,do_sample=False,pad_token_id=tokenizer.eos_token_id)
        text=tokenizer.decode(output[0,ids.shape[-1]:],skip_special_tokens=True)
        try: predicted=parse_decision(text)['verdict']
        except (ValueError,TypeError): predicted='invalid'
        return {'model_verdict':predicted,'rule_verdict':checked['verdict'],
                'agreement':predicted==checked['verdict'],'delivered_output':None,'mode':'shadow',
                'adapter_sha256':fingerprints[key],'latency_ms':round((time.perf_counter()-start)*1000,2),
                'reason':'AI comparison only. Customer delivery is disabled.'}
