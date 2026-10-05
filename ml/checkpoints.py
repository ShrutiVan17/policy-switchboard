"""Revision-pinned regular-file checkpoints for Windows and container portability."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def download(model,revision):
    from huggingface_hub import snapshot_download
    if len(revision)!=40 or not set(revision)<=set('0123456789abcdef'): raise ValueError('Immutable revision required')
    path=ROOT/'.cache/checkpoints'/revision
    snapshot_download(model,revision=revision,local_dir=path,
        allow_patterns=['*.json','*.safetensors','*.jinja','merges.txt','vocab.json','vocab.txt','LICENSE','README.md'])
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.glob('*') if p.is_file() and p.name!='source.json'}
    (path/'source.json').write_text(json.dumps({'model':model,'revision':revision,'files':hashes},indent=2))
    return path


def local_source(model,revision):
    path=ROOT/'.cache/checkpoints'/revision
    if (path/'source.json').exists():
        source=json.loads((path/'source.json').read_text())
        if (source['model'],source['revision'])!=(model,revision): raise ValueError('Wrong cached checkpoint identity')
        for name,digest in source['files'].items():
            if hashlib.sha256((path/name).read_bytes()).hexdigest()!=digest: raise ValueError('Changed checkpoint file')
        return str(path)
    return model
