"""Trusted support context adapter. Seed fixtures from an administrative CLI."""
from contextlib import closing
import sqlite3
from .engine import validate_input


def write(path,tenant,ticket,amount,approved):
    context={'fee_amount':amount,'currency':'USD','supervisor_approved':approved}
    validate_input('Hello!',context)
    if tenant not in {'harbor','cedar'}: raise ValueError('Unknown tenant')
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS support_context (tenant TEXT,ticket TEXT,amount TEXT,approved INTEGER,PRIMARY KEY(tenant,ticket))')
        conn.execute('INSERT OR REPLACE INTO support_context VALUES (?,?,?,?)',(tenant,ticket,str(amount),int(approved)))


def read(path,tenant,ticket):
    if not path.exists(): raise sqlite3.OperationalError('Trusted context store unavailable')
    with closing(sqlite3.connect(path)) as conn:
        row=conn.execute('SELECT amount,approved FROM support_context WHERE tenant=? AND ticket=?',(tenant,ticket)).fetchone()
    if row is None: raise LookupError('Ticket not found for authenticated tenant')
    return {'fee_amount':row[0],'currency':'USD','supervisor_approved':bool(row[1])}
