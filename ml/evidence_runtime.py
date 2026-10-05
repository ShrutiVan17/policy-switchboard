"""Bounded CPU verdict inference. Research predictions never deliver customer text."""
import json
from pathlib import Path
import threading
import time
from switchboard.engine import enforce, resolve
from switchboard.release_gate import digest_file
from .evidence_features import features, NAMES
from .constrained import LABELS
from .checkpoints import local_source

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
STATE = {}


def load(tenant, version, model_prefix='evidence'):
    import torch
    from transformers import AutoModel, AutoTokenizer
    from peft import PeftModel
    from safetensors.torch import load_file
    from .evidence_model import EvidenceModel
    torch.set_num_threads(2)
    policy = resolve(tenant, version)
    if model_prefix not in {'evidence','control'}:raise ValueError('Unknown experiment')
    path = ROOT/'models'/f'{model_prefix}-{policy.tenant}-{policy.version}'
    manifest = json.loads((path/'run_manifest.json').read_text())
    if (manifest['tenant'], manifest['policy_version'], manifest['policy_sha256']) != (tenant, version, policy.digest):
        raise ValueError('Adapter policy mismatch')
    if manifest['task'] != 'evidence-classifier' or manifest['labels'] != list(LABELS) or manifest['evidence_features'] != list(NAMES):
        raise ValueError('Unsupported model contract')
    for filename, field in [('adapter_model.safetensors','adapter_sha256'), ('evidence_head.safetensors','head_sha256'), ('adapter_config.json','adapter_config_sha256')]:
        if digest_file(path/filename) != manifest[field]:
            raise ValueError('Changed trained artifact')
    source = local_source(manifest['model'], manifest['revision'])
    if not Path(source).is_dir():
        raise OSError('Pinned base checkpoint must be provisioned locally')
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
    base = AutoModel.from_pretrained(source, local_files_only=True, attn_implementation='eager')
    model = EvidenceModel(PeftModel.from_pretrained(base, path), base.config.hidden_size)
    model.head.load_state_dict(load_file(path/'evidence_head.safetensors'))
    model.eval()
    return model, tokenizer, manifest


def predict(message, context, tenant, version, model_prefix='evidence'):
    import torch
    start = time.perf_counter()
    with LOCK:
        key = (tenant, version, model_prefix)
        if key not in STATE:
            STATE[key] = load(tenant, version, model_prefix)
        model, tokenizer, manifest = STATE[key]
        tokens = tokenizer(message, return_tensors='pt')
        if tokens['input_ids'].shape[-1] > 128:
            raise ValueError('AI comparison supports messages up to 128 tokens')
        facts = features(message, context, tenant, version)
        with torch.inference_mode():
            probs = model(input_ids=tokens['input_ids'], attention_mask=tokens['attention_mask'],
                          evidence=torch.tensor([facts], dtype=torch.float32)).softmax(-1)[0].tolist()
        index = max(range(len(probs)), key=probs.__getitem__)
        return {'model_verdict': LABELS[index], 'confidence': probs[index], 'probabilities': probs,
                'latency_ms': round((time.perf_counter()-start)*1000, 2),
                'adapter_sha256': manifest['adapter_sha256'], 'head_sha256': manifest['head_sha256'],
                'architecture': 'LoRA semantic encoder + explicit business evidence + trained verdict head'}


def shadow(message, context, tenant, version):
    checked = enforce(message, context, tenant, version)
    if checked['verdict'] == 'block':
        return {'model_verdict':'not-run','rule_verdict':'block','delivered_output':None,
                'reason':'Private information blocked before AI inference.','mode':'shadow'}
    result = predict(message, context, tenant, version)
    result.update(rule_verdict=checked['verdict'], agreement=result['model_verdict']==checked['verdict'],
                  delivered_output=None, mode='shadow', reason='AI comparison only. Customer delivery is disabled.')
    return result
