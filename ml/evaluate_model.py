"""Offline evaluation of a prompted model or a three-adapter registry.

Never executes financial actions or delivers generated text to a customer.
"""
import argparse
import json
from pathlib import Path
import time
from switchboard.benchmark import cases
from switchboard.engine import VERDICTS
from switchboard.evals import summarize
from .common import prompt


def parse_decision(text):
    result = json.loads(text)
    if not isinstance(result, dict) or result.get("verdict") not in VERDICTS:
        raise ValueError("Malformed verdict")
    if not isinstance(result.get("policy_ids"), list) or not all(isinstance(x,str) for x in result["policy_ids"]):
        raise ValueError("Malformed policy IDs")
    if not isinstance(result.get("reason"), str) or not (result.get("proposed_output") is None or isinstance(result["proposed_output"],str)):
        raise ValueError("Malformed output contract")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--registry", help="JSON mapping harbor/v1, harbor/v2, cedar/v1 to adapter directories")
    p.add_argument("--output", default="artifacts/model-evaluation.json")
    p.add_argument("--cpu", action="store_true")
    args = p.parse_args()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as exc:
        raise SystemExit("Install the optional ML dependencies first.") from exc
    if not args.cpu and not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU available; use --cpu for a small checkpoint.")
    if args.revision != "local" and (len(args.revision)!=40 or any(c not in "0123456789abcdef" for c in args.revision.lower())):
        raise SystemExit("Pin an immutable 40-character model revision, or specify local.")
    revision = None if args.revision == "local" else args.revision
    registry = json.loads(Path(args.registry).read_text()) if args.registry else None
    if registry is not None and set(registry) != {"harbor/v1","harbor/v2","cedar/v1"}:
        raise SystemExit("Registry must contain exactly harbor/v1, harbor/v2 and cedar/v1.")
    tokenizer = AutoTokenizer.from_pretrained(args.model,revision=revision,trust_remote_code=False)
    device = "cpu" if args.cpu else "cuda"
    base = AutoModelForCausalLM.from_pretrained(args.model,revision=revision,trust_remote_code=False,torch_dtype=torch.float32 if args.cpu else torch.float16).to(device)
    model = base
    if registry:
        for index,(key,path) in enumerate(registry.items()):
            manifest = json.loads(Path(path,"run_manifest.json").read_text())
            if manifest["model"] != args.model or manifest["revision"] != args.revision:
                raise SystemExit("Adapter manifest does not match the base model revision.")
            if index==0:
                model=PeftModel.from_pretrained(base,path,adapter_name=key)
            else:
                model.load_adapter(path,adapter_name=key)
    model.eval()
    rows=[]
    start=time.perf_counter()
    for case in cases():
        if registry:
            model.set_adapter(f"{case['tenant']}/{case['version']}")
        input_ids=tokenizer.apply_chat_template(prompt(case["message"],case["context"],case["tenant"],case["version"]),add_generation_prompt=True,return_tensors="pt").to(device)
        if not args.cpu: torch.cuda.synchronize()
        t=time.perf_counter()
        with torch.inference_mode():
            output=model.generate(input_ids,max_new_tokens=220,do_sample=False,pad_token_id=tokenizer.eos_token_id)
        if not args.cpu: torch.cuda.synchronize()
        duration=(time.perf_counter()-t)*1000
        text=tokenizer.decode(output[0,input_ids.shape[-1]:],skip_special_tokens=True)
        error=None
        try:
            decision=parse_decision(text)
            predicted=decision["verdict"]
        except (ValueError,TypeError):
            predicted="invalid"
            error="Malformed model output; runtime must withhold delivery."
        rows.append({**case,"predicted":predicted,"raw_output":text,"error":error,"cache_hit":False,"latency_ms":duration})
    result=summarize(rows,time.perf_counter()-start,backend="lora" if registry else "prompted-model")
    result.update(model=args.model,revision=args.revision,adapter_registry=registry,
        invalid_outputs=sum(r["predicted"]=="invalid" for r in rows),
        limitations="Synthetic smoke benchmark only. Raw model outputs are offline; semantic rewrite quality needs independent human review. Dollar cost and GPU-seconds not measured.")
    # Invalid outputs are neither correct decisions nor evidence of violation detection.
    violations=[r for r in rows if r["expected"]!="pass"]
    result["violation_recall"]=sum(r["predicted"] in {"rewrite","block","escalate"} for r in violations)/len(violations)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(f"Saved {len(rows)} measured model predictions to {out}")


if __name__ == "__main__":
    main()
