"""Six measured facts, never a target verdict or an engine prediction."""
from decimal import Decimal
import re
from switchboard.engine import resolve,validate_input

NAMES=('verified_approval','trusted_usd_fee','single_amount','amount_matches','within_unapproved_limit','all_refunds_need_approval')


def features(message,context,tenant,version):
    validate_input(message,context)
    policy=resolve(tenant,version)
    amounts=re.findall(r'\$(\d+(?:\.\d+)?)',message)
    known=context.get('currency')=='USD' and 'fee_amount' in context
    matched=bool(known and len(amounts)==1 and Decimal(amounts[0])==Decimal(str(context['fee_amount'])))
    within=bool(known and not policy.all_refunds_require_approval and Decimal(str(context['fee_amount']))<=policy.limit)
    return [float(context.get('supervisor_approved') is True),float(known),float(len(amounts)==1),float(matched),float(within),float(policy.all_refunds_require_approval)]
