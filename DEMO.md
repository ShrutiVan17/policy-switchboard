# Three-minute engineering walkthrough

Only describe what you have run and can explain. The current system uses a deterministic baseline, not a trained model.

## 0:00 — The problem

"A support agent promises a $15 transfer-fee refund. Harbor allows this under yesterday's rules, but today's limit is $10. Cedar requires approval for every refund. I built a small policy migration lab to make those differences testable."

Show the default replay: Harbor v1 passes; Harbor v2 and Cedar escalate. Explain why the escalation message is proposed for review and withheld from delivery.

## 0:40 — What must remain correct

Click `Small $5 refund`: Harbor passes under both versions. Check `Supervisor approved this refund`, then click `Check this message`: all three policies permit the refund. Explain that the toggle represents trusted context in this fictional demo, and that a deployed system would fetch approval rather than trust a user-supplied field.

## 1:10 — Other enforcement paths

Click `Guaranteed investment returns`: a supported simple claim becomes `Investment returns are uncertain.` and is verified by a separate deterministic check. Click `Private information`: output is blocked. Expand `View saved checks for Harbor` and a technical record to show the stored secret is redacted and the policy hash is recorded.

## 1:40 — Measured evaluations

Run the full benchmark. It has 72 curated synthetic cases; the rules baseline matches all 72. There are 3 required-change pairs and 21 invariant pairs. Explain that these small fixtures test the implementation, rather than establish legal accuracy or generalization.

Click `Test the changed rule`: 48 cases, including refund dependencies and a fixed set of invariant sentinels. Repeated exact-configuration runs use cached verdicts. Show downloaded raw JSON. Do not claim measured GPU or dollar savings; those fields are explicitly null.

## 2:20 — Applied ML next stage

Show `ml/build_dataset.py`, `ml/train_lora.py` and `ml/evaluate_model.py`. Explain family-based validation splits, revision-pinned base models, a customer/version adapter registry, manifest validation and explicit handling of malformed model outputs.

"These scripts prepare the next experiment: does customer-specific LoRA improve enforcement against the prompted baseline? Training has not run yet, so I haven't invented model results."

## 2:50 — Tradeoff and one real fix

"The local baseline escalates unfamiliar wording rather than trying to interpret everything. I also fixed a database connection lifecycle issue caught by concurrent API tests. The next milestone is reviewed data, actual adapter training and an independent benchmark, followed by a hosted model backend."

## Application note

Present this version as a policy-enforcement engineering prototype. Do not describe it as post-trained production deployment experience. Once actual model training and deployment have been completed, update the demonstration and application wording to the measured results.
