# Policy Switchboard

**When a company's rules change, prove its AI changes correctly.**

Portfolio project proposal for a Machine Learning / Applied AI Engineer role at ZeroDrift.

Status: runnable local application with a deterministic baseline, live synthetic smoke evaluations, evidence logging, tests, and optional LoRA training/offline model-evaluation scripts. No LoRA model has been trained or deployed yet. Example decisions represent fictional company policies, not legal judgments. See [RUN.md](../RUN.md) for commands, implemented scope and remaining work.

## The problem people recognize

An AI support agent tells a customer: "Yes, your transfer fee will be refunded."
Yesterday that was allowed. Today the company requires a supervisor's approval.
Meanwhile, another company still permits the refund. A universal refusal frustrates customers; a stale answer makes an unauthorized promise.

Build an enforcement service that catches this distinction, selects the correct customer's LoRA adapter and policy version, and returns pass, rewrite, block, or escalate with the applicable policy ID and evidence span.

## The distinctive experiment

Treat a policy update as a behavioral migration. Given policy versions v1 and v2, measure two things separately:

1. **Required changes:** examples whose correct decision changes under the updated policy.
2. **Required invariants:** examples whose correct decision must stay the same.

The same message can have different correct decisions across companies and policy versions. The benchmark must reward policy adherence rather than generic refusal or a memorized wording pattern.

The project does not claim that policy versioning, LoRA, or regression testing are new inventions. Its contribution is a reproducible experiment combining customer-specific training, paired policy-update evaluations, selective eval execution, and deployment controls.

## Relatable demo: a transfer-fee refund

Fictional tenants:

- Harbor: agents may authorize transfer-fee refunds up to $20.
- Cedar: all transfer-fee refunds require supervisor approval.
- Harbor v2: refunds above $10 now require supervisor approval.

Original agent message: "I can refund your $15 transfer fee now."

Expected behavior:

| Policy | Verdict | Reason |
| --- | --- | --- |
| Harbor v1 | pass | $15 is within the $20 limit |
| Cedar v1 | escalate | Supervisor approval is always required |
| Harbor v2 | escalate | $15 exceeds the new $10 limit |

The escalation message should say it will request approval, without promising approval. Preserve the customer's amount and request. A verified supervisor-approved context can allow a different decision, provided the trusted request metadata records that approval.

UI: original message on the left; three tenant/version decisions on the right; policy-diff panel below. A "replay update" action compares old and candidate versions. Show raw evidence and measured evals, rather than a simulated accuracy counter.

## Scope

Start with one domain: fictional financial customer support. Include refund permissions, unsupported guarantees, restricted product mentions, confidentiality, and escalation requirements. Use explicit company policies. A regulatory extension requires sourced rules and qualified label review; do not call synthetic labels legal ground truth.

MVP: two customers, three adapter artifacts (Harbor v1, Harbor v2, Cedar v1), one small instruction model, one endpoint, one eval runner, and a replay interface.

## Training design

Select a small open-weight instruction model after checking its model card, license, GPU memory requirements, and serving compatibility. Pin model and tokenizer revisions. Use Hugging Face Transformers, PEFT and TRL; use QLoRA if the available GPU requires it.

First train a shared enforcement checkpoint on common policies and structured responses. Freeze that checkpoint and train each customer's LoRA from it. Serve exactly one customer adapter against the shared checkpoint; do not assume stacking unrelated adapters works. This separation makes tenant behavior testable.

Each training input contains message, trusted context, policy version, and relevant policy content or identifiers. Teach output schema: verdict, policy IDs, exact evidence spans, proposed output when applicable, and escalation reason. Validate schema and span offsets outside the model.

Do not store rapidly changing balances, approval status, account identifiers, or refund limits only in weights. Keep current structured values in a versioned policy store and apply deterministic checks. The adapter learns contextual interpretation, relevant evidence, and appropriate handling. Benchmark whether LoRA improves that behavior beyond prompting and rules alone.

Suggested initial corpus: 2,400 reviewed synthetic examples across both tenants and versions, generated from several scenario families. Include compliant messages, contextual exceptions, negation, quoting, mixed violations, missing metadata, adversarial instructions inside messages, and minimally different counterexamples. This is a starting design, not a guaranteed sufficient dataset size.

Split by scenario family and source template before paraphrasing. Keep all variants of one scenario in one split. Maintain a separate manually authored locked test set. Label provenance and reviewer disagreement; do not use test failures for repeated training without a fresh final holdout.

DPO is an optional follow-up for choosing helpful compliant rewrites over excessive refusal. Add it only after an SFT baseline and a reviewed preference dataset exist.

## Runtime design

authenticated request -> server-selected tenant/version -> policy registry -> deterministic checks + adapter inference -> decision arbitration -> rewrite verification -> delivery or escalation -> evidence record

Use FastAPI for the service, a pinned inference server compatible with the chosen model and adapters, and SQLite locally or PostgreSQL for a deployed demo. Package the service in Docker.

Security and failure behavior:

