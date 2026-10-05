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
    args = p.parse_args()
    # Heavy imports are optional; the application itself has no third-party dependencies.
    try:
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig
        from trl import SFTTrainer, SFTConfig
    except ImportError as exc:
        raise SystemExit("Install ml/requirements.txt in a dedicated GPU environment first.") from exc
    if not args.cpu and not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU available. Use a suitable GPU environment or --cpu with a tiny model.")
    if args.qlora and args.cpu:
        raise SystemExit("QLoRA requires a supported CUDA environment.")
    if args.revision != "local" and (len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision.lower())):
        raise SystemExit("--revision must be a 40-character immutable commit SHA, or local.")
    revision = None if args.revision == "local" else args.revision
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=revision, trust_remote_code=False)
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
    datasets = load_dataset("json", data_files={"train":args.train,"validation":args.validation})
    train_families = set(datasets["train"]["family_id"])
    validation_families = set(datasets["validation"]["family_id"])
    if train_families & validation_families:
        raise SystemExit("Scenario family leakage between training and validation.")
    config = SFTConfig(output_dir=args.output, num_train_epochs=args.epochs,
        per_device_train_batch_size=1, per_device_eval_batch_size=1, gradient_accumulation_steps=8,
        learning_rate=2e-4, max_length=1024, packing=False, completion_only_loss=True,
        bf16=bf16, fp16=not args.cpu and not bf16, use_cpu=args.cpu,
        gradient_checkpointing=not args.cpu, eval_strategy="epoch", save_strategy="epoch",
        logging_steps=5, report_to="none", seed=42)
    adapter = LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,bias="none",task_type="CAUSAL_LM",target_modules="all-linear")
    trainer = SFTTrainer(model=model,args=config,train_dataset=datasets["train"],eval_dataset=datasets["validation"],processing_class=tokenizer,peft_config=adapter)
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    Path(args.output, "run_manifest.json").write_text(json.dumps({"model":args.model,"revision":args.revision,
        "training_sha256":digest(args.train),"validation_sha256":digest(args.validation),
        "epochs":args.epochs,"seed":42,"qlora":args.qlora,"versions":{k:__import__(k).__version__ for k in ("torch","transformers","peft","trl","datasets")}},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
