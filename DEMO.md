# Three-minute walkthrough

## 0:00 — A concrete policy change

Send the default $15 refund. Harbor's old $20 limit allows it; the new $10 limit and Cedar's approval policy hold it. Try $5 to show behavior that must remain correct. The approval toggle is fictional trusted context; production must fetch approval from a secure source.

## 0:40 — Other decisions

Try guaranteed returns and private information. A narrow supported guarantee is rewritten and verified; credentials are blocked. Open Saved checks to inspect redacted evidence and policy identities.

## 1:10 — Evaluations

Run 72 checks. Show required-change pairs, invariant cases and raw answers. The rules match all curated cases; that is an implementation smoke check, not general compliance accuracy. Selective iteration covers 48 cases; repeat runs use exact-configuration caching.

## 1:40 — Real post-training

Open AI lab and load measured results. Compare the pinned 135M base model with three customer/policy LoRA adapters. Explain actual correct decisions, invalid answers and gate failures using the recorded numbers. Show the separate wording-family holdout; do not claim every smoke case is unseen.

## 2:20 — Serving and trust

Compare a message with AI. Model inference is real, but generated text is never delivered. Explain the tenant key, policy hash, pinned base revision, adapter weight hash and adapter-switching lock. Show why model errors reject readiness, and why even perfect synthetic results only permit shadow research.

## 2:50 — Engineering tradeoffs

The small model fits the local 4 GB GPU; it is not ZeroDrift's proprietary enforcement model. The next customer-ready milestone requires independently reviewed data and operational validation. Discuss the actual failure patterns and what additional training data or a stronger model would test.

Use [the measured report](docs/MODEL_REPORT.md) and [interview guide](docs/INTERVIEW.md). Describe local post-training and shadow serving accurately; do not label this public production deployment experience.
