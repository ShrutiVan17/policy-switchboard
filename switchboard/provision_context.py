"""Administrative fixture provisioning, not a customer-facing approval endpoint."""
import argparse
from pathlib import Path
from .context_store import write


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--tenant',required=True,choices=['harbor','cedar'])
    p.add_argument('--ticket',required=True)
    p.add_argument('--amount',required=True)
    p.add_argument('--approved',action='store_true')
    p.add_argument('--database',default='artifacts/trusted-context.sqlite')
    a=p.parse_args()
    write(Path(a.database),a.tenant,a.ticket,a.amount,a.approved)
    print('Trusted fictional support context provisioned')


if __name__=='__main__': main()