- Derive tenant identity from authentication, never from an arbitrary adapter ID in the request body.
- Resolve one immutable tuple of policy hash, base checkpoint, adapter revision, tokenizer revision, and decoding settings per request.
- Never fall back to another tenant's adapter if loading fails.
- Queue for review or withhold delivery on unknown policies, inference timeout, malformed output, or failed rewrite verification.
- Keep delivered text withheld until enforcement finishes; do not stream unchecked tokens to the customer.
- Verify rewrites with structured rules and a separate verifier where practical. Reusing the same model can repeat the same mistake, so report that limitation.
- Log version identifiers and evidence with retention controls. Use fictional data in the demo.

The endpoint accepts a message and authenticated context and returns a structured decision. It does not execute a refund or other financial action.

## Evaluation harness

Compare four systems on identical locked examples:

1. Deterministic checks only.
2. Untuned model with the relevant policy in its prompt.
3. Shared post-trained enforcement checkpoint with the policy in its prompt.
4. Shared checkpoint plus the customer LoRA and the same policy context.

Measure:

| Metric | What it proves |
| --- | --- |
| Violation recall by severity | Whether dangerous messages get through |
| False-block rate on compliant inputs | Whether enforcement frustrates ordinary customers |
| Macro F1 across four verdicts | Whether the service distinguishes handling choices |
| Changed-case accuracy | Whether v2 behavior follows the update |
| Invariant regression rate | Whether unrelated correct behavior breaks |
| Paired policy sensitivity | Whether identical text follows the correct tenant/version |
| Evidence span correctness and policy-ID validity | Whether explanations identify real evidence |
| Rewrite compliance and fact preservation | Whether fixes remain useful and accurate |
| Cross-tenant routing failures | Whether requests use another customer's artifacts |
| p50/p95 latency and throughput | Whether the service is usable under stated load |
| GPU-seconds and cost per 1,000 decisions | Whether efficiency improves in measured conditions |

Report counts, denominators, confidence intervals, hardware, input/output lengths, concurrency, warm/cold adapter loading, and the exact model revisions. Do not market a tiny test set as proof of production safety.

## Faster, cheaper evaluations

Tag cases with policy dependencies. After a policy diff, run directly affected cases plus an invariant sentinel set first. Cache exact predictions using the complete inference configuration and input as the key. Changing an adapter invalidates that adapter's cached predictions, even for apparently unrelated policies.

Batch by compatible adapter to reduce serving churn, with a bounded queue and recorded latency tradeoff. Use deterministic schema/rule checks first; use human review and optional model judges for semantic rewrite quality. Model judges are supplementary evidence, not definitive labels.

Run the complete locked suite before release. Compare selective triage with the full suite: wall time, GPU-seconds, and regressions the triage missed. Policy dependency tags may miss indirect changes, which is why the full release gate remains necessary.

## Deployment experiment

Run v2 in shadow mode against fictional traffic while v1 remains active. Review failures, then run a bounded demo canary with a rollback mechanism. Promotion requires acceptable changed-case performance, invariant regressions, violation recall, helpfulness, tenant isolation, and latency against predeclared thresholds.

Simulate an adapter-loading failure, a timeout, a wrong-tenant request, and a failed rewrite. Show the response and audit event. A deployed portfolio demo demonstrates deployment experience; it is not evidence of operating real customer production workloads.

## Ten working-day plan

1. Define fictional policies, trusted context, scenario taxonomy, output schema and evaluation splits.
2. Author reviewed seed cases, hard negatives and paired policy-update examples.
3. Implement deterministic and prompted baselines; freeze the first test set.
4. Train shared checkpoint and customer adapters; record seeds, revisions and training logs.
5. Run paired evals and inspect failures; tune against validation data only.
6. Add cached/batched triage and compare with the full evaluation suite.
7. Implement authenticated API routing, registry, rewrite checks and failure handling.
8. Deploy a containerized demo and measure load behavior on stated hardware.
9. Build replay UI, shadow-update demonstration and rollback walkthrough.
10. Freeze final artifacts, run locked tests, publish model/eval cards and record a three-minute demo.

This schedule assumes Python/ML familiarity and access to a suitable GPU. Training and hosting budget must be established before paid resource provisioning.

## What to publish

- Reproducible repository with environment lockfile and commands for dataset generation, training, evaluation and serving.
- Dataset card describing synthetic origin, splits, review coverage and limitations.
- Adapter artifacts or reproducible training instructions where license permits.
- Measured baseline table and per-slice failures; leave unmeasured cells empty.
- Training logs, cost accounting, load-test output and a model card.
- Live demo, a three-minute video, and a short engineering note explaining one important failure and its fix.

Interview opening after implementation: "I built a system for testing whether customer-specific compliance adapters change correctly when policy changes. Here are the baseline comparison, paired update benchmark, eval-cost tradeoffs, and deployment failure modes."

Only substitute real measured numbers into your application. No project can guarantee an offer, and global novelty cannot be established by a short search.

## Why it fits ZeroDrift

The supplied hiring post emphasizes customer LoRA adapters, faster/cheaper evals and model deployment. ZeroDrift's public website describes pass/rewrite/block/escalate enforcement, customer policy adapters and verified rewrites. This project targets those responsibilities through one focused experiment rather than reproducing every product feature.

Sources checked October 4, 2026:

- https://zerodrift.ai/ redirects to https://zerodrift.com/
- https://zerodrift.com/model/anchor describes customer-trained LoRA adapters.
- https://www.linkedin.com/company/zerodrift/

Company product descriptions are first-party claims. This kit does not reproduce or validate their reported performance figures.
