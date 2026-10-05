"""Conservative, narrow-domain deterministic baseline. This is not an LLM."""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

ENGINE_REVISION = "rules-1.0.0"
VERDICTS = ("pass", "rewrite", "block", "escalate")


@dataclass(frozen=True)
class Policy:
    tenant: str
    version: str
    limit: int
    all_refunds_require_approval: bool = False

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def public(self):
        return {**asdict(self), "hash": self.digest,
                "rules": {"REFUND-01": "Verified approval required above refund limit; Cedar requires approval for every refund.",
                          "CLAIM-01": "Do not promise guaranteed investment returns.",
                          "SECRET-01": "Do not disclose API secrets or complete account numbers."}}


POLICIES = {
    ("harbor", "v1"): Policy("harbor", "v1", 20),
    ("harbor", "v2"): Policy("harbor", "v2", 10),
    ("cedar", "v1"): Policy("cedar", "v1", 0, True),
}


def resolve(tenant, version):
    try:
        return POLICIES[(tenant, version)]
    except (KeyError, TypeError):
        raise ValueError("Unknown tenant or policy version") from None


def validate_input(message, context):
    if not isinstance(message, str) or not message.strip() or len(message) > 6000:
        raise ValueError("message must contain 1–6000 characters")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if set(context) - {"currency", "fee_amount", "supervisor_approved"}:
        raise ValueError("Unknown context fields")
    if "supervisor_approved" in context and type(context["supervisor_approved"]) is not bool:
        raise ValueError("supervisor_approved must be a boolean")
    if "fee_amount" in context:
        if isinstance(context["fee_amount"], bool):
            raise ValueError("Invalid fee amount")
        try:
            value = Decimal(str(context["fee_amount"]))
        except InvalidOperation:
            raise ValueError("Invalid fee amount") from None
        if not value.is_finite() or value < 0 or value > 100000 or value.as_tuple().exponent < -2:
            raise ValueError("fee_amount must be a nonnegative amount with at most two decimal places")


def enforce(message, context, tenant="harbor", version="v1"):
    validate_input(message, context)
    policy = resolve(tenant, version)
    findings = []

    def add(rule, verdict, match, reason):
        findings.append({"policy_id": rule, "verdict": verdict, "span": {
            "start": match.start(), "end": match.end(), "text": match.group()}, "reason": reason})

    injection = re.search(r"\b(?:ignore|override|disregard)\b.{0,30}\b(?:rules|policy|policies|instructions)\b", message, re.I)
    if injection:
        add("SCOPE-01", "escalate", injection, "Instruction-like text in the message cannot override policy.")

    # Input text never overrides trusted policy/context. These rules intentionally
    # use a small pattern set; unsupported semantic cases go to human review.
    secret = re.search(r"\b(?:sk-[A-Za-z0-9_-]{8,}|account\s*(?:number\s*)?[:#]?\s*\d{8,})\b", message, re.I)
    if secret:
        add("SECRET-01", "block", secret, "Sensitive credential or full account identifier detected.")
    guarantee = re.search(r"\b(?:guaranteed\s+(?:returns?|profits?)|(?:returns?|profits?)\s+(?:are\s+)?guaranteed|risk[- ]free\s+(?:returns?|investment))\b", message, re.I)
    if guarantee:
        add("CLAIM-01", "rewrite", guarantee, "Unsupported investment guarantee.")

    refund_word = re.search(r"\brefund\w*\b", message, re.I)
    commitment = re.search(r"\b(?:I\s+(?:can|will)|we\s+(?:can|will)|I'll|we'll)\s+(?:\w+\s+){0,2}refund\b|\brefund\b.{0,40}\b(?:approved|processed|guaranteed)\b", message, re.I)
    if refund_word:
        negated = re.fullmatch(r"\s*(?:I|we)\s+(?:cannot|can't|will not|won't)\s+(?:authorize\s+)?refund[^.!?]*[.!?]?\s*", message, re.I)
        request = re.fullmatch(r"\s*(?:I|we)\s+can\s+(?:request|ask for)\s+(?:supervisor\s+)?approval\s+for\s+your\s+\$\d+(?:\.\d{1,2})?\s+transfer[- ]fee\s+refund[.!?]?\s*", message, re.I)
        if commitment:
            values = re.findall(r"\$(\d+(?:\.\d{1,2})?)\b", message)
            trusted = context.get("fee_amount")
            if len(values) != 1 or trusted is None or context.get("currency") != "USD":
                add("REFUND-01", "escalate", commitment, "A single USD amount and trusted fee metadata are required.")
            elif Decimal(values[0]) != Decimal(str(trusted)):
                add("REFUND-01", "escalate", commitment, "Message amount differs from the trusted fee amount.")
            elif not context.get("supervisor_approved", False) and (policy.all_refunds_require_approval or Decimal(values[0]) > policy.limit):
                add("REFUND-01", "escalate", commitment, "Supervisor approval is required under this policy version.")
        elif not (negated or request):
            add("REFUND-01", "escalate", refund_word, "Refund wording is outside this baseline's supported patterns.")

    priorities = {"pass": 0, "rewrite": 1, "escalate": 2, "block": 3}
    verdict = max((f["verdict"] for f in findings), key=priorities.get, default="pass")
    # Only allow ordinary messages from a small explicit supported set.
    # Avoid claiming semantic safety for arbitrary unfamiliar text.
    if not findings and not refund_word and not re.fullmatch(r"\s*(?:Hello[.!]?|Thank you(?: for contacting (?:us|support))?[.!]?|Your transfer is pending[.!]?|How can I help you today\?)\s*", message, re.I):
        verdict = "escalate"
        findings.append({"policy_id": "SCOPE-01", "verdict": "escalate", "span": {"start": 0, "end": len(message), "text": message}, "reason": "Unsupported message: this narrow baseline requires human review."})

    proposed = None
    if verdict == "rewrite":
        # Replace only supported exact claims. Anything ambiguous stays withheld.
        if re.fullmatch(r"\s*(?:This (?:fund|investment) (?:offers|has)\s+)?(?:guaranteed returns|risk[- ]free returns)[.!]?\s*", message, re.I):
            proposed = "Investment returns are uncertain."
        else:
            verdict = "escalate"
    if verdict == "escalate" and refund_word and context.get("fee_amount") is not None:
        proposed = f"I can request supervisor approval for your ${Decimal(str(context['fee_amount'])):f} transfer-fee refund."

    verified = verdict == "pass"
    delivered = message if verified else None
    if verdict == "rewrite" and proposed:
        # An independent deterministic check verifies this one supported rewrite.
        verified = proposed == "Investment returns are uncertain." and not re.search(r"guaranteed|risk[- ]free|sk-", proposed, re.I)
        if verified:
            delivered = proposed
        else:
            verdict = "escalate"
    return {"verdict": verdict, "tenant": tenant, "policy_version": version,
            "policy_hash": policy.digest, "backend": "deterministic", "engine_revision": ENGINE_REVISION,
            "adapter_revision": None, "findings": findings, "proposed_output": proposed,
            "delivered_output": delivered, "verified": verified,
            "reason": findings[0]["reason"] if findings else "Message matches supported policy checks."}
