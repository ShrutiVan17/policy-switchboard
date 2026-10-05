"""Finite-state verdict decoding. No invented model explanations or rewrites."""
LABELS=('pass','rewrite','block','escalate')
PREFIX='{"verdict": "'


def build_trie(tokenizer):
    root={}
    for label in LABELS:
        node=root
        for token in tokenizer.encode(label+'"',add_special_tokens=False):
            node=node.setdefault(token,{})
        node[None]=True
    return root


def allowed(trie,prefix,eos):
    node=trie
    for token in prefix:
        if token not in node: return [eos]
        node=node[token]
    return [eos] if None in node else [token for token in node if token is not None]


def classify_text(text):
    value=text.rstrip().removesuffix('"')
    return value if value in LABELS else 'invalid'
