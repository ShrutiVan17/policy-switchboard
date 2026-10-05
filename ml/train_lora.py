"""Optional LoRA SFT using the documented Hugging Face TRL interface."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="Licensed instruction checkpoint or local shared checkpoint")
    p.add_argument("--revision", required=True, help="Immutable Hugging Face commit SHA; use local for a local checkpoint")
    p.add_argument("--train", required=True)
    p.add_argument("--validation", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=float, default=2)
    p.add_argument("--qlora", action="store_true")
    p.add_argument("--cpu", action="store_true", help="Small-checkpoint smoke runs only")
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument('--verdict-weight',type=float,default=1.0)
    p.add_argument('--batch-size',type=int,choices=[1,2,4,8],default=4)
    p.add_argument('--gradient-checkpointing',action='store_true',help='Trade training speed for lower GPU memory')
    p.add_argument("--tenant", required=True, choices=['harbor','cedar'])
    p.add_argument("--policy-version", required=True, choices=['v1','v2'])
    args = p.parse_args()
    from switchboard.engine import resolve
    policy = resolve(args.tenant, args.policy_version)
    def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    initial_hashes={'train':digest(args.train),'validation':digest(args.validation)}
    trainer_source_hash=digest(__file__)
    # Training dependencies are separate from the lightweight serving environment.
    try:
        import torch
        from datasets import Dataset, DatasetDict
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed
        from peft import LoraConfig
        from trl import SFTTrainer, SFTConfig
    except ImportError as exc:
        raise SystemExit("Install ml/requirements.txt in a dedicated GPU environment first.") from exc
    torch.set_num_threads(2)
    if not args.cpu and not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU available. Use a suitable GPU environment or --cpu with a tiny model.")
    if args.qlora and args.cpu:
        raise SystemExit("QLoRA requires a supported CUDA environment.")
    if args.revision != "local" and (len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision.lower())):
        raise SystemExit("--revision must be a 40-character immutable commit SHA, or local.")
    revision = None if args.revision == "local" else args.revision
    set_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=revision, trust_remote_code=False)
    if args.verdict_weight < 1: raise SystemExit('Verdict weight must be at least one')
    if not tokenizer.chat_template:
        raise SystemExit("Choose an instruction checkpoint with a chat template.")
    if not tokenizer.pad_token:
        tokenizer.pad_token = tokenizer.eos_token
    bf16 = not args.cpu and torch.cuda.is_bf16_supported()
    kwargs = {"revision":revision,"trust_remote_code":False,"torch_dtype":torch.float32 if args.cpu else (torch.bfloat16 if bf16 else torch.float16)}
    if args.qlora:
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_compute_dtype=kwargs["torch_dtype"],bnb_4bit_use_double_quant=True)
        kwargs["device_map"] = {"":torch.cuda.current_device()}
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
    # Load this small local corpus in memory; avoid long Windows dataset-cache lock paths.
    datasets = DatasetDict({name:Dataset.from_list([json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()])
        for name,path in {'train':args.train,'validation':args.validation}.items()})
    train_families = set(datasets["train"]["family_id"])
    validation_families = set(datasets["validation"]["family_id"])
    if train_families & validation_families:
        raise SystemExit("Scenario family leakage between training and validation.")
    maximum_tokens=max(len(tokenizer.apply_chat_template(row['prompt']+row['completion']))
        for split in datasets.values() for row in split)
    if maximum_tokens > args.max_length:
        raise SystemExit(f'Examples need {maximum_tokens} tokens. Increase --max-length to avoid truncating labels.')
    config = SFTConfig(output_dir=args.output, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size, gradient_accumulation_steps=max(1,8//args.batch_size),
        learning_rate=2e-4, max_length=args.max_length, packing=False, completion_only_loss=True,
        bf16=bf16, fp16=not args.cpu and not bf16, use_cpu=args.cpu,
        gradient_checkpointing=args.gradient_checkpointing, eval_strategy="epoch", save_strategy="no",
        logging_steps=5, report_to="none", seed=42)
    adapter = LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,bias="none",task_type="CAUSAL_LM",target_modules="all-linear")
    loss_func=None
    if args.verdict_weight>1:
        from .verdict_loss import make_verdict_loss
        focus={token for verdict in ('pass','rewrite','block','escalate') for token in tokenizer.encode(verdict,add_special_tokens=False)}
        loss_func=make_verdict_loss(focus,args.verdict_weight)
    trainer = SFTTrainer(model=model,args=config,train_dataset=datasets["train"],eval_dataset=datasets["validation"],processing_class=tokenizer,peft_config=adapter,compute_loss_func=loss_func)
    started = __import__('time').perf_counter()
    training = trainer.train()
    elapsed = __import__('time').perf_counter() - started
    if initial_hashes != {'train':digest(args.train),'validation':digest(args.validation)}:
        raise SystemExit('Dataset changed during training; refusing to publish this adapter.')
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    Path(args.output, "run_manifest.json").write_text(json.dumps({"model":args.model,"revision":args.revision,
        "training_sha256":digest(args.train),"validation_sha256":digest(args.validation),
        "epochs":args.epochs,"seed":42,"qlora":args.qlora,"wall_seconds":elapsed,
        "max_length":args.max_length,"gradient_checkpointing":args.gradient_checkpointing,
        "verdict_weight":args.verdict_weight,
        "batch_size":args.batch_size,"effective_batch_size":8,
        "trainer_source_sha256":trainer_source_hash,"initialization_seed_explicit":True,
        "tenant":args.tenant,"policy_version":args.policy_version,"policy_sha256":policy.digest,
        "hardware": "CPU" if args.cpu else torch.cuda.get_device_name(), "training_metrics":training.metrics,
        "adapter_sha256":digest(Path(args.output,"adapter_model.safetensors")),
        "versions":{k:__import__(k).__version__ for k in ("torch","transformers","peft","trl","datasets")}},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
