"""The last N ledger rows (the receipts)."""
NAME, DOC = "ledger_tail", __doc__.strip()
ARGS = {"n": {"type": "number", "default": 20}}


def run(n=20):
    from ..ledger import rows
    return {"rows": rows(int(n))}
